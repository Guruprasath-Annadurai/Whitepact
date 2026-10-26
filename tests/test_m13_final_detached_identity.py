# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unattested detached execution cannot be treated as contained."""

import pytest

from responsibleai.isolation import in_flight


@pytest.mark.asyncio
async def test_detached_execution_without_termination_proof_remains_unresolved(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(in_flight, "_DISTRIBUTED_REGISTRY_DIR", tmp_path)
    registry = in_flight.InFlightExecutionRegistry()
    await registry.register(
        execution_id="detached",
        organization_id="tenant",
        action_id="probe",
    )
    confirmed = await registry.terminate_in_flight(organization_id="tenant")
    assert confirmed == []
    assert registry.has_unresolved("tenant")
