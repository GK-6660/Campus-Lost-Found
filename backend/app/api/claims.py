"""找回记录路由。G 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.claims import list_mine, submit_claim
from app.idempotency import replay_if_done, save
from app.schemas import Claim, ClaimCreate, ClaimList, User

router = APIRouter(tags=["claims"])


@router.post("/claims", status_code=201)
def post_claims(body: ClaimCreate, user: Annotated[User, Depends(require_user)]) -> Claim:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return replay
    claim = submit_claim(user, body.lost_item_id, body.found_item_id, body.result)
    save(user.id, body.request_id, claim)
    return claim


@router.get("/claims/mine")
def get_my_claims(user: Annotated[User, Depends(require_user)]) -> ClaimList:
    return ClaimList(items=list_mine(user))
