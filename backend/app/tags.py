"""物品上的类别和颜色。E 实现。模型写入走 write_model_tags，不写品牌。"""

from app.schemas import Item


def upsert_user_tags(item: Item, category: str | None, color: str | None) -> None:
    raise NotImplementedError(
        f"tags.upsert_user_tags item={item.id} category={category} color={color}"
    )


def confirm(item: Item) -> None:
    raise NotImplementedError(f"tags.confirm item={item.id}")


def write_model_tags(item: Item, category: str | None, color: str | None) -> None:
    raise NotImplementedError(
        f"tags.write_model_tags item={item.id} category={category} color={color}"
    )
