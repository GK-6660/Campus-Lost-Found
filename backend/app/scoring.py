"""纯打分。F 实现。不读数据库，不写数据库。公式见 docs/软件设计说明书.md 第 5.7 节。"""

import re
from datetime import date

from app.schemas import Item, Reason, Score, ScorePart

CATEGORY_NAMES = {
    "earphones": "耳机",
    "campus_card": "校园卡",
    "keys": "钥匙",
    "bottle": "水杯",
    "book": "书",
    "clothing": "衣物",
    "electronics": "电子产品",
    "umbrella": "伞",
    "bag": "包",
    "other": "其他",
}

COLOR_NAMES = {
    "black": "黑色",
    "white": "白色",
    "gray": "灰色",
    "red": "红色",
    "orange": "橙色",
    "yellow": "黄色",
    "green": "绿色",
    "blue": "蓝色",
    "purple": "紫色",
    "pink": "粉色",
    "brown": "棕色",
    "multi": "多色",
}

PLACE_NAMES = {
    "library": "图书馆",
    "teaching_a": "教学楼 A",
    "teaching_b": "教学楼 B",
    "canteen_1": "一食堂",
    "canteen_2": "二食堂",
    "dorm": "宿舍区",
    "gym": "体育馆",
    "admin_building": "行政楼",
}


def _known(value: str | None) -> bool:
    return bool(value and value != "unknown")


def score_category(a: str | None, b: str | None) -> ScorePart:
    if not _known(a) or not _known(b):
        return ScorePart(points=0, text="类别信息不足")
    if a == b:
        name = CATEGORY_NAMES.get(a, a)
        return ScorePart(points=40, text=f"类别相同：{name}")
    left = CATEGORY_NAMES.get(a, a)
    right = CATEGORY_NAMES.get(b, b)
    return ScorePart(points=-30, text=f"类别冲突：{left}与{right}", conflict=True)


def score_color(a: str | None, b: str | None) -> ScorePart:
    if not _known(a) or not _known(b):
        return ScorePart(points=0, text="颜色信息不足")
    same_group = {a, b} <= {"black", "gray"}
    if a == b or same_group:
        if a == b:
            text = f"颜色相同：{COLOR_NAMES.get(a, a)}"
        else:
            text = "颜色接近：黑色与灰色"
        return ScorePart(points=20, text=text)
    return ScorePart(points=0, text="颜色不同")


def score_place(
    found_place: str | None,
    visited_places: list[str] | None,
    ordered: bool | None,
) -> ScorePart:
    del ordered  # 缺少坐标时，是否有序不影响设计书规定的回退规则。
    if not found_place or not visited_places:
        return ScorePart(points=0, text="地点信息不足")
    if found_place in visited_places:
        name = PLACE_NAMES.get(found_place, found_place)
        return ScorePart(points=15, text=f"出现在你去过的{name}")
    return ScorePart(points=0, text="拾获地点不在所选楼栋中")


def score_time(lost_on: str | None, found_on: str | None) -> ScorePart:
    if not lost_on or not found_on:
        return ScorePart(points=0, text="日期信息不足")
    try:
        lost_date = date.fromisoformat(lost_on)
        found_date = date.fromisoformat(found_on)
    except ValueError:
        return ScorePart(points=0, text="日期格式无效")

    delta = abs((found_date - lost_date).days)
    points = 15 * max(0, 1 - delta / 7)
    suspicious = found_date < lost_date
    if suspicious:
        points *= 0.5

    rounded_points = round(points)
    text = f"日期相差 {delta} 天"
    if suspicious:
        text += "，时间顺序存疑"
    return ScorePart(points=rounded_points, text=text)


def score_brand(a: str | None, b: str | None) -> ScorePart:
    left = a.strip() if a else ""
    right = b.strip() if b else ""
    if not left or not right:
        return ScorePart(points=0, text="品牌信息不足")
    if left.casefold() == right.casefold():
        return ScorePart(points=5, text=f"品牌相同：{left}")
    return ScorePart(points=0, text="品牌不同")


def score_keywords(lost_desc: str | None, found_desc: str | None) -> ScorePart:
    lost_tokens = _description_tokens(lost_desc)
    found_tokens = _description_tokens(found_desc)
    if not lost_tokens or not found_tokens:
        return ScorePart(points=0, text="描述信息不足")

    common = lost_tokens & found_tokens
    if not common:
        return ScorePart(points=0, text="描述中没有共同关键词")

    ratio = len(common) / min(len(lost_tokens), len(found_tokens))
    points = max(1, round(5 * ratio))
    examples = "、".join(sorted(common)[:3])
    return ScorePart(points=points, text=f"共同关键词：{examples}")


def _description_tokens(description: str | None) -> set[str]:
    """提取英文单词、数字和中文二字片段，供确定性的关键词比较使用。"""
    if not description:
        return set()

    normalized = description.casefold()
    tokens = set(re.findall(r"[a-z0-9]+", normalized))
    for chunk in re.findall(r"[\u4e00-\u9fff]+", normalized):
        if len(chunk) == 1:
            tokens.add(chunk)
        else:
            tokens.update(chunk[index : index + 2] for index in range(len(chunk) - 1))
    return tokens


def score_pair(lost: Item, found: Item) -> Score:
    scored_parts = [
        ("category", score_category(lost.category, found.category)),
        ("color", score_color(lost.color, found.color)),
        (
            "place",
            score_place(found.found_place, lost.visited_places, lost.places_ordered),
        ),
        ("time", score_time(lost.occurred_on, found.occurred_on)),
        ("brand", score_brand(lost.brand, found.brand)),
        ("keyword", score_keywords(lost.description, found.description)),
    ]
    reasons = [
        Reason(code=code, points=part.points, text=part.text)
        for code, part in scored_parts
        if not part.conflict
    ]
    conflicts = [
        Reason(code=code, points=part.points, text=part.text)
        for code, part in scored_parts
        if part.conflict
    ]
    return Score(
        score=sum(part.points for _, part in scored_parts),
        reasons=reasons,
        conflicts=conflicts,
        hard_conflict=bool(conflicts),
    )
