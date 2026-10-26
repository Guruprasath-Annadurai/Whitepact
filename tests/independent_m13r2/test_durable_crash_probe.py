# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent signed-service interruption probe; not a physical crash test."""

import asyncio
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from tests.independent_m13r2.test_m13r_verified_containment import verified_input
from tests.test_m12fs_root_hardening import _configure_test_env  # noqa: F401

from responsibleai.db.engine import authority_containment_records
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.isolation.in_flight import InFlightExecutionRegistry


@pytest.mark.asyncio
async def test_verified_worker_interruption_requires_a_durable_incident(monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    monkeypatch.setattr(
        registry, "terminate_in_flight", AsyncMock(side_effect=asyncio.CancelledError())
    )
    with pytest.raises(asyncio.CancelledError):
        await service.execute_emergency_containment(actor, **kwargs)
    async with get_enterprise_engine().raw.connect() as conn:
        row = (
            await conn.execute(
                select(authority_containment_records).where(
                    authority_containment_records.c.org_id == kwargs["org_id"]
                )
            )
        ).first()
    assert row is not None, (
        "Lockdown committed before cancellation, but no durable incident/status exists for restart reconciliation"
    )
    assert row.status != "CONTAINED"
