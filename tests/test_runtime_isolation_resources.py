# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial resource limits and abuse tests for WhitePact Runtime Isolation."""

from __future__ import annotations

import asyncio

import pytest

from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend


@pytest.mark.asyncio
class TestResourceGovernance:
    async def test_output_clamping_limits_stdout(self):
        backend = LocalSubprocessBackend()
        # Request with 1024 bytes max output limit
        strict_limits = IsolationProfile(
            resources=ResourceLimits(max_output_bytes=256)
        )
        request = IsolatedExecutionRequest(
            action_id="act-clamp",
            organization_id="org-clamp",
            action_type="rai_trust_score",
            arguments={"agent_id": "test-agent"},
            profile=strict_limits,
        )
        outcome = await backend.execute(request)
        # Outcome stdout and stderr must be capped at max_output_bytes
        assert len(outcome.stdout.encode("utf-8")) <= 256
        assert len(outcome.stderr.encode("utf-8")) <= 256

    async def test_concurrent_isolated_executions_no_cross_pollution(self):
        backend = LocalSubprocessBackend()

        async def run_one(i: int):
            req = IsolatedExecutionRequest(
                action_id=f"act-concur-{i}",
                organization_id=f"org-{i}",
                action_type="rai_trust_score",
                arguments={"agent_id": f"agent-{i}"},
            )
            return await backend.execute(req)

        results = await asyncio.gather(*(run_one(i) for i in range(5)))
        assert len(results) == 5
        for i, res in enumerate(results):
            assert res.is_success
            assert res.action_id == f"act-concur-{i}"
