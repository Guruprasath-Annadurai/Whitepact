# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Phase 5 Policy Revision History & Immutable Lineage."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import insert

from responsibleai.db.engine import DatabaseEngine, create_engine, organizations
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import (
    PolicyLifecycleManager,
    compute_policy_digest,
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
                name="Test Org Revision",
                created_at="2026-09-12T00:00:00Z",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_monotonic_revision_numbering(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)
    rules1 = [
        PolicyRule(rule_id="r1", reason_code="RC_DENY", effect=GovernanceDecision.DENY)
    ]
    rules2 = [
        PolicyRule(rule_id="r1", reason_code="RC_DENY", effect=GovernanceDecision.DENY),
        PolicyRule(rule_id="r2", reason_code="RC_ALLOW", effect=GovernanceDecision.ALLOW),
    ]

    rev1 = await mgr.create_revision(sample_org, rules1, "admin-1", "Initial revision")
    assert rev1.revision_num == 1
    assert rev1.created_by == "admin-1"
    assert rev1.change_reason == "Initial revision"

    rev2 = await mgr.create_revision(sample_org, rules2, "admin-2", "Added allow rule")
    assert rev2.revision_num == 2

    revisions = await mgr.get_revisions(sample_org)
    assert len(revisions) == 2
    assert [r.revision_num for r in revisions] == [1, 2]


@pytest.mark.asyncio
async def test_deterministic_content_digest(sqlite_engine: DatabaseEngine):
    rule_a = PolicyRule(
        rule_id="r1",
        reason_code="RC_TEST",
        effect=GovernanceDecision.ALLOW,
        risk_tiers=frozenset({RiskTier.HIGH, RiskTier.LOW}),
        action_types=frozenset({"read", "write"}),
        targets=frozenset({"db", "api"}),
    )
    rule_b = PolicyRule(
        rule_id="r1",
        reason_code="RC_TEST",
        effect=GovernanceDecision.ALLOW,
        risk_tiers=frozenset({RiskTier.LOW, RiskTier.HIGH}),  # different order in set
        action_types=frozenset({"write", "read"}),
        targets=frozenset({"api", "db"}),
    )

    digest_a = compute_policy_digest([rule_a])
    digest_b = compute_policy_digest([rule_b])
    assert digest_a == digest_b

    # Semantic mutation produces different digest
    rule_mutated = PolicyRule(
        rule_id="r1",
        reason_code="RC_TEST",
        effect=GovernanceDecision.DENY,  # changed effect
    )
    digest_mutated = compute_policy_digest([rule_mutated])
    assert digest_a != digest_mutated


@pytest.mark.asyncio
async def test_tenant_revision_isolation(sqlite_engine: DatabaseEngine, sample_org: str):
    mgr = PolicyLifecycleManager(sqlite_engine)
    other_org = f"org-other-{uuid.uuid4().hex[:8]}"
    async with sqlite_engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=other_org,
                name="Other Org",
                created_at="2026-09-12T00:00:00Z",
                slug=f"slug-{uuid.uuid4().hex[:8]}",
            )
        )

    rules = [PolicyRule(rule_id="r1", reason_code="RC1", effect=GovernanceDecision.ALLOW)]
    await mgr.create_revision(sample_org, rules, "admin-1", "Org 1 rev")
    await mgr.create_revision(other_org, rules, "admin-2", "Org 2 rev")

    revs_org1 = await mgr.get_revisions(sample_org)
    revs_org2 = await mgr.get_revisions(other_org)

    assert len(revs_org1) == 1
    assert len(revs_org2) == 1
    assert revs_org1[0].org_id == sample_org
    assert revs_org2[0].org_id == other_org
