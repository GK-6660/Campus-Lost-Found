"""举报和下架。G 实现。"""

from app.auth import require_admin
from app.items import lock, mark_closed
from app.notify import taken_down
from app.schemas import Item, Report, User


def create(user: User, item_id: str, reason: str) -> Report:
    raise NotImplementedError(f"reports.create user={user.id} item={item_id} reason={reason}")


def list_open(admin: User) -> list[Report]:
    require_admin(admin)
    raise NotImplementedError(f"reports.list_open admin={admin.id}")


def _close_open_reports(item_id: str, reason: str) -> None:
    raise NotImplementedError(f"reports.takedown item={item_id} reason={reason}")


def takedown(admin: User, item_id: str, version: int, reason: str) -> Item:
    require_admin(admin)
    item = lock(item_id, version)
    mark_closed(item)
    _close_open_reports(item_id, reason)
    taken_down(item.owner_id, item.id)
    return item
