"""候选。F 实现。自己查物品行，不调用 items.create_item / update_item。"""

from dataclasses import dataclass
from datetime import datetime, timezone
from threading import RLock
from uuid import uuid4

from app import notify, scoring
from app.errors import NotFound
from app.schemas import Item, Match, Score, User


@dataclass
class _Candidate:
    id: str
    score: Score

MATCHES: dict[tuple[str, str], _Candidate] = {}
_LOCK = RLock()


def _active(item: Item) -> bool:
    today = datetime.now(timezone.utc).date().isoformat()
    return item.status == "open" and (item.expires_on is None or item.expires_on >= today)


def _ready(item: Item) -> bool:
    if not _active(item):
        return False
    # 与 publish_item 一致，拾获先确认类别和颜色，不能提前使用识别结果。
    if item.type == "found":
        confirmed = {tag.key for tag in item.tags if tag.confirmed}
        return {"category", "color"} <= confirmed
    return True


def _confirmed_view(item: Item) -> Item:
    """未确认的标签不参与打分，不改动原物品。"""
    hidden = {tag.key: None for tag in item.tags if not tag.confirmed}
    return item.model_copy(update=hidden)


def _save_pair(lost: Item, found: Item) -> None:
    result = scoring.score_pair(_confirmed_view(lost), _confirmed_view(found))
    key = (lost.id, found.id)
    previous = MATCHES.get(key)
    MATCHES[key] = _Candidate(previous.id if previous else str(uuid4()), result)
    positive = [reason.text for reason in result.reasons if reason.points > 0]
    place = scoring.PLACE_NAMES.get(found.found_place, found.found_place or "地点未知")
    body = (
        f"拾获地点：{place}。匹配理由：{'；'.join(positive) or '暂无相同特征'}。"
        f"匹配分 {result.score}/100，仅用于排序。物品可能已经不在，请核实。"
    )
    notify.maybe_new_match(
        lost.owner_id,
        lost.id,
        found.id,
        result.score,
        result.hard_conflict,
        lost.subscribe_matches is True,
        "发现新的候选物品",
        body,
    )


def _rematch(item_id: str, expected_type: str) -> None:
    from app.items import ITEMS

    with _LOCK:
        item = ITEMS.get(item_id)
        if item is None:
            raise NotFound("没有这条物品")
        keep: set[tuple[str, str]] = set()
        if item.type == expected_type and _ready(item):
            for other in list(ITEMS.values()):
                if other.type == item.type or other.owner_id == item.owner_id or not _ready(other):
                    continue
                lost, found = (item, other) if item.type == "lost" else (other, item)
                _save_pair(lost, found)
                keep.add((lost.id, found.id))
        for key in list(MATCHES):
            if item_id in key and key not in keep:
                del MATCHES[key]


def rematch_for_lost(lost_id: str) -> None:
    _rematch(lost_id, "lost")


def rematch_for_found(found_id: str) -> None:
    _rematch(found_id, "found")


def on_tags_confirmed(item: Item) -> None:
    if item.status != "open":
        return
    if item.type == "lost":
        rematch_for_lost(item.id)
    elif item.type == "found":
        rematch_for_found(item.id)


def list_matches(owner: User, item_id: str) -> list[Match]:
    from app.items import ITEMS, to_public_view

    with _LOCK:
        item = ITEMS.get(item_id)
        if item is None or item.owner_id != owner.id:
            raise NotFound("没有这条物品")
        if not _ready(item):
            return []
        matches: list[Match] = []
        for (lost_id, found_id), candidate in MATCHES.items():
            if item_id not in (lost_id, found_id) or candidate.score.score < 40:
                continue
            lost, found = ITEMS.get(lost_id), ITEMS.get(found_id)
            if lost is None or found is None or not _ready(lost) or not _ready(found):
                continue
            if lost.owner_id == found.owner_id:
                continue
            counterpart = found if item.type == "lost" else lost
            result = candidate.score
            matches.append(
                Match(
                    id=candidate.id,
                    lost_item_id=lost_id,
                    found_item_id=found_id,
                    score=result.score,
                    score_max=result.score_max,
                    notify=(
                        result.score >= 60
                        and not result.hard_conflict
                        and lost.subscribe_matches is True
                    ),
                    reasons=result.reasons,
                    conflicts=result.conflicts,
                    counterpart=to_public_view(counterpart, found.found_place),
                )
            )
        matches.sort(key=lambda row: (-row.score, row.lost_item_id, row.found_item_id))
        return [row.model_copy(deep=True) for row in matches[:5]]


def suppress_found(found_id: str) -> None:
    """移除该拾获的所有候选，不改变物品状态，通知历史仍保留。"""
    with _LOCK:
        for key in list(MATCHES):
            if key[1] == found_id:
                del MATCHES[key]
