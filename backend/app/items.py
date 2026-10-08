"""物品状态只在这个模块里改。E 实现。"""

from app import extract, match
from app.errors import Forbidden
from app.files import get_own_file
from app.schemas import Item, ItemCreate, ItemPatch, ItemStatus, ItemType, PublicItem, User
from app.tags import confirm, upsert_user_tags


def _labels_confirmed(item: Item) -> bool:
    by_key = {tag.key: tag for tag in item.tags}
    return all(key in by_key and by_key[key].confirmed for key in ("category", "color"))


def create_item(owner: User, payload: ItemCreate) -> Item:
    if payload.image_id is not None:
        get_own_file(payload.image_id, owner.id)
    raise NotImplementedError(
        f"items.create_item owner={owner.id} type={payload.type} next={upsert_user_tags.__name__}"
    )


def update_item(owner: User, item_id: str, version: int, patch: ItemPatch) -> Item:
    item = lock(item_id, version)
    if item.owner_id != owner.id:
        raise Forbidden("不是物品主人")
    if patch.confirm_tags:
        confirm(item)
        match.on_tags_confirmed(item)
    raise NotImplementedError(f"items.update_item item={item_id}")


def publish_item(owner: User, item_id: str, version: int) -> Item:
    item = lock(item_id, version)
    if item.owner_id != owner.id:
        raise Forbidden("不是物品主人")
    mark_open(item)
    if item.type == "lost":
        match.rematch_for_lost(item.id)
    elif _labels_confirmed(item):
        match.rematch_for_found(item.id)
    elif item.image_id is not None:
        extract.enqueue(item)
    return item


def close_item(owner: User, item_id: str, version: int) -> Item:
    item = lock(item_id, version)
    if item.owner_id != owner.id:
        raise Forbidden("不是物品主人")
    mark_closed(item)
    return item


def list_mine(owner: User, item_type: ItemType | None, status: ItemStatus | None) -> list[Item]:
    raise NotImplementedError(f"items.list_mine owner={owner.id} type={item_type} status={status}")


def get_for_viewer(viewer: User, item_id: str) -> Item:
    raise NotImplementedError(f"items.get_for_viewer viewer={viewer.id} item={item_id}")


def lock(item_id: str, version: int) -> Item:
    raise NotImplementedError(f"items.lock item={item_id} version={version}")


def mark_open(item: Item) -> None:
    raise NotImplementedError(f"items.mark_open item={item.id}")


def mark_returned_pair(lost: Item, found: Item) -> None:
    raise NotImplementedError(f"items.mark_returned_pair lost={lost.id} found={found.id}")


def mark_closed(item: Item) -> None:
    raise NotImplementedError(f"items.mark_closed item={item.id}")


def to_owner_view(item: Item) -> Item:
    return item


def to_public_view(item: Item, place_code: str | None) -> PublicItem:
    raise NotImplementedError(f"items.to_public_view item={item.id} place={place_code}")
