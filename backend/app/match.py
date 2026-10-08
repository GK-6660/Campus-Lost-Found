"""候选。F 实现。自己查物品行，不调用 items.create_item / update_item。"""

from app import notify, scoring
from app.schemas import Item, Match, User

_CALLEES = (scoring.score_pair, notify.maybe_new_match)


def rematch_for_lost(lost_id: str) -> None:
    raise NotImplementedError(f"match.rematch_for_lost lost={lost_id} calls={len(_CALLEES)}")


def rematch_for_found(found_id: str) -> None:
    raise NotImplementedError(f"match.rematch_for_found found={found_id}")


def on_tags_confirmed(item: Item) -> None:
    if item.status != "open":
        return
    if item.type == "lost":
        rematch_for_lost(item.id)
    elif item.type == "found":
        rematch_for_found(item.id)


def list_matches(owner: User, item_id: str) -> list[Match]:
    from app.items import to_public_view

    raise NotImplementedError(
        f"match.list_matches owner={owner.id} item={item_id} view={to_public_view.__name__}"
    )


def suppress_found(found_id: str) -> None:
    raise NotImplementedError(f"match.suppress_found found={found_id}")
