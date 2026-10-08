"""举报和下架路由。G 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_admin_user, require_user
from app.idempotency import replay_if_done, save
from app.reports import create, list_open, takedown
from app.schemas import Item, Report, ReportCreate, ReportList, TakedownBody, User

router = APIRouter(tags=["reports"])


@router.post("/reports", status_code=201)
def post_reports(body: ReportCreate, user: Annotated[User, Depends(require_user)]) -> Report:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return replay
    report = create(user, body.item_id, body.reason)
    save(user.id, body.request_id, report)
    return report


@router.get("/admin/reports")
def get_admin_reports(admin: Annotated[User, Depends(require_admin_user)]) -> ReportList:
    return ReportList(items=list_open(admin))


@router.post("/admin/items/{item_id}/takedown")
def post_takedown(
    item_id: str,
    body: TakedownBody,
    admin: Annotated[User, Depends(require_admin_user)],
) -> Item:
    replay = replay_if_done(admin.id, body.request_id)
    if replay is not None:
        return replay
    item = takedown(admin, item_id, body.version, body.reason)
    save(admin.id, body.request_id, item)
    return item
