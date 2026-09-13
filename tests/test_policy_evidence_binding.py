# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Policy-to-Evidence Binding and Historical Reconstruction."""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_evidence,
    organizations,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import (
    PolicyLifecycleManager,
)
from responsibleai.governance.risk import RiskTier


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture
async def sample_org(sqlite_engine: DatabaseEngine):
    org_id = f"org-{uuid.uuid4().hex[:8]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Test Org Evidence Binding",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
                created_at="2026-09-12T00:00:00Z",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_policy_evidence_binding_and_reconstruction(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)

    rules = [
        PolicyRule(
            rule_id="rule-exec-1",
            reason_code="RC_ALLOWED",
            effect=GovernanceDecision.ALLOW,
            risk_tiers=frozenset({RiskTier.LOW}),
            action_types=frozenset({"query"}),
            targets=frozenset({"analytics"}),
        )
    ]
    rev = await mgr.create_revision(sample_org, rules, "admin-1", "Initial analytical policy")
    act = await mgr.activate_revision(sample_org, rev.id, "admin-1")

    evidence_id = str(uuid.uuid4())
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(governance_evidence).values(
                id=evidence_id,
                org_id=sample_org,
                action_id="act-123",
                agent_id="agent-99",
                identity_id="user-456",
                action_type="query",
                decision="ALLOW",
                reason_codes=json.dumps(["RC_ALLOWED"]),
                evaluated_at="2026-09-12T00:00:00Z",
                recorded_at="2026-09-12T00:00:00Z",
                entry_hash="hash-123",
                target="analytics",
                authority_delegated_by="sovereign-root",
                policy_version=rev.revision_num,
                policy_digest=rev.content_digest,
                governance_epoch=act.governance_epoch,
            )
        )

    async with sqlite_engine.raw.connect() as conn:
        ev_row = (
            await conn.execute(
                select(governance_evidence).where(governance_evidence.c.id == evidence_id)
            )
        ).fetchone()

    assert ev_row is not None
    assert ev_row.policy_version == rev.revision_num
    assert ev_row.policy_digest == rev.content_digest

    historical_rev = await mgr.get_revision(sample_org, ev_row.policy_version)
    assert historical_rev is not None
    assert historical_rev.content_digest == ev_row.policy_digest
    assert len(historical_rev.rules) == 1
    assert historical_rev.rules[0].rule_id == "rule-exec-1"


@pytest.mark.asyncio
async def test_policy_drift_epoch_invalidation(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)

    rules1 = [PolicyRule(rule_id="r1", reason_code="RC1", effect=GovernanceDecision.ALLOW)]
    rev1 = await mgr.create_revision(sample_org, rules1, "admin", "Rev 1")
    act1 = await mgr.activate_revision(sample_org, rev1.id, "admin")
    epoch1 = act1.governance_epoch

    rules2 = [PolicyRule(rule_id="r2", reason_code="RC2", effect=GovernanceDecision.DENY)]
    rev2 = await mgr.create_revision(sample_org, rules2, "admin", "Rev 2")
    act2 = await mgr.activate_revision(sample_org, rev2.id, "admin")
    epoch2 = act2.governance_epoch

    assert epoch2 > epoch1
