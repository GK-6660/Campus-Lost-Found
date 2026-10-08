"""F。打分。不访问数据库。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_same_category_has_reason() -> None:
    """类别相同有类别分，并有一句理由。"""


@pytest.mark.skip(reason="待实现")
def test_time_score_is_zero_after_seven_days() -> None:
    """相差不少于 7 天时，时间分是 0。"""
