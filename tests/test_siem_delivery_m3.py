# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SIEM HTTP delivery retries and idempotency (P1-06)."""

from __future__ import annotations

import httpx
import pytest
import respx

from responsibleai.audit.siem_delivery import SiemEventForwarder


@pytest.mark.asyncio
@respx.mock
async def test_siem_forwarder_retries_until_success() -> None:
    route = respx.post("https://siem.example/ingest").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200),
        ]
    )
    forwarder = SiemEventForwarder(max_retries=3, retry_delays=(0.0, 0.0))
    result = await forwarder.forward_ndjson(
        "https://siem.example/ingest",
        '{"schema":"whitepact.siem.audit.v1"}\n',
    )
    assert result.delivered is True
    assert result.attempts == 2
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_siem_forwarder_skips_duplicate_payload() -> None:
    route = respx.post("https://siem.example/ingest").mock(return_value=httpx.Response(200))
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    body = '{"correlation_id":"req-1"}\n'
    first = await forwarder.forward_ndjson("https://siem.example/ingest", body)
    second = await forwarder.forward_ndjson("https://siem.example/ingest", body)
    assert first.delivered and not first.duplicate_skipped
    assert second.duplicate_skipped
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_siem_forwarder_rejects_empty_destination() -> None:
    forwarder = SiemEventForwarder()
    result = await forwarder.forward_ndjson("  ", "line\n")
    assert not result.delivered
    assert result.error
