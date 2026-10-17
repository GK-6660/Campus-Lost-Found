"""F。打分。不访问数据库。"""

from app.schemas import Item
from app.scoring import (
    score_brand,
    score_category,
    score_color,
    score_keywords,
    score_pair,
    score_place,
    score_time,
)


def test_same_category_has_reason() -> None:
    """类别相同有类别分，并有一句理由。"""
    result = score_category("earphones", "earphones")

    assert result.points == 40
    assert "类别相同" in result.text
    assert "耳机" in result.text
    assert result.conflict is False


def test_time_score_is_zero_after_seven_days() -> None:
    """相差不少于 7 天时，时间分是 0。"""
    assert score_time("2026-10-01", "2026-10-08").points == 0
    assert score_time("2026-10-01", "2026-10-20").points == 0


def test_different_known_categories_are_a_hard_conflict() -> None:
    result = score_category("earphones", "book")

    assert result.points == -30
    assert result.conflict is True
    assert "类别冲突" in result.text


def test_black_and_gray_are_in_the_same_color_group() -> None:
    assert score_color("black", "gray").points == 20


def test_found_place_in_visited_places_gets_full_points() -> None:
    result = score_place("library", ["library", "gym"], ordered=True)

    assert result.points == 15
    assert "图书馆" in result.text


def test_found_before_lost_halves_the_time_points() -> None:
    result = score_time("2026-10-02", "2026-10-01")

    assert result.points == 6
    assert "时间顺序存疑" in result.text


def test_brand_comparison_ignores_case_and_outer_spaces() -> None:
    assert score_brand(" Apple ", "apple").points == 5


def test_shared_description_keywords_receive_points() -> None:
    result = score_keywords("黑色书包，挂着小熊", "捡到黑色书包")

    assert 1 <= result.points <= 5
    assert "共同关键词" in result.text


def make_item(item_type: str) -> Item:
    """构造测试物品，双方默认信息相同且没有照片。"""
    return Item(
        id=f"{item_type}-item",
        owner_id=f"{item_type}-owner",
        type=item_type,
        status="open",
        version=1,
        category="earphones",
        color="black",
        brand="Apple",
        description="黑色耳机",
        occurred_on="2026-10-01",
        day_part=None,
        visited_places=["library"],
        places_ordered=False,
        found_place="library",
        place_note=None,
        subscribe_matches=True,
        image_id=None,
        tags=[],
        job_id=None,
        expires_on=None,
        created_at="2026-10-01T00:00:00Z",
        updated_at="2026-10-01T00:00:00Z",
    )


def test_score_pair_totals_all_parts_without_photo() -> None:
    """六项完全匹配得 100 分，没有照片也正常计分。"""
    lost = make_item("lost")
    found = make_item("found")

    result = score_pair(lost, found)

    assert result.score == 100
    assert result.score_max == 100
    assert result.hard_conflict is False
    assert result.conflicts == []
    assert len(result.reasons) == 6
    assert sum(reason.points for reason in result.reasons) == 100
    assert all(reason.text for reason in result.reasons)


def test_score_pair_includes_category_penalty() -> None:
    """类别冲突时扣 30 分，保留其他分项并标记硬冲突。"""
    lost = make_item("lost")
    found = make_item("found")
    found.category = "book"

    result = score_pair(lost, found)

    # 类别 -30，颜色 20，地点 15，时间 15，品牌 5，关键词 5。
    assert result.score == 30
    assert result.hard_conflict is True
    assert len(result.conflicts) == 1
    assert result.conflicts[0].code == "category"
    assert result.conflicts[0].points == -30

    all_reasons = result.reasons + result.conflicts
    assert sum(reason.points for reason in all_reasons) == result.score


def test_unknown_category_does_not_score_or_conflict() -> None:
    """类别未知时不加分，也不产生硬冲突。"""
    for left, right in [
        (None, "earphones"),
        ("earphones", None),
        ("unknown", "earphones"),
        ("unknown", "unknown"),
        (None, None),
    ]:
        result = score_category(left, right)

        assert result.points == 0
        assert result.conflict is False


def test_unknown_color_does_not_score() -> None:
    """颜色未知时，即使双方都未知，也不加分。"""
    for left, right in [
        (None, "black"),
        ("black", None),
        ("unknown", "black"),
        ("unknown", "unknown"),
        (None, None),
    ]:
        result = score_color(left, right)

        assert result.points == 0
        assert result.conflict is False


def test_missing_or_different_place_does_not_conflict() -> None:
    """缺少坐标时，不同楼或缺地点得 0 分，不产生硬冲突。"""
    for found_place, visited_places in [
        ("gym", ["library"]),
        ("library", []),
        ("library", None),
        (None, ["library"]),
    ]:
        result = score_place(found_place, visited_places, ordered=False)

        assert result.points == 0
        assert result.conflict is False


def test_missing_or_different_brand_does_not_score() -> None:
    """品牌缺失、空白或不同时不加分。"""
    for left, right in [
        (None, "Apple"),
        ("Apple", None),
        ("", ""),
        (" ", " "),
        ("Apple", "Huawei"),
    ]:
        assert score_brand(left, right).points == 0


def test_missing_or_unrelated_description_does_not_score() -> None:
    """描述缺失或没有共同片段时不加分。"""
    for left, right in [
        (None, "黑色耳机"),
        ("黑色耳机", None),
        ("", ""),
        (" ", " "),
        ("耳机", "课本"),
    ]:
        assert score_keywords(left, right).points == 0


def test_score_pair_with_missing_information() -> None:
    """六项信息都缺失时，总分为 0，无硬冲突。"""
    lost = make_item("lost")
    found = make_item("found")

    for item in (lost, found):
        item.category = None
        item.color = None
        item.brand = None
        item.description = None
        item.occurred_on = None
        item.visited_places = None
        item.found_place = None

    result = score_pair(lost, found)

    assert result.score == 0
    assert result.hard_conflict is False
    assert result.conflicts == []
    assert len(result.reasons) == 6
    assert all(reason.text for reason in result.reasons)


def test_category_conflict_can_produce_negative_total() -> None:
    """类别冲突且其他项为 0 时，保留 -30 分。"""
    lost = make_item("lost")
    found = make_item("found")

    lost.category = "earphones"
    found.category = "book"

    for item in (lost, found):
        item.color = None
        item.brand = None
        item.description = None
        item.occurred_on = None
        item.visited_places = None
        item.found_place = None

    result = score_pair(lost, found)

    assert result.score == -30
    assert result.hard_conflict is True
    assert len(result.conflicts) == 1
    assert result.conflicts[0].code == "category"
    assert result.conflicts[0].points == -30


def test_partial_match_uses_correct_item_fields() -> None:
    """失物提供路线，拾获提供楼栋；地点不符不影响其他分项。"""
    lost = make_item("lost")
    found = make_item("found")

    lost.found_place = None
    lost.visited_places = ["library"]
    found.visited_places = None
    found.found_place = "gym"
    found.color = "white"
    found.brand = "Huawei"
    found.description = None
    found.occurred_on = "2026-10-08"

    result = score_pair(lost, found)
    points = {reason.code: reason.points for reason in result.reasons}

    assert points == {
        "category": 40,
        "color": 0,
        "place": 0,
        "time": 0,
        "brand": 0,
        "keyword": 0,
    }
    assert result.score == 40
    assert result.hard_conflict is False
    assert result.conflicts == []


def test_time_score_follows_linear_formula() -> None:
    """正向相差 1～6 天，按线性公式计算后取整。"""
    expected_points = [13, 11, 9, 6, 4, 2]

    for day, expected in enumerate(expected_points, start=2):
        result = score_time("2026-10-01", f"2026-10-{day:02d}")

        assert result.points == expected


def test_reverse_time_after_seven_days() -> None:
    """提前至少 7 天，时间分仍为 0，并提示顺序存疑。"""
    result = score_time("2026-10-08", "2026-10-01")

    assert result.points == 0
    assert "时间顺序存疑" in result.text


def test_missing_or_invalid_date_scores_zero() -> None:
    """缺日期或日期无效时，不加分并给出说明。"""
    for lost_on, found_on in [
        (None, "2026-10-01"),
        ("2026-10-01", None),
        ("bad-date", "2026-10-01"),
        ("2026-02-30", "2026-10-01"),
    ]:
        result = score_time(lost_on, found_on)

        assert result.points == 0
        assert result.text


def test_keywords_have_exact_partial_and_full_scores() -> None:
    """锁定当前关键词算法的部分重合与完全重合得分。"""
    # 两边各有三个词，共同词为 alpha：round(5 / 3) = 2。
    partial = score_keywords("alpha beta gamma", "alpha delta epsilon")
    assert partial.points == 2

    full = score_keywords("黑色耳机", "黑色耳机")
    assert full.points == 5