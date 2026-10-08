"""F。站内信只发一次。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_same_pair_notifies_once() -> None:
    """同一条失物和同一条拾获通知两次，仍然只有一条。"""
