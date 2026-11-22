"""E2 图片接口：文件头、大小、幂等、归属和候选读取权限。

E1 与 F 尚未实现，按工作说明用假的幂等结果和候选读表隔离依赖。
与 test_items 一样直接驱动 ASGI，测试真实 multipart 和错误 JSON，不新增依赖。
"""

import asyncio
import base64
import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from app import files, items
from app.api import files as api_files
from app.api.deps import require_user
from app.errors import NotFound
from app.main import app
from app.schemas import Item, ItemCreate, Match, User
from starlette.datastructures import UploadFile

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
WEBP = base64.b64decode("UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA")
# JPEG 的文件头样本；这里只测试 CON-08 规定的文件头检查，不做图片解码。
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"
OWNER = User(id="owner", student_no="1001", nickname="拾到者", role="user")
OTHER = User(id="other", student_no="1002", nickname="失主", role="user")
ADMIN = User(id="admin", student_no="1003", nickname="管理员", role="admin")


@pytest.fixture(autouse=True)
def isolated_tables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(files, "FILES", {})
    monkeypatch.setattr(files, "MATCHES", {})
    monkeypatch.setattr(items, "ITEMS", {})
    monkeypatch.setattr(items, "_SEQ", {})
    monkeypatch.setattr(app, "dependency_overrides", {})
    responses: dict[tuple[str, str], dict] = {}
    monkeypatch.setattr(
        api_files, "replay_if_done", lambda user_id, key: responses.get((user_id, key))
    )
    monkeypatch.setattr(
        api_files,
        "save",
        lambda user_id, key, value: responses.update(
            {(user_id, key): value.model_dump(mode="json")}
        ),
    )


def _call(
    method: str,
    path: str,
    user: User | None,
    body: bytes = b"",
    content_type: str | None = None,
) -> tuple[int, dict[str, str], bytes]:
    headers = [(b"host", b"testserver"), (b"content-length", str(len(body)).encode())]
    if content_type:
        headers.append((b"content-type", content_type.encode()))
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
    messages: list[dict] = []

    async def receive() -> dict:
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message: dict) -> None:
        messages.append(message)

    if user is not None:
        app.dependency_overrides[require_user] = lambda: user
    try:
        asyncio.run(app(scope, receive, send))
    finally:
        app.dependency_overrides.pop(require_user, None)
    start = next(message for message in messages if message["type"] == "http.response.start")
    response_headers = {key.decode(): value.decode() for key, value in start["headers"]}
    response_body = b"".join(
        message.get("body", b"") for message in messages if message["type"] == "http.response.body"
    )
    return start["status"], response_headers, response_body


def _upload(
    data: bytes = PNG,
    mime: str = "image/png",
    user: User | None = OWNER,
    request_id: str | None = None,
) -> tuple[int, dict]:
    boundary = "clf-test-boundary"
    key = str(uuid4()) if request_id is None else request_id
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="request_id"\r\n\r\n'
            f"{key}\r\n"
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="redacted.png"\r\nContent-Type: {mime}\r\n\r\n'
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    status, _, raw = _call(
        "POST", "/api/v1/files", user, body, f"multipart/form-data; boundary={boundary}"
    )
    return status, json.loads(raw)


def _assert_invalid_file(status: int, body: dict) -> None:
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["fields"] == [{"name": "file", "code": "invalid_file"}]
    assert not files.FILES


def _item(owner: User, item_type: str, image_id: str | None = None, **fields: object) -> Item:
    today = datetime.now(timezone.utc).date().isoformat()
    values = {
        "type": item_type,
        "request_id": str(uuid4()),
        "category": "earphones",
        "color": "black",
        "occurred_on": today,
        "day_part": "morning",
        "image_id": image_id,
    }
    values.update(fields)
    item = items.create_item(owner, ItemCreate(**values))
    items.mark_open(item)
    return item


def _candidate(lost: Item, found: Item, score: int = 80) -> Match:
    candidate = Match(
        id=str(uuid4()),
        lost_item_id=lost.id,
        found_item_id=found.id,
        score=score,
        notify=score >= 60,
        reasons=[],
        conflicts=[],
        counterpart=items.to_public_view(found, found.found_place),
    )
    files.MATCHES[candidate.id] = candidate
    return candidate


@pytest.mark.parametrize(
    "data,mime", [(PNG, "image/png"), (JPEG, "image/jpeg"), (WEBP, "image/webp")]
)
def test_upload_and_read_preserve_bytes_and_actual_mime(data: bytes, mime: str) -> None:
    status, saved = _upload(data, mime)
    assert status == 201
    assert set(saved) == {"id", "mime", "created_at"}
    UUID(saved["id"])
    datetime.strptime(saved["created_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert saved["mime"] == mime  # 文件名一直是 .png，不能据此猜类型。

    status, headers, raw = _call("GET", f"/api/v1/files/{saved['id']}", OWNER)
    assert status == 200
    assert headers["content-type"] == mime
    assert raw == data
    assert files.get_own_file(saved["id"], OWNER.id).model_dump() == saved


@pytest.mark.parametrize(
    "data,mime",
    [
        (b"not an image", "image/png"),
        (b"MZ executable", "image/jpeg"),
        (b"GIF89a", "image/gif"),
        (b"<svg xmlns='http://www.w3.org/2000/svg'/>", "image/svg+xml"),
        (PNG, "image/jpeg"),
        (PNG, "application/octet-stream"),
        (b"", "image/png"),
        (PNG[:7], "image/png"),
        (b"RIFF\x04\x00\x00\x00WEBP", "image/webp"),
        (WEBP[:4] + b"\x00" * 4 + WEBP[8:], "image/webp"),
        (WEBP[:8] + b"WAVE" + WEBP[12:], "image/webp"),
    ],
)
def test_non_image_or_mismatched_upload_is_rejected(data: bytes, mime: str) -> None:
    _assert_invalid_file(*_upload(data, mime))


def test_size_limit_accepts_5mb_and_rejects_one_byte_more() -> None:
    data = PNG + b"\x00" * (files.MAX_IMAGE_BYTES - len(PNG))
    status, saved = _upload(data)
    assert status == 201
    assert files.read_image(saved["id"], OWNER) == data
    files.FILES.clear()
    _assert_invalid_file(*_upload(data + b"\x00"))


def test_other_user_cannot_read_image_but_admin_can() -> None:
    _, saved = _upload()
    status, _, raw = _call("GET", f"/api/v1/files/{saved['id']}", OTHER)
    assert status == 404
    assert json.loads(raw)["error"]["code"] == "not_found"
    status, headers, raw = _call("GET", f"/api/v1/files/{saved['id']}", ADMIN)
    assert status == 200
    assert headers["content-type"] == "image/png"
    assert raw == PNG


@pytest.mark.parametrize("user", [OWNER, OTHER, ADMIN])
def test_missing_file_is_not_found(user: User) -> None:
    status, _, raw = _call("GET", f"/api/v1/files/{uuid4()}", user)
    assert status == 404
    assert json.loads(raw)["error"]["code"] == "not_found"


def test_upload_and_download_require_login() -> None:
    status, body = _upload(user=None)
    assert status == 401
    assert body["error"]["code"] == "unauthenticated"
    assert not files.FILES
    status, _, raw = _call("GET", f"/api/v1/files/{uuid4()}", None)
    assert status == 401
    assert json.loads(raw)["error"]["code"] == "unauthenticated"


def test_request_id_must_be_a_uuid() -> None:
    status, body = _upload(request_id="not-a-uuid")
    assert status == 422
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["fields"][0]["name"] == "request_id"
    assert not files.FILES


def test_repeated_upload_returns_first_response_without_reading_again() -> None:
    request_id = str(uuid4())
    first_status, first = _upload(request_id=request_id)
    second_status, second = _upload(b"invalid retry", request_id=request_id)
    assert first_status == second_status == 201
    assert first == second
    assert len(files.FILES) == 1
    assert files.read_image(first["id"], OWNER) == PNG


def test_idempotency_is_scoped_to_user_and_does_not_cache_failures() -> None:
    request_id = str(uuid4())
    _assert_invalid_file(*_upload(b"invalid", request_id=request_id))
    status, first = _upload(request_id=request_id)
    other_status, second = _upload(user=OTHER, request_id=request_id)
    assert status == other_status == 201
    assert first["id"] != second["id"]
    assert len(files.FILES) == 2


def test_only_uploader_can_attach_file_to_item() -> None:
    _, saved = _upload()
    own = items.create_item(
        OWNER, ItemCreate(type="found", request_id=str(uuid4()), image_id=saved["id"])
    )
    assert own.image_id == saved["id"]
    for user in (OTHER, ADMIN):
        with pytest.raises(NotFound):
            items.create_item(
                user, ItemCreate(type="found", request_id=str(uuid4()), image_id=saved["id"])
            )
    assert len(items.ITEMS) == 1
    with pytest.raises(NotFound):
        files.get_own_file("missing", OWNER.id)


def test_lost_owner_can_read_image_in_own_candidate() -> None:
    _, saved = _upload()
    found = _item(OWNER, "found", saved["id"], found_place="library")
    lost = _item(OTHER, "lost", visited_places=["library"])
    _candidate(lost, found)
    status, headers, raw = _call("GET", f"/api/v1/files/{saved['id']}", OTHER)
    assert status == 200
    assert headers["content-type"] == "image/png"
    assert raw == PNG
    # 候选读取权限并不授予把对方图片挂在自己物品上的权限。
    with pytest.raises(NotFound):
        files.get_own_file(saved["id"], OTHER.id)


@pytest.mark.parametrize(
    "case", ["no_match", "low_score", "other_lost", "closed_lost", "expired_lost", "closed_found"]
)
def test_unavailable_or_foreign_candidate_does_not_grant_access(case: str) -> None:
    _, saved = _upload()
    found = _item(OWNER, "found", saved["id"], found_place="library")
    lost_owner = ADMIN if case == "other_lost" else OTHER
    occurred_on = datetime.now(timezone.utc).date()
    if case == "expired_lost":
        occurred_on -= timedelta(days=31)
    lost = _item(
        lost_owner, "lost", visited_places=["library"], occurred_on=occurred_on.isoformat()
    )
    if case != "no_match":
        _candidate(lost, found, score=39 if case == "low_score" else 80)
    if case == "closed_lost":
        items.mark_closed(lost)
    if case == "closed_found":
        items.mark_closed(found)
    status, _, raw = _call("GET", f"/api/v1/files/{saved['id']}", OTHER)
    assert status == 404
    assert json.loads(raw)["error"]["code"] == "not_found"


def test_sixth_candidate_does_not_grant_image_access() -> None:
    lost = _item(OTHER, "lost", visited_places=["library"])
    saved_files = []
    for score in range(40, 46):
        _, saved = _upload()
        saved_files.append(saved)
        found = _item(OWNER, "found", saved["id"], found_place="library")
        _candidate(lost, found, score)
    for index, saved in enumerate(saved_files):
        status, _, _ = _call("GET", f"/api/v1/files/{saved['id']}", OTHER)
        assert status == (404 if index == 0 else 200)


def test_upload_closes_file_and_bounds_read(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = []
    closed = []
    original_read = UploadFile.read
    original_close = UploadFile.close

    async def track_read(self: UploadFile, size: int = -1) -> bytes:
        reads.append(size)
        return await original_read(self, size)

    async def track_close(self: UploadFile) -> None:
        closed.append(self)
        await original_close(self)

    monkeypatch.setattr(UploadFile, "read", track_read)
    monkeypatch.setattr(UploadFile, "close", track_close)
    assert _upload()[0] == 201
    assert reads == [files.MAX_IMAGE_BYTES + 1]
    assert closed
