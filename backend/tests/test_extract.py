"""G。没有模型密钥时仍能手填后匹配。"""

import pytest


@pytest.mark.skip(reason="待实现")
def test_missing_model_key_fails_job_for_manual_entry() -> None:
    """没有密钥时识别任务直接失败，不阻止手填。"""
