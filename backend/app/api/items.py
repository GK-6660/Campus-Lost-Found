"""物品路由。E 实现。"""

from typing import Annotated

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


@router.post("/items", status_code=201)
def post_items(body: ItemCreate, user: Annotated[User, Depends(require_user)]) -> Item:
    replay = replay_if_done(user.id, body.request_id)
    if replay is not None:
        return replay
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
        return replay
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
        return replay
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
        return replay
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
