"""写操作的 request_id。E 实现。空壳一律视为还没做过。"""

from typing import Any


def replay_if_done(user_id: str, request_id: str) -> Any | None:
    raise NotImplementedError(f"idempotency.replay_if_done user={user_id} request_id={request_id}")


def save(user_id: str, request_id: str, response: object) -> None:
    raise NotImplementedError(
        f"idempotency.save user={user_id} request_id={request_id} "
        f"response={type(response).__name__}"
    )
