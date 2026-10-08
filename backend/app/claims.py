"""失主标记已找回或没找到。G 实现。"""

from app.items import lock, mark_returned_pair
from app.match import suppress_found
from app.notify import found_returned
from app.schemas import Claim, ClaimResult, User

_CALLEES = (lock, mark_returned_pair, suppress_found, found_returned)


def submit_claim(user: User, lost_id: str, found_id: str, result: ClaimResult) -> Claim:
    raise NotImplementedError(
        f"claims.submit_claim user={user.id} lost={lost_id} found={found_id} "
        f"result={result} calls={len(_CALLEES)}"
    )


def list_mine(user: User) -> list[Claim]:
    raise NotImplementedError(f"claims.list_mine user={user.id}")
