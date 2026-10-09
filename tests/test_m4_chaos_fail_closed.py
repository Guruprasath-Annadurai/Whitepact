# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 chaos / dependency failure — governance must fail closed."""

from __future__ import annotations

import pytest

from responsibleai.audit.siem_delivery import SiemEventForwarder
from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
)


def test_restore_not_ready_blocks_traffic() -> None:
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    assert gate.is_admitted() is False
    with pytest.raises(RestoreQuarantineError):
        gate.assert_traffic_admitted()


@pytest.mark.asyncio
async def test_siem_delivery_outage_does_not_fake_success() -> None:
    """SIEM forward failure is isolated to observability path."""
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    result = await forwarder.forward_ndjson("http://127.0.0.1:9", '{"event":"x"}\n')
    assert result.delivered is False
    assert result.attempts >= 1
