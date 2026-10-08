"""纯打分。F 实现。不读数据库，不写数据库。公式见 docs/软件设计说明书.md 第 5.7 节。"""

from app.schemas import Item, Score, ScorePart


def score_category(a: str | None, b: str | None) -> ScorePart:
    raise NotImplementedError(f"scoring.score_category {a} {b}")


def score_color(a: str | None, b: str | None) -> ScorePart:
    raise NotImplementedError(f"scoring.score_color {a} {b}")


def score_place(
    found_place: str | None,
    visited_places: list[str] | None,
    ordered: bool | None,
) -> ScorePart:
    raise NotImplementedError(
        f"scoring.score_place {found_place} {visited_places} ordered={ordered}"
    )


def score_time(lost_on: str | None, found_on: str | None) -> ScorePart:
    raise NotImplementedError(f"scoring.score_time {lost_on} {found_on}")


def score_brand(a: str | None, b: str | None) -> ScorePart:
    raise NotImplementedError(f"scoring.score_brand {a} {b}")


def score_keywords(lost_desc: str | None, found_desc: str | None) -> ScorePart:
    raise NotImplementedError(f"scoring.score_keywords {lost_desc} {found_desc}")


def score_pair(lost: Item, found: Item) -> Score:
    parts = [
        score_category(lost.category, found.category),
        score_color(lost.color, found.color),
        score_place(found.found_place, lost.visited_places, lost.places_ordered),
        score_time(lost.occurred_on, found.occurred_on),
        score_brand(lost.brand, found.brand),
        score_keywords(lost.description, found.description),
    ]
    raise NotImplementedError(f"scoring.score_pair parts={len(parts)}")
