"""G。下架权限。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_normal_user_cannot_takedown() -> None:
    """普通用户下架会被拒绝。"""
