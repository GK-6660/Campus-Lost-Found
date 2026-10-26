"""物品上的类别和颜色。E 实现。模型写入走 write_model_tags，不写品牌。"""

from app.schemas import Item, Tag

CATEGORY_VALUES = {
    "earphones",
    "campus_card",
    "keys",
    "bottle",
    "book",
    "clothing",
    "electronics",
    "umbrella",
    "bag",
    "other",
    "unknown",
}

COLOR_VALUES = {
    "black",
    "white",
    "gray",
    "red",
    "orange",
    "yellow",
    "green",
    "blue",
    "purple",
    "pink",
    "brown",
    "multi",
    "unknown",
}


def normalize(value: str | None, allowed: set[str]) -> str | None:
    if value is None:
        return None
    return value if value in allowed else "unknown"


def upsert_tag(item: Item, key: str, value: str | None, source: str, confirmed: bool) -> None:
    if value is None:
        return

    for tag in item.tags:
        if tag.key == key and tag.confirmed and source == "model":
            # 8.2 识别只写未确认的标签：用户已经确认过的值不得被模型覆盖。
            return

    if key == "category":
        value = normalize(value, CATEGORY_VALUES)
        item.category = value
    elif key == "color":
        value = normalize(value, COLOR_VALUES)
        item.color = value
    else:
        raise ValueError(f"Unknown tag key: {key}")

    if item.tags is None:
        item.tags = []

    for tag in item.tags:
        if tag.key == key:
            tag.value = value
            tag.source = source
            tag.confirmed = confirmed
            return

    item.tags.append(Tag(key=key, value=value, source=source, confirmed=confirmed))


def upsert_user_tags(item: Item, category: str | None, color: str | None) -> None:
    upsert_tag(item, "category", category, "user", True)
    upsert_tag(item, "color", color, "user", True)


def confirm(item: Item) -> None:
    if item.tags is None:
        return
    for tag in item.tags:
        if tag.key in ("category", "color"):
            tag.confirmed = True


def write_model_tags(item: Item, category: str | None, color: str | None) -> None:
    """识别只写未确认的标签（8.2）。已确认的值被 upsert_tag 挡掉，不写品牌。"""
    upsert_tag(item, "category", category, "model", False)
    upsert_tag(item, "color", color, "model", False)
