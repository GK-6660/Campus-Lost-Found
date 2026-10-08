"""站内信。F 实现。"""

from app.schemas import Notification


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
    raise NotImplementedError(
        "notify.maybe_new_match "
        f"user={user_id} lost={lost_id} found={found_id} score={score} "
        f"hard_conflict={hard_conflict} subscribed={subscribed} title={title} body={body}"
    )


def found_returned(user_ids: list[str], lost_id: str, found_id: str) -> None:
    raise NotImplementedError(
        f"notify.found_returned users={user_ids} lost={lost_id} found={found_id}"
    )


def taken_down(owner_id: str, item_id: str) -> None:
    raise NotImplementedError(f"notify.taken_down owner={owner_id} item={item_id}")


def list_for(user_id: str) -> tuple[int, list[Notification]]:
    raise NotImplementedError(f"notify.list_for user={user_id}")


def mark_read(user_id: str, notification_id: str) -> Notification:
    raise NotImplementedError(f"notify.mark_read user={user_id} notification={notification_id}")
