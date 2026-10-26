"""物品状态只在这个模块里改。E 实现。

CON-07：`items.status` 和 `items.version` 只有本模块能写。
现在还没有数据库层，先用进程内表 `ITEMS` 顶替；接上 PostgreSQL 后，
`lock` 要换成 `SELECT ... FOR UPDATE`（5.9 要求同一事务），其余函数名和语义不变。
其他模块可以遍历 `ITEMS` 读行，但不得直接改 `status` / `version`。
"""

import re
from datetime import date, datetime, timedelta, timezone
from itertools import count
from uuid import uuid4

from app import extract, match
from app.errors import (
    FieldError,
    Forbidden,
    InvalidState,
    NotFound,
    ValidationError,
    VersionConflict,
)
from app.files import get_own_file
from app.schemas import (
    Item,
    ItemCreate,
    ItemPatch,
    ItemStatus,
    ItemType,
    PublicItem,
    User,
)
from app.tags import confirm, upsert_user_tags

EXPIRE_DAYS = 30
MAX_VISITED_PLACES = 8
LIST_LIMIT = 100

# 物品表，键是 item.id。
ITEMS: dict[str, Item] = {}
# 写入顺序。只用来给 updated_at 相同的行做稳定排序，不是 Item 的字段。
_SEQ: dict[str, int] = {}
_SEQ_COUNTER = count(1)
_DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _labels_confirmed(item: Item) -> bool:
    by_key = {tag.key: tag for tag in item.tags}
    return all(key in by_key and by_key[key].confirmed for key in ("category", "color"))


def _now() -> str:
    """UTC 时刻，形如 2026-09-29T10:00:00Z（CON-09）。"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_day(value: str) -> date | None:
    """只认 YYYY-MM-DD，认不出来返回 None。"""
    if _DAY_RE.match(value) is None:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _expires_on(occurred_on: str) -> str | None:
    day = _parse_day(occurred_on)
    return None if day is None else (day + timedelta(days=EXPIRE_DAYS)).isoformat()


def _get(item_id: str) -> Item:
    item = ITEMS.get(item_id)
    if item is None:
        raise NotFound("没有这条物品")
    return item


def _authorize(owner: User, item: Item) -> None:
    if item.owner_id != owner.id:
        raise Forbidden("不是物品主人")


def _check_version(item: Item, version: int) -> None:
    if item.version != version:
        raise VersionConflict(item.version)


def _bump(item: Item) -> None:
    """一次成功的写操作：版本加 1，刷新 updated_at。"""
    item.version += 1
    item.updated_at = _now()


def _check_day_field(value: str | None, fields: list[FieldError]) -> None:
    """occurred_on 只允许 YYYY-MM-DD；错误代码只能用 5.14 里列的几个。"""
    if value is not None and _parse_day(value) is None:
        fields.append(FieldError("occurred_on", "unknown_enum"))


def _publish_fields(item: Item) -> list[FieldError]:
    """API-ITEM-03 的必填字段。缺什么就报什么，一次报全。"""
    fields: list[FieldError] = []
    if item.occurred_on is None:
        fields.append(FieldError("occurred_on", "required"))
    else:
        _check_day_field(item.occurred_on, fields)
    if item.day_part is None:
        fields.append(FieldError("day_part", "required"))
    if item.type == "lost":
        places = item.visited_places or []
        if not places:
            fields.append(FieldError("visited_places", "required"))
        elif len(places) > MAX_VISITED_PLACES:
            fields.append(FieldError("visited_places", "too_long"))
    elif item.found_place is None:
        fields.append(FieldError("found_place", "required"))
    return fields


def create_item(owner: User, payload: ItemCreate) -> Item:
    fields: list[FieldError] = []
    _check_day_field(payload.occurred_on, fields)
    if payload.visited_places is not None and len(payload.visited_places) > MAX_VISITED_PLACES:
        fields.append(FieldError("visited_places", "too_long"))
    if fields:
        raise ValidationError(fields)

    if payload.image_id is not None:
        get_own_file(payload.image_id, owner.id)

    is_lost = payload.type == "lost"
    now = _now()
    item = Item(
        id=str(uuid4()),
        owner_id=owner.id,
        type=payload.type,
        status="draft",
        version=1,
        category=None,
        color=None,
        brand=payload.brand,
        description=payload.description,
        occurred_on=payload.occurred_on,
        day_part=payload.day_part,
        # 失物才有路线；拾获只记一栋楼，其余必须为 null（5.5）。
        visited_places=list(payload.visited_places) if is_lost and payload.visited_places else None,
        places_ordered=(payload.places_ordered is not False) if is_lost else None,
        found_place=payload.found_place if not is_lost else None,
        place_note=payload.place_note if not is_lost else None,
        subscribe_matches=(payload.subscribe_matches is not False) if is_lost else None,
        image_id=payload.image_id,
        tags=[],
        job_id=None,
        expires_on=None,
        created_at=now,
        updated_at=now,
    )
    # 手填的类别和颜色写成用户标签：source=user、confirmed=true（API-ITEM-01）。
    upsert_user_tags(item, payload.category, payload.color)

    ITEMS[item.id] = item
    _SEQ[item.id] = next(_SEQ_COUNTER)
    return item


def update_item(owner: User, item_id: str, version: int, patch: ItemPatch) -> Item:
    item = _get(item_id)
    _authorize(owner, item)
    _check_version(item, version)
    is_lost = item.type == "lost"

    touched = patch.model_fields_set - {"version", "request_id", "confirm_tags"}
    if not touched and not patch.confirm_tags:
        raise ValidationError([FieldError("body", "required")], "至少要修改一项")

    # 已经开放且类别、颜色都确认之后，只允许改是否接收新候选通知（API-ITEM-02）。
    if item.status == "open" and _labels_confirmed(item):
        locked = sorted(touched - {"subscribe_matches"})
        if locked:
            raise InvalidState(f"物品已经开放且标签已确认，不能修改 {', '.join(locked)}")

    fields: list[FieldError] = []
    _check_day_field(patch.occurred_on if "occurred_on" in touched else None, fields)
    if is_lost and len(patch.visited_places or []) > MAX_VISITED_PLACES:
        fields.append(FieldError("visited_places", "too_long"))
    if fields:
        raise ValidationError(fields)

    if "image_id" in touched and patch.image_id is not None:
        get_own_file(patch.image_id, owner.id)

    if "category" in touched or "color" in touched:
        # 手改的类别和颜色记为用户标签；没传的那一项保持原样。
        upsert_user_tags(
            item,
            patch.category if "category" in touched else None,
            patch.color if "color" in touched else None,
        )

    if "brand" in touched:
        item.brand = patch.brand
    if "description" in touched:
        item.description = patch.description
    if "occurred_on" in touched:
        item.occurred_on = patch.occurred_on
    if "day_part" in touched:
        item.day_part = patch.day_part
    if "visited_places" in touched:
        places = list(patch.visited_places) if patch.visited_places else None
        item.visited_places = places if is_lost else None
    if "places_ordered" in touched:
        item.places_ordered = (patch.places_ordered is not False) if is_lost else None
    if "found_place" in touched:
        item.found_place = None if is_lost else patch.found_place
    if "place_note" in touched:
        item.place_note = None if is_lost else patch.place_note
    if "subscribe_matches" in touched:
        item.subscribe_matches = (patch.subscribe_matches is not False) if is_lost else None
    if "image_id" in touched:
        item.image_id = patch.image_id

    if patch.confirm_tags:
        confirm(item)

    _bump(item)

    # 说明书 8.3：开放中的物品确认标签后按类型重跑匹配。手改类别或颜色也算确认。
    tags_touched = bool({"category", "color"} & touched)
    if item.status == "open" and _labels_confirmed(item):
        if patch.confirm_tags or tags_touched:
            match.on_tags_confirmed(item)
    return item


def publish_item(owner: User, item_id: str, version: int) -> Item:
    item = _get(item_id)
    _authorize(owner, item)
    _check_version(item, version)

    fields = _publish_fields(item)
    if fields:
        raise ValidationError(fields)

    mark_open(item)

    # API-ITEM-03 的三个分支。有图且标签未确认时不匹配，先认图（8.2）。
    if item.type == "lost":
        match.rematch_for_lost(item.id)
    elif _labels_confirmed(item):
        match.rematch_for_found(item.id)
    elif item.image_id is not None:
        job = extract.enqueue(item)
        if job is not None:
            item.job_id = job.id
    return item


def close_item(owner: User, item_id: str, version: int) -> Item:
    item = _get(item_id)
    _authorize(owner, item)
    _check_version(item, version)

    if item.status != "open":
        raise InvalidState("只有已经开放的物品可以撤回")

    mark_closed(item)
    return item


def list_mine(owner: User, item_type: ItemType | None, status: ItemStatus | None) -> list[Item]:
    rows = [item for item in ITEMS.values() if item.owner_id == owner.id]
    if item_type is not None:
        rows = [item for item in rows if item.type == item_type]
    if status is not None:
        rows = [item for item in rows if item.status == status]
    rows.sort(key=lambda item: (item.updated_at, _SEQ.get(item.id, 0)), reverse=True)
    return [to_owner_view(item) for item in rows[:LIST_LIMIT]]


def get_for_viewer(viewer: User, item_id: str) -> Item:
    item = ITEMS.get(item_id)
    if item is None or (item.owner_id != viewer.id and viewer.role != "admin"):
        # 不是主人也不是管理员：按「不存在」处理，不说明它存在（API-ITEM-06）。
        raise NotFound("没有这条物品")
    return to_owner_view(item)


def lock(item_id: str, version: int) -> Item:
    """校验版本并返回这一行。接上数据库后这里要真的加行锁。"""
    item = _get(item_id)
    _check_version(item, version)
    return item


def mark_open(item: Item) -> None:
    item.status = "open"
    if item.occurred_on is not None:
        item.expires_on = _expires_on(item.occurred_on)
    _bump(item)


def mark_returned_pair(lost: Item, found: Item) -> None:
    for item in (lost, found):
        item.status = "returned"
        _bump(item)


def mark_closed(item: Item) -> None:
    item.status = "closed"
    _bump(item)


def to_owner_view(item: Item) -> Item:
    """主人视图。owner_id 在 schemas.Item 上标了 exclude=True，不会出现在响应里。"""
    return item.model_copy(deep=True)


def to_public_view(item: Item, place_code: str | None) -> PublicItem:
    """公开投影。只给一栋楼，不给失主的整条路线，也不给描述和品牌（5.6）。"""
    if place_code is None and item.type == "found":
        place_code = item.found_place
    return PublicItem(
        item_id=item.id,
        type=item.type,
        category=item.category,
        color=item.color,
        place_code=place_code,
        place_note=item.place_note,
        occurred_on=item.occurred_on,
        day_part=item.day_part,
        image_id=item.image_id,
    )
