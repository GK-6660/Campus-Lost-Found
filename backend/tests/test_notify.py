"""F。匹配、通知去重和权限；沿用当前进程内存储，不依赖 E1 的空实现。"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

import pytest
from app import items, match, notify
from app.api.deps import require_user
from app.errors import NotFound
from app.main import app
from app.schemas import Item, ItemCreate, Reason, Score, User


@pytest.fixture(autouse=True)
def isolated_stores(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(items, "ITEMS", {})
    monkeypatch.setattr(items, "_SEQ", {})
    monkeypatch.setattr(match, "MATCHES", {})
    monkeypatch.setattr(notify, "_NOTIFICATIONS", {})
    previous = app.dependency_overrides.copy()
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()
    app.dependency_overrides.update(previous)


def _user(user_id: str = "owner") -> User:
    return User(id=user_id, student_no=user_id, nickname=user_id, role="user")


def _item(kind: str, owner_id: str, **fields) -> Item:
    today = datetime.now(timezone.utc).date().isoformat()
    values = dict(
        type=kind,
        category="earphones",
        color="black",
        brand="Apple",
        description="黑色耳机",
        occurred_on=today,
        day_part="morning",
        visited_places=["library"] if kind == "lost" else None,
        found_place="library" if kind == "found" else None,
    )
    values.update(fields)
    return items.create_item(_user(owner_id), ItemCreate(request_id="create", **values))


def _publish(item: Item) -> Item:
    return items.publish_item(_user(item.owner_id), item.id, item.version)


def _pair() -> tuple[Item, Item]:
    lost, found = _item("lost", "owner"), _item("found", "finder")
    _publish(lost)
    _publish(found)
    return lost, found


def _send(user_id="owner", lost_id="lost", found_id="found", **changes) -> None:
    values = dict(
        user_id=user_id,
        lost_id=lost_id,
        found_id=found_id,
        score=60,
        hard_conflict=False,
        subscribed=True,
        title="新候选",
        body="图书馆，类别相同：耳机。物品可能已经不在。",
    )
    values.update(changes)
    notify.maybe_new_match(**values)


def test_same_pair_notifies_once() -> None:
    """同一对重复、并发调用和已读后重跑，仍只有一条通知。"""
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: _send(), range(12)))
    unread, notices = notify.list_for("owner")
    assert unread == len(notices) == 1
    notify.mark_read("owner", notices[0].id)
    _send()
    assert notify.list_for("owner")[0] == 0
    assert len(notify.list_for("owner")[1]) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"score": 59},
        {"hard_conflict": True},
        {"subscribed": False},
    ],
)
def test_notification_conditions(changes) -> None:
    _send(**changes)
    assert notify.list_for("owner") == (0, [])
    # 未达到条件的调用不能占用以后真正满足条件的去重键。
    _send()
    assert notify.list_for("owner")[0] == 1


def test_notification_deduplication_scope() -> None:
    _send()
    _send(found_id="another-found")
    _send(lost_id="another-lost")
    _send(user_id="another-user")
    assert len(notify.list_for("owner")[1]) == 3
    assert len(notify.list_for("another-user")[1]) == 1


def test_publish_found_creates_candidate_and_one_notification() -> None:
    lost, found = _pair()
    rows = match.list_matches(_user(), lost.id)
    assert len(rows) == 1
    assert rows[0].score == 100
    assert rows[0].notify is True
    original_id = rows[0].id
    _publish(found)
    match.rematch_for_lost(lost.id)
    assert match.list_matches(_user(), lost.id)[0].id == original_id
    unread, notices = notify.list_for("owner")
    assert unread == len(notices) == 1
    assert notices[0].lost_item_id == lost.id
    assert notices[0].found_item_id == found.id
    assert "图书馆" in notices[0].body
    assert "类别相同：耳机" in notices[0].body
    assert "物品可能已经不在" in notices[0].body
    assert notify.list_for("finder") == (0, [])


def test_publish_lost_after_found_also_matches() -> None:
    found = _publish(_item("found", "finder"))
    lost = _publish(_item("lost", "owner"))
    assert match.list_matches(_user(), lost.id)[0].found_item_id == found.id
    assert notify.list_for("owner")[0] == 1


@pytest.mark.parametrize("kind", ["lost", "found"])
@pytest.mark.parametrize("invalid", ["same_owner", "draft", "closed", "returned", "expired"])
def test_rematch_excludes_ineligible_items(kind, invalid) -> None:
    other_kind = "found" if kind == "lost" else "lost"
    target = _publish(_item(kind, "owner"))
    other = _item(other_kind, "owner" if invalid == "same_owner" else "other")
    if invalid != "draft":
        items.mark_open(other)
    if invalid == "closed":
        items.mark_closed(other)
    elif invalid == "returned":
        items.mark_returned_pair(target, other)
        items.mark_open(target)
    elif invalid == "expired":
        other.expires_on = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    rematch = match.rematch_for_lost if kind == "lost" else match.rematch_for_found
    rematch(target.id)
    assert match.list_matches(_user(), target.id) == []
    assert notify.list_for("owner") == (0, [])


def test_unconfirmed_found_waits_for_confirmation() -> None:
    lost = _publish(_item("lost", "owner"))
    found = _item("found", "finder")
    for tag in found.tags:
        tag.confirmed = False
    items.mark_open(found)
    match.rematch_for_lost(lost.id)
    match.rematch_for_found(found.id)
    assert match.list_matches(_user(), lost.id) == []
    assert notify.list_for("owner") == (0, [])
    for tag in found.tags:
        tag.confirmed = True
    match.on_tags_confirmed(found)
    assert len(match.list_matches(_user(), lost.id)) == 1
    assert notify.list_for("owner")[0] == 1


def test_unconfirmed_lost_tag_is_not_scored_or_mutated() -> None:
    lost = _item("lost", "owner")
    lost.tags[0].confirmed = False
    _publish(lost)
    _publish(_item("found", "finder"))
    row = match.list_matches(_user(), lost.id)[0]
    assert next(reason.points for reason in row.reasons if reason.code == "category") == 0
    assert lost.category == "earphones"


@pytest.mark.parametrize(
    "points,visible,notified",
    [
        (39, False, False),
        (40, True, False),
        (59, True, False),
        (60, True, True),
    ],
)
def test_candidate_and_notification_thresholds(monkeypatch, points, visible, notified) -> None:
    monkeypatch.setattr(
        match.scoring,
        "score_pair",
        lambda *_: Score(
            score=points,
            reasons=[Reason(code="category", points=points, text="类别相同：耳机")],
            conflicts=[],
            hard_conflict=False,
        ),
    )
    lost, _ = _pair()
    assert bool(match.list_matches(_user(), lost.id)) is visible
    assert bool(notify.list_for("owner")[0]) is notified


def test_hard_conflict_blocks_notification_even_with_high_score(monkeypatch) -> None:
    monkeypatch.setattr(
        match.scoring,
        "score_pair",
        lambda *_: Score(
            score=70,
            reasons=[],
            hard_conflict=True,
            conflicts=[Reason(code="category", points=-30, text="类别冲突")],
        ),
    )
    lost, _ = _pair()
    row = match.list_matches(_user(), lost.id)[0]
    assert row.conflicts[0].points == -30
    assert row.notify is False
    assert notify.list_for("owner") == (0, [])


def test_subscription_is_checked_again_when_rematching() -> None:
    lost = _publish(_item("lost", "owner", subscribe_matches=False))
    _publish(_item("found", "finder"))
    assert match.list_matches(_user(), lost.id)[0].notify is False
    assert notify.list_for("owner") == (0, [])
    lost.subscribe_matches = True
    match.rematch_for_lost(lost.id)
    assert notify.list_for("owner")[0] == 1


def test_top_five_sorted_and_public_for_both_owners() -> None:
    lost = _publish(_item("lost", "owner"))
    for index in range(7):
        _publish(_item("found", f"finder-{index}", color="white" if index < 2 else "black"))
    rows = match.list_matches(_user(), lost.id)
    assert len(rows) == 5
    assert [row.score for row in rows] == [100] * 5
    public = rows[0].counterpart.model_dump()
    assert set(public) == {
        "item_id",
        "type",
        "category",
        "color",
        "place_code",
        "place_note",
        "occurred_on",
        "day_part",
        "image_id",
    }
    found = items.ITEMS[rows[0].found_item_id]
    reverse = match.list_matches(_user(found.owner_id), found.id)[0]
    assert reverse.counterpart.item_id == lost.id
    assert reverse.counterpart.place_code == "library"
    assert "visited_places" not in reverse.counterpart.model_dump()
    with pytest.raises(NotFound):
        match.list_matches(_user("stranger"), lost.id)
    with pytest.raises(NotFound):
        match.list_matches(_user(), "missing")


def test_closed_and_returned_candidates_disappear_without_changing_item_versions() -> None:
    lost, found = _pair()
    version = found.version
    match.rematch_for_found(found.id)
    assert found.version == version
    items.mark_closed(found)
    assert match.list_matches(_user(), lost.id) == []
    items.mark_open(found)
    items.mark_returned_pair(lost, found)
    match.suppress_found(found.id)
    match.rematch_for_found(found.id)
    assert match.MATCHES == {}
    assert match.list_matches(_user(), lost.id) == []
    assert len(notify.list_for("owner")[1]) == 1


def test_returned_and_taken_down_notifications() -> None:
    lost, found = _pair()
    notify.found_returned(["other", "other"], lost.id, found.id)
    notices = notify.list_for("other")[1]
    assert len(notices) == 1
    assert notices[0].type == "found_returned"
    assert "图书馆" in notices[0].body
    for item in (lost, found):
        notify.taken_down(item.owner_id, item.id)
        notice = notify.list_for(item.owner_id)[1][0]
        assert notice.type == "item_taken_down"
        assert (notice.lost_item_id, notice.found_item_id) == (
            (item.id, None) if item.type == "lost" else (None, item.id)
        )


def test_notification_list_limit_total_unread_and_read_permissions(monkeypatch) -> None:
    # 固定时钟，明确验证同一时间戳下也必须让后插入的通知排在前面。
    class FixedClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 10, tzinfo=timezone.utc)

    monkeypatch.setattr(notify, "datetime", FixedClock)
    for index in range(103):
        _send(found_id=str(index))
    unread, notices = notify.list_for("owner")
    assert unread == 103
    assert len(notices) == 100
    assert notices[0].found_item_id == "102"
    assert notices[-1].found_item_id == "3"
    with pytest.raises(NotFound):
        notify.mark_read("stranger", notices[0].id)
    with pytest.raises(NotFound):
        notify.mark_read("owner", "missing")
    assert notify.mark_read("owner", notices[0].id).read is True
    assert notify.mark_read("owner", notices[0].id).read is True
    assert notify.list_for("owner")[0] == 102
    # 调用方不能借返回对象改存储中的通知。
    notices[1].read = True
    assert notify.list_for("owner")[0] == 102
    assert notify.list_for("stranger") == (0, [])


def _request(method: str, path: str, user: User | None = None) -> tuple[int, dict]:
    """直接驱动 ASGI，使用真实路由和异常处理，无需添加 httpx 依赖。"""
    if user is not None:
        app.dependency_overrides[require_user] = lambda: user
    messages = []

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        messages.append(message)

    scope = dict(
        type="http",
        asgi={"version": "3.0"},
        http_version="1.1",
        method=method,
        scheme="http",
        path=path,
        raw_path=path.encode(),
        query_string=b"",
        root_path="",
        headers=[],
        client=("127.0.0.1", 1),
        server=("testserver", 80),
    )
    try:
        asyncio.run(app(scope, receive, send))
    finally:
        app.dependency_overrides.pop(require_user, None)
    status = next(
        message["status"] for message in messages if message["type"] == "http.response.start"
    )
    body = b"".join(message.get("body", b"") for message in messages)
    return status, json.loads(body)


def test_routes_authentication_empty_lists_and_ownership() -> None:
    lost = _publish(_item("lost", "owner"))
    for method, path in [
        ("GET", f"/api/v1/items/{lost.id}/matches"),
        ("GET", "/api/v1/notifications"),
        ("POST", "/api/v1/notifications/missing/read"),
    ]:
        status, body = _request(method, path)
        assert status == 401
        assert body["error"]["code"] == "unauthenticated"
    assert _request("GET", f"/api/v1/items/{lost.id}/matches", _user()) == (
        200,
        {"item_id": lost.id, "matches": []},
    )
    assert _request("GET", "/api/v1/notifications", _user()) == (
        200,
        {"unread_count": 0, "items": []},
    )
    assert _request("GET", f"/api/v1/items/{lost.id}/matches", _user("stranger"))[0] == 404


def test_routes_return_candidates_notifications_and_mark_read() -> None:
    lost, _ = _pair()
    status, body = _request("GET", f"/api/v1/items/{lost.id}/matches", _user())
    assert status == 200
    assert body["matches"][0]["score"] == 100
    assert "owner_id" not in body["matches"][0]["counterpart"]
    status, body = _request("GET", "/api/v1/notifications", _user())
    assert status == 200
    assert body["unread_count"] == 1
    notice_id = body["items"][0]["id"]
    path = f"/api/v1/notifications/{notice_id}/read"
    assert _request("POST", path, _user("stranger"))[0] == 404
    status, notice = _request("POST", path, _user())
    assert status == 200
    assert notice["read"] is True
    assert "user_id" not in notice
    assert _request("GET", "/api/v1/notifications", _user())[1]["unread_count"] == 0
