"""E2。涂黑图的上传和读取权限。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_non_image_upload_is_rejected() -> None:
    """上传的不是图片时，接口拒绝。"""


@pytest.mark.skip(reason="待实现")
def test_other_user_cannot_read_image() -> None:
    """别人不能读到这张图。"""
