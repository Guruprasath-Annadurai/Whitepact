# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.client import RETRY_MAP, RetryClass, SovereignClient


def test_retry_audit_never_blind_for_shadow() -> None:
    client = SovereignClient()
    assert client.retry_class("shadow") == RetryClass.NEVER_BLINDLY_RETRY
    assert RETRY_MAP["gauntlet"] == RetryClass.NEVER_BLINDLY_RETRY
