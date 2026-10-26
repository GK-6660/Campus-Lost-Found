"""E2。物品的创建、发布和版本。

别人的模块还是空壳（E1 的 current_user 与 idempotency、F 的 match、G 的 extract），
按《工作说明》用说明书里的假数据把它们替换掉，只测 items.py 这一段。

接口层：本机没装 httpx，用不了 fastapi.testclient，所以直接驱动 ASGI 应用。
这样 422 / 409 的响应体（error.code、fields、current_version）也真的被测到。
字段和错误码见《软件设计说明书》5.5、5.14、6.3、7.3、8.2、8.3。
"""

import asyncio
import json

import pytest
from app import extract, items, match
from app.api import items as api_items
from app.api.deps import require_user
from app.errors import Forbidden, InvalidState, NotFound, ValidationError, VersionConflict
from app.main import app
from app.schemas import Item, ItemCreate, ItemPatch, Job, User

# 主人视图的键。空值必须写成 null，键一个都不能少，owner_id 不得出现。
ITEM_KEYS = {
    "id",
    "type",
    "status",
    "version",
    "category",
    "color",
    "brand",
    "description",
    "occurred_on",
    "day_part",
    "visited_places",
    "places_ordered",
    "found_place",
    "place_note",
    "subscribe_matches",
    "image_id",
    "tags",
    "job_id",
    "expires_on",
    "created_at",
    "updated_at",
}


@pytest.fixture(autouse=True)
def clean_store() -> None:
    """每个测试都用一张空表。"""
    items.ITEMS.clear()
    items._SEQ.clear()


@pytest.fixture(autouse=True)
def fake_idempotency(monkeypatch: pytest.MonkeyPatch) -> None:
    """E1 的 request_id 去重还没实现，这里一律按「没做过」处理。"""
    monkeypatch.setattr(api_items, "replay_if_done", lambda user_id, request_id: None)
    monkeypatch.setattr(api_items, "save", lambda user_id, request_id, response: None)


def _user(user_id: str = "u1", role: str = "user") -> User:
    return User(id=user_id, student_no=user_id, nickname=user_id, role=role)


def _call(method: str, path: str, payload: dict | None, user: User) -> tuple[int, dict]:
    """直接调一次 ASGI 应用，返回 (状态码, 响应 JSON)。"""
    body = b"" if payload is None else json.dumps(payload).encode()
    headers = [(b"host", b"testserver")]
    if payload is not None:
        headers.append((b"content-type", b"application/json"))
    headers.append((b"content-length", str(len(body)).encode()))
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": headers,
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "state": {},
    }
    sent: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        sent.append(message)

    app.dependency_overrides[require_user] = lambda: user
    try:
        asyncio.run(app(scope, receive, send))
    finally:
        app.dependency_overrides.clear()

    status = next(m["status"] for m in sent if m["type"] == "http.response.start")
    raw = b"".join(m.get("body", b"") for m in sent if m["type"] == "http.response.body")
    return status, (json.loads(raw) if raw else {})


def _create(owner: User, **fields: object) -> Item:
    """本模块自己的函数，测试里直接调，省一层。"""
    return items.create_item(owner, ItemCreate(request_id="r-create", **fields))


def test_publish_missing_place_is_rejected() -> None:
    """失物发布时没有楼，接口拒绝。"""
    owner = _user()
    created_status, created = _call(
        "POST",
        "/api/v1/items",
        {
            "type": "lost",
            "request_id": "r-1",
            "occurred_on": "2026-09-29",
            "day_part": "morning",
        },
        owner,
    )
    assert created_status == 201
    assert set(created) == ITEM_KEYS
    assert created["status"] == "draft"
    assert created["version"] == 1
    assert created["visited_places"] is None
    assert created["expires_on"] is None

    status, body = _call(
        "POST",
        f"/api/v1/items/{created['id']}/publish",
        {"version": 1, "request_id": "r-2"},
        owner,
    )

    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["fields"] == [{"name": "visited_places", "code": "required"}]
    # 被拒绝就是没发布：状态和版本都不能动
    assert items.ITEMS[created["id"]].status == "draft"
    assert items.ITEMS[created["id"]].version == 1


def test_update_with_stale_version_conflicts() -> None:
    """用旧版本号修改，接口要求刷新。"""
    owner = _user()
    _, created = _call("POST", "/api/v1/items", {"type": "lost", "request_id": "r-1"}, owner)

    ok_status, updated = _call(
        "PATCH",
        f"/api/v1/items/{created['id']}",
        {"version": 1, "request_id": "r-2", "description": "黑色耳机"},
        owner,
    )
    assert ok_status == 200
    assert updated["version"] == 2

    status, body = _call(
        "PATCH",
        f"/api/v1/items/{created['id']}",
        {"version": 1, "request_id": "r-3", "description": "再改一次"},
        owner,
    )

    assert status == 409
    assert body["error"]["code"] == "version_conflict"
    assert body["error"]["current_version"] == 2  # 客户端刷新后再试
    assert items.ITEMS[created["id"]].description == "黑色耳机"


def test_publish_lost_opens_item_and_asks_for_matches(monkeypatch: pytest.MonkeyPatch) -> None:
    """失物发布：状态变 open、写 expires_on、立刻匹配。"""
    asked: list[str] = []
    monkeypatch.setattr(match, "rematch_for_lost", asked.append)
    owner = _user()
    item = _create(
        owner,
        type="lost",
        occurred_on="2026-09-29",
        day_part="evening",
        visited_places=["library", "canteen_1"],
    )

    published = items.publish_item(owner, item.id, item.version)

    assert published.status == "open"
    assert published.version == 2
    assert published.expires_on == "2026-10-29"  # occurred_on 加 30 天
    assert published.places_ordered is True  # 失物默认按顺序走
    assert published.subscribe_matches is True  # 失物默认收新候选
    assert asked == [item.id]


def test_publish_found_with_image_enqueues_without_matching(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """拾获有图、标签未确认：建识别任务，且不得匹配（8.2）。"""
    monkeypatch.setattr(items, "get_own_file", lambda file_id, owner_id: None)
    monkeypatch.setattr(
        extract,
        "enqueue",
        lambda item: Job(
            id="job-1",
            item_id=item.id,
            status="processing",
            error_code=None,
            prompt_version="tags-v1",
        ),
    )

    def _must_not_match(found_id: str) -> None:
        raise AssertionError("标签没确认的拾获不得匹配")

    monkeypatch.setattr(match, "rematch_for_found", _must_not_match)

    owner = _user()
    item = _create(
        owner,
        type="found",
        occurred_on="2026-09-30",
        day_part="afternoon",
        found_place="gym",
        image_id="f1",
    )

    published = items.publish_item(owner, item.id, item.version)

    assert published.status == "open"
    assert published.job_id == "job-1"  # API-ITEM-03 的响应要带 job_id
    assert published.visited_places is None  # 拾获没有路线
    assert published.subscribe_matches is None


def test_open_confirmed_item_only_allows_subscribe_change(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """已经 open 且标签已确认：只能改是否接收新候选通知。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user()
    item = _create(
        owner,
        type="lost",
        category="earphones",
        color="black",
        occurred_on="2026-09-29",
        day_part="morning",
        visited_places=["library"],
    )
    published = items.publish_item(owner, item.id, item.version)

    # 手填的类别和颜色是用户标签，且已确认
    tags = {tag.key: tag for tag in published.tags}
    assert tags["category"].source == "user"
    assert tags["category"].confirmed is True

    with pytest.raises(InvalidState):
        items.update_item(
            owner,
            published.id,
            published.version,
            ItemPatch(version=published.version, request_id="r-1", description="改描述"),
        )

    updated = items.update_item(
        owner,
        published.id,
        published.version,
        ItemPatch(version=published.version, request_id="r-2", subscribe_matches=False),
    )
    assert updated.subscribe_matches is False
    assert updated.version == 3


def test_close_requires_open_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """只有 open 的物品可以撤回。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user()
    item = _create(
        owner,
        type="lost",
        occurred_on="2026-09-29",
        day_part="morning",
        visited_places=["dorm"],
    )

    with pytest.raises(InvalidState):
        items.close_item(owner, item.id, item.version)

    items.publish_item(owner, item.id, item.version)
    closed = items.close_item(owner, item.id, item.version)
    assert closed.status == "closed"
    assert closed.version == 3


def test_only_owner_can_change_and_stranger_cannot_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """别人不能改（403）；不是主人也不是管理员时按不存在处理（404）。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user("u1")
    other = _user("u2")
    admin = _user("a1", role="admin")
    item = _create(owner, type="lost", description="黑色耳机")

    status, body = _call(
        "PATCH",
        f"/api/v1/items/{item.id}",
        {"version": 1, "request_id": "r-1", "description": "不是我的"},
        other,
    )
    assert status == 403
    assert body["error"]["code"] == "forbidden"

    status, body = _call("GET", f"/api/v1/items/{item.id}", None, other)
    assert status == 404
    assert body["error"]["code"] == "not_found"

    # 管理员能看主人视图，但同样看不到原图
    status, body = _call("GET", f"/api/v1/items/{item.id}", None, admin)
    assert status == 200
    assert body["id"] == item.id
    assert "owner_id" not in body

    with pytest.raises(Forbidden):
        items.update_item(
            other, item.id, item.version, ItemPatch(version=item.version, request_id="r-2")
        )
    with pytest.raises(NotFound):
        items.get_for_viewer(other, item.id)


def test_public_view_hides_private_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """公开投影不给描述、品牌、主人，也不给失主的整条路线。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user()
    found = _create(
        owner,
        type="found",
        brand="Sony",
        description="右耳有划痕",
        occurred_on="2026-09-29",
        day_part="morning",
        found_place="library",
        place_note="二楼靠窗",
    )

    public = items.to_public_view(found, None).model_dump()

    assert public["place_code"] == "library"  # 拾获用 found_place
    assert public["place_note"] == "二楼靠窗"
    for hidden in ("description", "brand", "owner_id", "visited_places", "student_no", "nickname"):
        assert hidden not in public


def test_list_mine_filters_orders_and_caps(monkeypatch: pytest.MonkeyPatch) -> None:
    """我的列表：只返回本人的、新的在前、可按 type 和 status 过滤、最多 100 条。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user("u1")
    other = _user("u2")
    first = _create(owner, type="lost")
    second = _create(owner, type="found", occurred_on="2026-09-29", day_part="morning")
    third = _create(owner, type="lost")
    other_item = _create(other, type="lost")

    mine = items.list_mine(owner, None, None)
    assert other_item.id not in [item.id for item in mine]
    assert len(mine) == 3
    assert [item.id for item in mine] == [third.id, second.id, first.id]  # 新的在前

    assert [item.id for item in items.list_mine(owner, "found", None)] == [second.id]
    assert [item.id for item in items.list_mine(owner, None, "open")] == []
    assert {item.id for item in items.list_mine(owner, None, "draft")} == {
        first.id,
        second.id,
        third.id,
    }

    bulk = _user("u3")
    for _ in range(105):
        _create(bulk, type="lost")
    assert len(items.list_mine(bulk, None, None)) == 100


def test_lock_returns_live_row_and_returned_pair_bumps_both(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """claims 和 reports 依赖这一段：lock 返回真行，mark_returned_pair 两条都加版本。"""
    monkeypatch.setattr(match, "rematch_for_lost", lambda lost_id: None)
    owner = _user()
    lost = _create(
        owner,
        type="lost",
        occurred_on="2026-09-29",
        day_part="morning",
        visited_places=["library"],
    )
    found = _create(
        owner,
        type="found",
        occurred_on="2026-09-29",
        day_part="morning",
        found_place="library",
    )
    items.publish_item(owner, lost.id, lost.version)
    items.publish_item(owner, found.id, found.version)

    lost_row = items.lock(lost.id, lost.version)
    found_row = items.lock(found.id, found.version)
    versions = (lost_row.version, found_row.version)

    items.mark_returned_pair(lost_row, found_row)

    assert (lost_row.status, found_row.status) == ("returned", "returned")
    assert (lost_row.version, found_row.version) == (versions[0] + 1, versions[1] + 1)
    assert items.ITEMS[lost.id].status == "returned"  # 改的是表里的那一行

    with pytest.raises(VersionConflict) as caught:
        items.lock(lost.id, versions[0])
    assert caught.value.current_version == versions[0] + 1
    with pytest.raises(NotFound):
        items.lock("missing", 1)


def test_empty_patch_and_bad_date_are_rejected() -> None:
    """至少要改一项；日期只认 YYYY-MM-DD。"""
    owner = _user()
    item = _create(owner, type="lost")

    with pytest.raises(ValidationError) as caught:
        items.update_item(owner, item.id, item.version, ItemPatch(version=1, request_id="r-1"))
    assert (caught.value.fields[0].name, caught.value.fields[0].code) == ("body", "required")

    with pytest.raises(ValidationError) as caught:
        items.update_item(
            owner,
            item.id,
            item.version,
            ItemPatch(version=1, request_id="r-2", occurred_on="29/09/2026"),
        )
    assert {field.name: field.code for field in caught.value.fields} == {
        "occurred_on": "unknown_enum"
    }
    assert item.occurred_on is None


def test_replay_of_stored_response_returns_first_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """VER-02：同一 request_id 再提交，返回第一次的结果，不得写出第二条。

    E1 的幂等只存得下 JSON 时，owner_id 会被 schemas.Item 的 exclude=True 拿掉，
    路由要自己补回来，否则第二次提交是 500，而不是第一次的结果。
    """
    owner = _user()
    created_status, created = _call(
        "POST", "/api/v1/items", {"type": "lost", "request_id": "r-1"}, owner
    )
    assert created_status == 201

    stored = {key: value for key, value in created.items() if key != "owner_id"}
    monkeypatch.setattr(api_items, "replay_if_done", lambda user_id, request_id: dict(stored))

    status, replayed = _call(
        "POST", "/api/v1/items", {"type": "lost", "request_id": "r-1"}, owner
    )

    assert status == 201
    assert replayed == created  # 拿到的是第一次的结果
    assert len(items.ITEMS) == 1  # 没有写出第二条
