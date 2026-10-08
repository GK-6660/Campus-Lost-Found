"""E1。账号和重复提交。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_register_same_request_id_once() -> None:
    """同一个提交编号注册两次，只有一个用户，返回里没有密码。"""


@pytest.mark.skip(reason="待实现")
def test_login_failure_hides_which_field() -> None:
    """学号或密码错误时登录失败，且不说明是哪一项错。"""
