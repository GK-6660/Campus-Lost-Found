"""候选路由。F 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.match import list_matches
from app.schemas import MatchList, User

router = APIRouter(tags=["matches"])


@router.get("/items/{item_id}/matches")
def get_matches(item_id: str, user: Annotated[User, Depends(require_user)]) -> MatchList:
    return MatchList(item_id=item_id, matches=list_matches(user, item_id))
