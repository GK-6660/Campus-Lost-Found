"""站内信。与当前物品存储一致，暂用进程内表，重启后不保留。

接数据库时需把 new_match 去重迁移为用户、失物、拾获、类型的唯一约束。
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app.errors import NotFound
from app.schemas import Notification, NotificationType


@dataclass
class _Notice:
    user_id: str
    notification: Notification


_NOTIFICATIONS: dict[str, _Notice] = {}
_LOCK = RLock()


def _insert(
    user_id: str,
    kind: NotificationType,
    lost_id: str | None,
    found_id: str | None,
    title: str,
    body: str,
) -> None:
    created_at = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    notice = Notification(
        id=str(uuid4()),
        type=kind,
        read=False,
        lost_item_id=lost_id,
        found_item_id=found_id,
        title=title,
        body=body,
        created_at=created_at.replace("+00:00", "Z"),
    )
    _NOTIFICATIONS[notice.id] = _Notice(user_id, notice)


def maybe_new_match(
    user_id: str,
    lost_id: str,
    found_id: str,
    score: int,
    hard_conflict: bool,
    subscribed: bool,
    title: str,
    body: str,
) -> None:
    if score < 60 or hard_conflict or not subscribed:
        return
    # 检查与插入在同一锁内，防止同一进程的并发请求重复发信。
    with _LOCK:
        for row in _NOTIFICATIONS.values():
            notice = row.notification
            if (
                row.user_id == user_id
                and notice.type == "new_match"
                and notice.lost_item_id == lost_id
                and notice.found_item_id == found_id
            ):
                return
        _insert(user_id, "new_match", lost_id, found_id, title, body)


def _place(item_id: str) -> str:
    from app.items import ITEMS
    from app.scoring import PLACE_NAMES

    item = ITEMS.get(item_id)
    if item is None:
        return "地点未知"
    code = item.found_place
    if code is None and item.visited_places:
        code = item.visited_places[0]
    return PLACE_NAMES.get(code, code or "地点未知")


def found_returned(user_ids: list[str], lost_id: str, found_id: str) -> None:
    body = f"地点：{_place(found_id)}。该拾获已被标记为已找回，物品可能已经不在。"
    with _LOCK:
        for user_id in dict.fromkeys(user_ids):
            _insert(user_id, "found_returned", lost_id, found_id, "候选物品已找回", body)


def taken_down(owner_id: str, item_id: str) -> None:
    from app.items import ITEMS

    item = ITEMS.get(item_id)
    if item is None:
        raise NotFound("没有这条物品")
    body = f"地点：{_place(item_id)}。该物品已被管理员下架，物品可能已经不在。"
    with _LOCK:
        _insert(
            owner_id,
            "item_taken_down",
            item_id if item.type == "lost" else None,
            item_id if item.type == "found" else None,
            "物品已下架",
            body,
        )


def list_for(user_id: str) -> tuple[int, list[Notification]]:
    with _LOCK:
        rows = [
            row.notification for row in reversed(_NOTIFICATIONS.values()) if row.user_id == user_id
        ]
        unread_count = sum(not row.read for row in rows)
        rows.sort(key=lambda row: row.created_at, reverse=True)
        return unread_count, [row.model_copy(deep=True) for row in rows[:100]]


def mark_read(user_id: str, notification_id: str) -> Notification:
    with _LOCK:
        row = _NOTIFICATIONS.get(notification_id)
        if row is None or row.user_id != user_id:
            raise NotFound("没有这条通知")
        row.notification.read = True
        return row.notification.model_copy(deep=True)
