"""E1。账号和重复提交。"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from app import auth, idempotency
from app.main import app
from fastapi.testclient import TestClient

REGISTER_BODY = {
    "student_no": "20240001",
    "nickname": "小明",
    "password": "password123",
    "request_id": "req-1",
}


@pytest.fixture()
def client() -> TestClient:
    """每个测试从空存储开始，互不串数据。"""
    auth._reset()
    idempotency._reset()
    return TestClient(app)


def _register(client: TestClient, **overrides: str) -> dict:
    body = {**REGISTER_BODY, **overrides}
    return client.post("/api/v1/auth/register", json=body)


def test_register_same_request_id_once(client: TestClient) -> None:
    """同一个提交编号注册两次，只有一个用户，返回里没有密码。"""
    first = _register(client)
    second = _register(client)

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    # 幂等重放：两次返回同一个用户
    assert first.json()["id"] == second.json()["id"]
    # 任何响应都不得出现密码（5.3）
    assert "password" not in first.json()
    assert "password" not in second.json()

    # 幂等键 = student_no（CON-05）：换成新 request_id 再注册同一学号，
    # 不是重放，而是学号冲突，拒绝且指出 student_no（API-AUTH-01）。
    # code 用 unknown_enum 是组长确认的口径（5.14 四个合法值里无「重复」，
    # 沿用 main.py 把其余情况归入 unknown_enum 的口径），改口径要先改这里。
    duplicate = _register(client, request_id="req-2")
    assert duplicate.status_code == 422, duplicate.text
    fields = duplicate.json()["error"]["fields"]
    assert fields[0]["name"] == "student_no"
    assert fields[0]["code"] == "unknown_enum"

    # 注册成功即登录：响应里带了会话 Cookie，能取到当前用户
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["id"] == first.json()["id"]
    assert me.json()["student_no"] == "20240001"


def test_login_failure_hides_which_field(client: TestClient) -> None:
    """学号或密码错误时登录失败，且不说明是哪一项错。"""
    assert _register(client).status_code == 201

    wrong_no = client.post(
        "/api/v1/auth/login",
        json={"student_no": "20999999", "password": "password123", "request_id": "req-no"},
    )
    wrong_pw = client.post(
        "/api/v1/auth/login",
        json={"student_no": "20240001", "password": "wrong-password", "request_id": "req-pw"},
    )

    assert wrong_no.status_code == 401, wrong_no.text
    assert wrong_pw.status_code == 401, wrong_pw.text
    # 两种失败的响应体必须完全一致，看不出哪一项错（API-AUTH-02）
    assert wrong_no.json() == wrong_pw.json()

    # 都正确才登录成功
    ok = client.post(
        "/api/v1/auth/login",
        json={"student_no": "20240001", "password": "password123", "request_id": "req-ok"},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["student_no"] == "20240001"


def test_register_role_is_user(client: TestClient) -> None:
    """注册结果 role 固定为 user，管理员只能来自种子数据（5.2）。"""
    response = _register(client)
    assert response.status_code == 201, response.text
    assert response.json()["role"] == "user"


def test_logout_clears_session(client: TestClient) -> None:
    """退出后删除 clf_session，再取当前用户要 401。"""
    assert _register(client).status_code == 201
    assert client.get("/api/v1/auth/me").status_code == 200

    logout = client.post("/api/v1/auth/logout")
    assert logout.status_code == 204, logout.text

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401, me.text
    assert me.json()["error"]["code"] == "unauthenticated"


def test_unauthenticated_takedown_rejected(client: TestClient) -> None:
    """没登录去下架，被拒绝（VER-01：401）。"""
    response = client.post(
        "/api/v1/admin/items/item-1/takedown",
        json={"version": 1, "request_id": "req-td", "reason": "违规"},
    )
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == "unauthenticated"


def test_login_replay_returns_first_result(client: TestClient) -> None:
    """同一学号同一 request_id 登录两次，只发一次会话逻辑，返回同一个用户（CON-05）。"""
    assert _register(client).status_code == 201
    body = {"student_no": "20240001", "password": "password123", "request_id": "req-login"}

    first = client.post("/api/v1/auth/login", json=body)
    second = client.post("/api/v1/auth/login", json=body)

    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json() == second.json()


# ---------- 以下为边界补充测试 ----------


def test_register_field_boundaries(client: TestClient) -> None:
    """学号 1–32、密码 8–64 的边界（RegisterBody 的 Field 约束）。"""
    # 学号恰好 32 字符：通过
    ok_no = _register(client, student_no="2" * 32)
    assert ok_no.status_code == 201, ok_no.text
    # 学号 33 字符：422
    long_no = _register(client, student_no="2" * 33, request_id="req-no33")
    assert long_no.status_code == 422, long_no.text
    assert long_no.json()["error"]["code"] == "validation_error"
    # 密码恰好 8 位：通过；7 位：422
    ok_pw = _register(client, student_no="20240002", password="p" * 8, request_id="req-pw8")
    assert ok_pw.status_code == 201, ok_pw.text
    short_pw = _register(client, student_no="20240003", password="p" * 7, request_id="req-pw7")
    assert short_pw.status_code == 422, short_pw.text
    # 密码恰好 64 位：通过；65 位：422
    ok_pw64 = _register(client, student_no="20240004", password="p" * 64, request_id="req-pw64")
    assert ok_pw64.status_code == 201, ok_pw64.text
    long_pw = _register(client, student_no="20240005", password="p" * 65, request_id="req-pw65")
    assert long_pw.status_code == 422, long_pw.text


def test_password_hash_is_salted() -> None:
    """同一密码注册两个用户，存的是不同的哈希，且哈希里没有明文（5.3）。"""
    auth._reset()
    idempotency._reset()
    try:
        auth.register("20240001", "甲", "password123")
        auth.register("20240002", "乙", "password123")
        h1 = auth._users_by_no["20240001"]["password_hash"]
        h2 = auth._users_by_no["20240002"]["password_hash"]
        # 加了随机盐：同一密码的两次哈希不同
        assert h1 != h2
        assert "password123" not in h1
        # 存的哈希能验证出原密码
        assert auth._hasher.verify("password123", h1)
        assert not auth._hasher.verify("password124", h1)
    finally:
        auth._reset()
        idempotency._reset()


def test_me_with_forged_session_rejected(client: TestClient) -> None:
    """拿伪造的会话 id 调 /auth/me，按未登录拒绝。"""
    assert _register(client).status_code == 201
    client.cookies.set("clf_session", "forged-session-id")
    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401, me.text
    assert me.json()["error"]["code"] == "unauthenticated"


def test_logout_without_cookie_rejected(client: TestClient) -> None:
    """没带 Cookie 就退出，按未登录拒绝（路由的 Unauthenticated 分支）。"""
    response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401, response.text


def test_double_logout(client: TestClient) -> None:
    """第一次退出 204；第二次会话已不存在且 Cookie 已清，按未登录拒绝。"""
    assert _register(client).status_code == 201
    assert client.post("/api/v1/auth/logout").status_code == 204
    assert client.post("/api/v1/auth/logout").status_code == 401


def test_two_users_sessions_isolated(client: TestClient) -> None:
    """两个用户各自登录，/auth/me 不会串人。"""
    assert _register(client).status_code == 201
    other = TestClient(app)
    body = {**REGISTER_BODY, "student_no": "20240002", "request_id": "req-b"}
    assert other.post("/api/v1/auth/register", json=body).status_code == 201

    me_a = client.get("/api/v1/auth/me")
    me_b = other.get("/api/v1/auth/me")
    assert me_a.status_code == 200 and me_b.status_code == 200
    assert me_a.json()["student_no"] == "20240001"
    assert me_b.json()["student_no"] == "20240002"
    assert me_a.json()["id"] != me_b.json()["id"]


def test_same_request_id_different_students(client: TestClient) -> None:
    """不同学号用同一个 request_id：互不影响，各建一个用户（CON-05 幂等范围是学号）。"""
    a = _register(client)
    b = _register(client, student_no="20240002", request_id="req-1")
    assert a.status_code == 201, a.text
    assert b.status_code == 201, b.text
    assert a.json()["id"] != b.json()["id"]


def test_concurrent_register_same_student_no_one_user() -> None:
    """并发注册同一学号：查重和写入在锁内，最终只有一个用户。"""
    auth._reset()
    idempotency._reset()
    try:
        failures: list[Exception] = []

        def attempt(_i: int) -> None:
            try:
                auth.register("20240001", "并发", "password123")
            except Exception as exc:  # noqa: BLE001 并发失败就是 ValidationError，这里全收
                failures.append(exc)

        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(attempt, range(8)))

        assert len(auth._users_by_no) == 1
        assert len(auth._users_by_id) == 1
        # 没抢到的都收到 ValidationError（学号已被注册），没有静默丢失
        assert len(failures) == 7
    finally:
        auth._reset()
        idempotency._reset()


def test_cookie_flags_and_value(client: TestClient) -> None:
    """Set-Cookie 满足 CON-03：HttpOnly、SameSite=lax、Path=/，值不是 user.id。"""
    response = _register(client)
    assert response.status_code == 201, response.text
    cookie = response.headers["set-cookie"]
    assert cookie.startswith("clf_session=")
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Path=/" in cookie
    value = cookie.split("clf_session=", 1)[1].split(";", 1)[0]
    assert value != response.json()["id"]
    # 随机会话 id（uuid4().hex 32 位），不是能猜出来的短值
    assert len(value) >= 32


def test_replay_does_not_reissue_cookie(client: TestClient) -> None:
    """幂等重放只返回第一次结果，不重发 Set-Cookie。

    这是组长确认的口径（对齐清单第 2 条选 A）：重放分支不走 _issue_session，
    响应丢失后重试的客户端要靠重新登录兜底。若以后改成重放补发 Cookie，
    先改路由再改这个测试。
    """
    assert _register(client).status_code == 201

    replay = _register(client)
    assert replay.status_code == 201
    assert "set-cookie" not in replay.headers

    login_body = {
        "student_no": "20240001",
        "password": "password123",
        "request_id": "req-login",
    }
    assert client.post("/api/v1/auth/login", json=login_body).status_code == 200
    login_replay = client.post("/api/v1/auth/login", json=login_body)
    assert login_replay.status_code == 200
    assert "set-cookie" not in login_replay.headers
