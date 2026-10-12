# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
from __future__ import annotations

import httpx
import pytest
from sdk.python.rai_client.governance import GovernanceRuntimeClient


@pytest.mark.asyncio
async def test_existing_evidence_list_and_attestation_contract() -> None:
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.url.query))
        assert request.headers["Authorization"] == "Bearer synthetic"
        return httpx.Response(200, json={"evidence": []})

    client = GovernanceRuntimeClient("synthetic", transport=httpx.MockTransport(handler))
    assert await client.list_evidence(limit=25) == {"evidence": []}
    await client.get_attestation("ev-1")
    assert seen == [
        ("GET", "/api/governance/evidence", b"limit=25"),
        ("GET", "/api/governance/evidence/ev-1/attestation", b""),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("limit", [0, 201, True, 1.5])
async def test_evidence_limit_rejected_before_network(limit) -> None:
    with pytest.raises(ValueError, match="Evidence limit"):
        await GovernanceRuntimeClient("synthetic").list_evidence(limit=limit)
