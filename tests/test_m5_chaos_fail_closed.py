# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 chaos / dependency-failure fail-closed slices (UNKNOWN, no blind replay)."""

from __future__ import annotations

import httpx
import pytest
import respx

from responsibleai.audit.siem_delivery import SiemEventForwarder


@pytest.mark.asyncio
@respx.mock
async def test_siem_delivery_exhausted_retries_fail_closed() -> None:
    respx.post("https://siem.example/ingest").mock(return_value=httpx.Response(503))
    forwarder = SiemEventForwarder(max_retries=2, retry_delays=(0.0, 0.0))
    result = await forwarder.forward_ndjson(
        "https://siem.example/ingest",
        '{"schema":"whitepact.siem.audit.v1"}\n',
    )
    assert not result.delivered
    assert result.attempts == 2
    assert result.error


def test_m5_chaos_regression_modules_importable() -> None:
    """Ensure fail-closed matrices remain importable for campaign subprocess runs."""
    import tests.test_mcp_ws2_failclosed_dependency_matrix  # noqa: F401
    import tests.test_mcp_ws2_upstream_reconciliation  # noqa: F401
    import tests.test_mcp_ws2_worker_retry_matrix  # noqa: F401
