"""站内信路由。F 实现。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import require_user
from app.notify import list_for, mark_read
from app.schemas import Notification, NotificationList, User

router = APIRouter(tags=["notifications"])


@router.get("/notifications")
def get_notifications(user: Annotated[User, Depends(require_user)]) -> NotificationList:
    unread_count, items = list_for(user.id)
    return NotificationList(unread_count=unread_count, items=items)


@router.post("/notifications/{notification_id}/read")
def post_read(
    notification_id: str,
    user: Annotated[User, Depends(require_user)],
) -> Notification:
    return mark_read(user.id, notification_id)
