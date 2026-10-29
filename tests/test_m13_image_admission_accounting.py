# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real durable Option A accounting with an injected image-admission fault."""

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationExecutionUncertainError,
    IsolationRuntimeUnavailableError,
)
from responsibleai.isolation.image_admission import ImageAdmissionError
from responsibleai.mcp.governance_integration import resume_approval
from tests.test_m13_execution_isolation_recovery import (
    durable_case as durable_case,
)
from tests.test_m13_execution_isolation_recovery import (
    recovery_engine as recovery_engine,
)
from tests.test_m13_execution_isolation_recovery import (
    restore_boundary as restore_boundary,
)
from tests.test_m13_execution_isolation_recovery import (
    resume_case as resume_case,
)
from tests.test_m13_execution_isolation_recovery import (
    snapshot,
)


@pytest.mark.asyncio
async def test_unapproved_image_blocks_before_nonce_without_restoring_approval(
    durable_case, monkeypatch
):
    case = durable_case
    case.fault = "Actual backend preflight rejects mutable image before nonce admission"
    backend = DockerContainerBackend(image_name="mutable:tag")
    monkeypatch.setattr(backend, "is_available", lambda: True)
    case.broker.preflight.side_effect = backend.preflight
    with pytest.raises(IsolationRuntimeUnavailableError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 0
    assert [r["status"] for r in state["outcomes"]] == ["BLOCKED"]
    case.broker.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_image_failure_after_admission_preserves_nonce_and_unknown(durable_case):
    case = durable_case
    case.fault = "Image admission refuses after successful probe and committed execution nonce"
    case.possible_execution = True
    case.broker.execute.side_effect = ImageAdmissionError(
        "registry unavailable after successful preflight"
    )
    with pytest.raises(IsolationExecutionUncertainError):
        await resume_approval(case.id, **case.kwargs)
    state = await snapshot(case)
    assert state["approval"] == "CONSUMED" and state["nonce_count"] == 1
    assert [r["status"] for r in state["outcomes"]] == ["UNKNOWN"]


async def journal_for(case):
    from responsibleai.db.containment_repository import ContainmentRepository

    journal = ContainmentRepository(case.engine)
    await journal.begin(
        execution_id="image-unit",
        organization_id=case.kwargs["org_id"],
        owner_generation="unit",
        backend_identity="unit-daemon",
        authorization_id="unit-auth",
        action_digest="ab" * 32,
        admission_epoch=0,
        expected_container_name="unit-container",
    )
    await journal.acknowledge("image-unit", "unit", "c" * 64)
    return journal


@pytest.mark.asyncio
async def test_image_binding_is_durable_and_names_the_acknowledged_owner(durable_case):
    import json

    from sqlalchemy import select

    from responsibleai.db.engine import enterprise_security_audit

    journal = await journal_for(durable_case)
    await journal.record_image_binding(
        "image-unit", "unit", "c" * 64, "sha256:" + "a" * 64, "sha256:" + "a" * 64
    )
    async with durable_case.engine.raw.connect() as conn:
        rows = (
            (
                await conn.execute(
                    select(enterprise_security_audit).where(
                        enterprise_security_audit.c.action == "isolation.image.bound"
                    )
                )
            )
            .mappings()
            .all()
        )
    assert len(rows) == 1 and rows[0]["org_id"] == durable_case.kwargs["org_id"]
    receipt = json.loads(rows[0]["metadata_json"])
    assert receipt["image_id"] == "sha256:" + "a" * 64 and receipt["container_id"] == "c" * 64
    assert receipt["start_sent"] is False and receipt["publisher_signature_verified"] is False


@pytest.mark.asyncio
async def test_failed_binding_write_does_not_claim_persisted_evidence(durable_case, monkeypatch):
    from unittest.mock import AsyncMock

    from sqlalchemy import select

    from responsibleai.db.engine import enterprise_security_audit
    from responsibleai.enterprise.audit import EnterpriseAuditLog

    journal = await journal_for(durable_case)
    monkeypatch.setattr(
        EnterpriseAuditLog, "record", AsyncMock(side_effect=OSError("injected write outage"))
    )
    with pytest.raises(OSError):
        await journal.record_image_binding(
            "image-unit", "unit", "c" * 64, "sha256:" + "a" * 64, "sha256:" + "a" * 64
        )
    async with durable_case.engine.raw.connect() as conn:
        rows = (
            await conn.execute(
                select(enterprise_security_audit).where(
                    enterprise_security_audit.c.action == "isolation.image.bound"
                )
            )
        ).all()
    assert rows == []
