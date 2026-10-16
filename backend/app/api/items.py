"""物品路由。E 实现。

CON-12：路由只做三件事——读会话、查幂等、调一个服务函数。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import require_user
from app.idempotency import replay_if_done, save
from app.items import close_item, create_item, get_for_viewer, list_mine, publish_item, update_item
from app.schemas import (
    Item,
    ItemCreate,
    ItemList,
    ItemPatch,
    ItemStatus,
    ItemType,
    User,
    VersionedWrite,
)

router = APIRouter(tags=["items"])


def _replayed(value: Any, user: User) -> Any:
    """幂等重放：返回第一次的结果（CON-05）。

    schemas.Item 的 owner_id 标了 exclude=True，所以只要 E1 的 save() 存的是
    model_dump() / jsonable_encoder() 这类 dict，owner_id 就没了；再把它当 Item
    校验会抛 ResponseValidationError（500），而不是返回第一次的结果。
    幂等键按用户划分，补回当前用户的 id 是安全的。
    """
    if isinstance(value, Item):
        return value
    if isinstance(value, dict):
        return Item.model_validate({**value, "owner_id": user.id})
    return value


@router.post("/items", status_code=201)
def post_items(body: ItemCreate, user: Annotated[User, Depends(require_user)]) -> Item:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return _replayed(replay, user)
    item = create_item(user, body)
    save(user.id, body.request_id, item)
    return item


@router.patch("/items/{item_id}")
def patch_item(
    item_id: str,
    body: ItemPatch,
    user: Annotated[User, Depends(require_user)],
) -> Item:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return _replayed(replay, user)
    item = update_item(user, item_id, body.version, body)
    save(user.id, body.request_id, item)
    return item


@router.post("/items/{item_id}/publish")
def post_publish(
    item_id: str,
    body: VersionedWrite,
    user: Annotated[User, Depends(require_user)],
) -> Item:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return _replayed(replay, user)
    item = publish_item(user, item_id, body.version)
    save(user.id, body.request_id, item)
    return item


@router.post("/items/{item_id}/close")
def post_close(
    item_id: str,
    body: VersionedWrite,
    user: Annotated[User, Depends(require_user)],
) -> Item:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return _replayed(replay, user)
    item = close_item(user, item_id, body.version)
    save(user.id, body.request_id, item)
    return item


@router.get("/items")
def get_items(
    user: Annotated[User, Depends(require_user)],
    item_type: Annotated[ItemType | None, Query(alias="type")] = None,
    status: ItemStatus | None = None,
) -> ItemList:
    return ItemList(items=list_mine(user, item_type, status))


@router.get("/items/{item_id}")
def get_item(item_id: str, user: Annotated[User, Depends(require_user)]) -> Item:
    return get_for_viewer(user, item_id)
