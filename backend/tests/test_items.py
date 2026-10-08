"""E2。物品的创建、发布和版本。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_publish_missing_place_is_rejected() -> None:
    """失物发布时没有楼，接口拒绝。"""


@pytest.mark.skip(reason="待实现")
def test_update_with_stale_version_conflicts() -> None:
    """用旧版本号修改，接口要求刷新。"""
