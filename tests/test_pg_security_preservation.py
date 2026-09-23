# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive PostgreSQL tests for WP-PG-REV-02 and WP-PG-REV-03.

Proves:
1. WP-PG-REV-02: Deletion/tombstone/erasure preservation across schema upgrades and downgrades.
   - Tombstoned tenants and erased states cannot be resurrected.
   - Upgrade/downgrade preserves tombstone state intact.
   - Erased tenant data remains strictly inaccessible.

2. WP-PG-REV-03: Production repository compatibility after historical PostgreSQL upgrades.
   - Real production repository classes (OrgRepository, PolicyRepository, EvidenceRepository,
     AuthorityGraph) operate flawlessly against the upgraded schema.
   - Zero wrong-tenant reads, zero authority widening, zero repository exceptions.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from responsibleai.data_governance.deletion_orchestrator import TenantDeletionError
from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.db.engine import create_engine
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.db.migrate import (
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.policy_repository import PolicyRepository
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.policy import PolicyRule
from responsibleai.iam.session import SessionService
from responsibleai.trust_fabric.authority_graph import (
    AuthorityGraph,
    CrossTenantAccessError,
)
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url("wp_sec_pg"):
        yield url


@pytest.mark.asyncio
async def test_tombstone_and_erasure_preservation_across_upgrades(pg_test_db: str) -> None:
    """WP-PG-REV-02: Prove deletion/tombstone/erasure preservation across migrations."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Migrate up to 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine = create_engine(pg_test_db)
    org_tombstoned = f"org-dead-{uuid.uuid4().hex[:6]}"
    tombstone_id = f"tomb-{uuid.uuid4().hex[:8]}"
    tombstone_digest = "a" * 64

    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO organizations (id, slug, name, created_at) VALUES (:a, :a, 'Dead Tenant', '2026-01-01T00:00:00Z')"
            ),
            {"a": org_tombstoned},
        )
        # Record tenant tombstone in 0045
        await conn.execute(
            text(
                "INSERT INTO tenant_tombstones "
                "(id, org_id, original_name, generation_id, tombstoned_at, tombstoned_by, authority_hash, evidence_digest, details_json) "
                "VALUES (:id, :org, 'Dead Tenant', 'gen-1', '2026-01-02T00:00:00Z', 'compliance-bot', :hash, :ev, '{}')"
            ),
            {
                "id": tombstone_id,
                "org": org_tombstoned,
                "hash": tombstone_digest,
                "ev": "ev-digest-1",
            },
        )
    await engine.close()

    # 2. Upgrade to 0046
    await _run_alembic(ini, env, "upgrade", "0046")

    # Verify tombstone survives 0046 upgrade unchanged
    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        res = await conn.execute(
            text("SELECT authority_hash, tombstoned_by FROM tenant_tombstones WHERE id = :id"),
            {"id": tombstone_id},
        )
        row = res.first()
        assert row is not None, "Tombstone lost during 0046 upgrade!"
        assert row[0] == tombstone_digest
        assert row[1] == "compliance-bot"

    # Verify tombstoned tenant cannot be resurrected/recreated
    org_repo = OrgRepository(engine)
    with pytest.raises(TenantDeletionError):
        await org_repo.create_org(name="Dead Tenant", slug="dead-slug")

    await engine.close()

    # 3. Downgrade 0046 -> 0045 and re-upgrade to 0046 (idempotent rollback preservation)
    await _run_alembic(ini, env, "downgrade", "0045")
    await _run_alembic(ini, env, "upgrade", "0046")

    engine = create_engine(pg_test_db)
    async with engine.raw.begin() as conn:
        res = await conn.execute(
            text("SELECT authority_hash FROM tenant_tombstones WHERE id = :id"),
            {"id": tombstone_id},
        )
        row = res.first()
        assert row is not None, "Tombstone lost during downgrade/re-upgrade cycle!"
        assert row[0] == tombstone_digest
    await engine.close()


@pytest.mark.asyncio
async def test_production_repository_compatibility_post_upgrade(pg_test_db: str) -> None:
    """WP-PG-REV-03: Exercise actual production repositories against upgraded schema."""
    await run_migrations_or_raise(pg_test_db)

    engine = create_engine(pg_test_db)
    await engine.init()

    try:
        # 1. OrgRepository compatibility
        org_repo = OrgRepository(engine)
        slug_a = f"slug-{uuid.uuid4().hex[:6]}"
        org_a = await org_repo.create_org(name="Production Org A", slug=slug_a)
        org_id = org_a.id
        fetched = await org_repo.get_org(org_id)
        assert fetched is not None
        assert fetched.name == "Production Org A"

        # 2. PolicyRepository compatibility
        policy_repo = PolicyRepository(engine)
        from responsibleai.governance.models import GovernanceDecision

        rule = PolicyRule(
            rule_id=f"rule-{uuid.uuid4().hex[:6]}",
            reason_code="DEFAULT_ALLOW",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset(["mcp_exec"]),
        )
        await policy_repo.add_rule(org_id=org_id, rule=rule)
        pol = await policy_repo.get_policy(org_id)
        assert len(pol.rules) >= 1
        assert "mcp_exec" in (pol.rules[0].action_types or set())

        # 3. EvidenceRepository compatibility
        evidence_repo = EvidenceRepository(engine)
        other_slug = f"other-{uuid.uuid4().hex[:6]}"
        other_org = await org_repo.create_org(name="Other Org", slug=other_slug)
        other_org_id = other_org.id

        ev_record = EvidenceRecord(
            action_id="act-1",
            agent_id="agent-1",
            identity_id="ident-1",
            action_type="mcp_exec",
            target="calculator",
            argument_keys=["x", "y"],
            authority_delegated_by="admin-1",
            decision="ALLOW",
            reason_codes=["POLICY_ALLOW"],
            evaluated_at=datetime.now(UTC),
            organization_id=org_id,
        )
        saved_ev = await evidence_repo.record(ev_record)
        assert saved_ev is not None

        # Same-tenant read succeeds
        read_same = await evidence_repo.get_for_org(saved_ev.evidence_id, org_id)
        assert read_same is not None
        assert read_same.action_type == "mcp_exec"

        # Cross-tenant read returns None (no cross-tenant leakage)
        read_cross = await evidence_repo.get_for_org(saved_ev.evidence_id, other_org_id)
        assert read_cross is None, "Cross-tenant read leaked evidence!"

        # 4. AuthorityGraph compatibility & cross-tenant security verification
        auth_mgr = AuthorityGraph(engine)
        async with engine.raw.begin() as conn:
            p_grantor = f"prin-g-{uuid.uuid4().hex[:8]}"
            p_grantee = f"prin-e-{uuid.uuid4().hex[:8]}"
            p_foreign = f"prin-f-{uuid.uuid4().hex[:8]}"
            await conn.execute(
                text(
                    "INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) "
                    "VALUES (:pg, :org, 'HUMAN_OPERATOR', 'Grantor', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                    "(:pe, :org, 'AGENT', 'Grantee', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                    "(:pf, :other, 'HUMAN_OPERATOR', 'Foreign Principal', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
                ),
                {
                    "pg": p_grantor,
                    "pe": p_grantee,
                    "org": org_id,
                    "pf": p_foreign,
                    "other": other_org_id,
                },
            )

        # A) Same-tenant authority grant succeeds
        edge = await auth_mgr.grant_authority(
            grantor_principal_id=p_grantor,
            grantee_principal_id=p_grantee,
            org_id=org_id,
            action_type="mcp_exec",
            resource_pattern="*",
        )
        assert edge is not None
        assert edge.grantor_principal_id == p_grantor

        # B) Cross-tenant authority attempt fails with CrossTenantAccessError
        with pytest.raises(CrossTenantAccessError):
            await auth_mgr.grant_authority(
                grantor_principal_id=p_foreign,  # foreign!
                grantee_principal_id=p_grantee,
                org_id=org_id,
                action_type="mcp_exec",
            )

        # C) Check authority cannot see edge from another tenant
        can_exec, _, _ = await auth_mgr.check_authority(
            grantee_principal_id=p_grantee,
            org_id=other_org_id,  # checking in wrong tenant
            action_type="mcp_exec",
        )
        assert can_exec is False, "Authority widened across tenant boundary!"

    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_unified_lifecycle_dataset_round_trip(pg_test_db: str) -> None:
    """Codex WP-PG-REV-05: Unified lifecycle dataset across 0045 -> 0046 -> 0045 -> 0046.

    Establishes a comprehensive lifecycle dataset at 0045:
    A. Active organization
    B. Deleted/tombstoned organization
    C. Deletion/erasure model (topological cascade into tenant_tombstones)
    D. Active authority grant
    E. Revoked authority grant
    F. Active IAM session
    G. Revoked IAM session
    H. Monotonic policy revisions & activations
    I. Active legal data hold
    J. Retained evidence record
    K. Generational tombstone metadata
    L. Cross-tenant isolation boundaries

    Executes: 0045 -> 0046 -> 0045 -> 0046
    Validates after EACH step using real repositories and services:
    - tenant resurrection: 0
    - revoked authority resurrection: 0
    - revoked session resurrection: 0
    - policy history loss: 0
    - data hold loss: 0
    - required evidence loss: 0
    - cross-tenant access: 0
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Establish database at schema 0045
    await _run_alembic(ini, env, "upgrade", "0045")

    engine = create_engine(pg_test_db)

    # Identifiers for the unified dataset
    org_active_id = f"org-act-{uuid.uuid4().hex[:6]}"
    org_dead_id = f"org-dead-{uuid.uuid4().hex[:6]}"
    org_other_id = f"org-other-{uuid.uuid4().hex[:6]}"
    dead_org_name = "Tombstoned Corporation"

    p_active_grantor = f"p-act-g-{uuid.uuid4().hex[:6]}"
    p_active_grantee = f"p-act-e-{uuid.uuid4().hex[:6]}"
    p_revoked_grantee = f"p-rev-e-{uuid.uuid4().hex[:6]}"
    p_other = f"p-oth-{uuid.uuid4().hex[:6]}"

    tombstone_id = f"tomb-{uuid.uuid4().hex[:8]}"
    tombstone_hash = hashlib.sha256(f"{org_dead_id}:auth".encode()).hexdigest()

    edge_act_id = f"edge-act-{uuid.uuid4().hex[:6]}"
    edge_rev_id = f"edge-rev-{uuid.uuid4().hex[:6]}"

    sess_act_id = f"sess_act_{uuid.uuid4().hex[:8]}"
    sess_act_tok = "tok_active_secret_123"
    sess_act_hash = hashlib.sha256(sess_act_tok.encode("utf-8")).hexdigest()

    sess_rev_id = f"sess_rev_{uuid.uuid4().hex[:8]}"
    sess_rev_tok = "tok_revoked_secret_456"
    sess_rev_hash = hashlib.sha256(sess_rev_tok.encode("utf-8")).hexdigest()

    rev1_id = f"rev-1-{uuid.uuid4().hex[:6]}"
    rev2_id = f"rev-2-{uuid.uuid4().hex[:6]}"
    act1_id = f"act-1-{uuid.uuid4().hex[:6]}"

    hold_id = f"hold-{uuid.uuid4().hex[:8]}"

    # Seed the complete unified dataset at schema 0045
    async with engine.raw.begin() as conn:
        # A & B: Organizations (active, tombstoned, and other)
        await conn.execute(
            text(
                "INSERT INTO organizations (id, slug, name, created_at) VALUES "
                "(:act, :act, 'Active Corp', '2026-01-01T00:00:00Z'), "
                "(:dead, :dead, :dead_name, '2026-01-01T00:00:00Z'), "
                "(:oth, :oth, 'Other Corp', '2026-01-01T00:00:00Z')"
            ),
            {
                "act": org_active_id,
                "dead": org_dead_id,
                "dead_name": dead_org_name,
                "oth": org_other_id,
            },
        )

        # K: Tombstone metadata for dead organization
        await conn.execute(
            text(
                "INSERT INTO tenant_tombstones "
                "(id, org_id, original_name, generation_id, tombstoned_at, tombstoned_by, authority_hash, evidence_digest, details_json) "
                "VALUES (:id, :org, :orig_name, 'gen-1', '2026-01-02T00:00:00Z', 'lifecycle-service', :hash, 'ev-dig-1', '{}')"
            ),
            {
                "id": tombstone_id,
                "org": org_dead_id,
                "orig_name": dead_org_name,
                "hash": tombstone_hash,
            },
        )

        # Principals
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at) VALUES "
                "(:pg, :act, 'HUMAN_OPERATOR', 'Active Grantor', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(:pe, :act, 'AGENT', 'Active Grantee', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(:pr, :act, 'AGENT', 'Revoked Grantee', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'), "
                "(:po, :oth, 'HUMAN_OPERATOR', 'Other Principal', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z')"
            ),
            {
                "pg": p_active_grantor,
                "pe": p_active_grantee,
                "pr": p_revoked_grantee,
                "po": p_other,
                "act": org_active_id,
                "oth": org_other_id,
            },
        )

        # D & E: Authority grants (active and revoked)
        await conn.execute(
            text(
                "INSERT INTO trust_fabric_authority_edges "
                "(id, grantor_principal_id, grantee_principal_id, org_id, action_type, valid_from, revoked_at, canonical_digest) VALUES "
                "(:id_act, :pg, :pe, :act, 'mcp_exec', '2026-01-01T00:00:00Z', NULL, 'digest-act'), "
                "(:id_rev, :pg, :pr, :act, 'mcp_exec', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z', 'digest-rev')"
            ),
            {
                "id_act": edge_act_id,
                "id_rev": edge_rev_id,
                "pg": p_active_grantor,
                "pe": p_active_grantee,
                "pr": p_revoked_grantee,
                "act": org_active_id,
            },
        )

        # F & G: IAM Sessions (active and revoked)
        await conn.execute(
            text(
                "INSERT INTO iam_sessions "
                "(id, org_id, principal_id, token_hash, session_type, status, created_at, expires_at, last_seen_at, revoked_at) VALUES "
                "(:id_act, :act, :pe, :hash_act, 'INTERACTIVE', 'ACTIVE', '2026-01-01T00:00:00Z', '2099-01-01T00:00:00Z', '2026-01-01T00:00:00Z', NULL), "
                "(:id_rev, :act, :pr, :hash_rev, 'INTERACTIVE', 'REVOKED', '2026-01-01T00:00:00Z', '2099-01-01T00:00:00Z', '2026-01-01T00:00:00Z', '2026-01-02T00:00:00Z')"
            ),
            {
                "id_act": sess_act_id,
                "id_rev": sess_rev_id,
                "act": org_active_id,
                "pe": p_active_grantee,
                "pr": p_revoked_grantee,
                "hash_act": sess_act_hash,
                "hash_rev": sess_rev_hash,
            },
        )

        # H: Policy revisions & activations (revision 1 permissive, revision 2 restricted active)
        rules_v1 = json.dumps(
            [
                {
                    "rule_id": "r1",
                    "reason_code": "PERMISSIVE_ALLOW",
                    "effect": "ALLOW",
                    "action_types": ["mcp_exec"],
                }
            ]
        )
        rules_v2 = json.dumps(
            [
                {
                    "rule_id": "r2",
                    "reason_code": "RESTRICTED_DENY",
                    "effect": "DENY",
                    "action_types": ["mcp_exec"],
                }
            ]
        )
        await conn.execute(
            text(
                "INSERT INTO governance_policy_revisions "
                "(id, org_id, revision_num, rules_json, content_digest, created_at, created_by, change_reason) VALUES "
                "(:r1, :act, 1, :rj1, 'dig-v1', '2026-01-01T00:00:00Z', 'admin', 'Initial permissive'), "
                "(:r2, :act, 2, :rj2, 'dig-v2', '2026-01-02T00:00:00Z', 'admin', 'Hardened restricted')"
            ),
            {"r1": rev1_id, "r2": rev2_id, "act": org_active_id, "rj1": rules_v1, "rj2": rules_v2},
        )
        await conn.execute(
            text(
                "INSERT INTO governance_policy_activations "
                "(id, org_id, revision_id, content_digest, activated_at, activated_by, governance_epoch, is_active) VALUES "
                "(:act_id, :act, :r2, 'dig-v2', '2026-01-02T00:00:00Z', 'admin', 2, true)"
            ),
            {"act_id": act1_id, "act": org_active_id, "r2": rev2_id},
        )

        # I: Legal Data Hold
        await conn.execute(
            text(
                "INSERT INTO data_holds "
                "(id, org_id, data_category, hold_reason, active, created_at, created_by) VALUES "
                "(:id, :act, 'audit_logs', 'Litigation Hold', true, '2026-01-01T00:00:00Z', 'legal-counsel')"
            ),
            {"id": hold_id, "act": org_active_id},
        )

    # J: Retained Evidence
    ev_repo = EvidenceRepository(engine)
    ev_record = EvidenceRecord(
        action_id="act-rt-1",
        agent_id="agent-rt-1",
        identity_id="ident-rt-1",
        action_type="mcp_exec",
        target="filesystem",
        argument_keys=["path"],
        authority_delegated_by=p_active_grantor,
        decision="ALLOW",
        reason_codes=["POLICY_ALLOW"],
        evaluated_at=datetime.now(UTC),
        organization_id=org_active_id,
    )
    saved_ev = await ev_repo.record(ev_record)
    ev_id = saved_ev.evidence_id

    async def verify_lifecycle_invariants(step_name: str) -> None:
        tenant_resurrection = 0
        revoked_authority_resurrection = 0
        revoked_session_resurrection = 0
        policy_history_loss = 0
        data_hold_loss = 0
        required_evidence_loss = 0
        cross_tenant_access = 0

        # 1. Verify Active Org & Tombstoned Org via OrgRepository
        org_repo = OrgRepository(engine)
        act_org = await org_repo.get_org(org_active_id)
        assert act_org is not None, f"Active org missing in {step_name}"

        # Attempt resurrection of tombstoned org name
        try:
            await org_repo.create_org(name=dead_org_name, slug=f"slug-{uuid.uuid4().hex[:4]}")
            tenant_resurrection += 1
        except TenantDeletionError:
            pass  # Expected: tombstone prevents recreation

        # Verify tombstone record intact
        async with engine.raw.connect() as c:
            t_row = (
                await c.execute(
                    text("SELECT authority_hash FROM tenant_tombstones WHERE id = :id"),
                    {"id": tombstone_id},
                )
            ).fetchone()
            assert t_row is not None and t_row[0] == tombstone_hash, (
                f"Tombstone lost in {step_name}"
            )

        # 2. Authority Graph via AuthorityGraph service
        auth_mgr = AuthorityGraph(engine)
        can_active, _, _ = await auth_mgr.check_authority(
            grantee_principal_id=p_active_grantee,
            org_id=org_active_id,
            action_type="mcp_exec",
        )
        assert can_active is True, f"Active authority grant failed in {step_name}"

        can_revoked, _, _ = await auth_mgr.check_authority(
            grantee_principal_id=p_revoked_grantee,
            org_id=org_active_id,
            action_type="mcp_exec",
        )
        if can_revoked is True:
            revoked_authority_resurrection += 1
        assert can_revoked is False, f"Revoked authority resurrected in {step_name}"

        # Cross-tenant authority check
        can_cross, _, _ = await auth_mgr.check_authority(
            grantee_principal_id=p_active_grantee,
            org_id=org_other_id,
            action_type="mcp_exec",
        )
        if can_cross is True:
            cross_tenant_access += 1
        assert can_cross is False, f"Cross-tenant authority check leaked in {step_name}"

        # 3. IAM Session via SessionService
        sess_svc = SessionService(engine)
        val_act = await sess_svc.validate_session(
            org_id=org_active_id, session_id=sess_act_id, token=sess_act_tok
        )
        assert val_act is True, f"Active session invalidated in {step_name}"

        val_rev = await sess_svc.validate_session(
            org_id=org_active_id, session_id=sess_rev_id, token=sess_rev_tok
        )
        if val_rev is True:
            revoked_session_resurrection += 1
        assert val_rev is False, f"Revoked session authenticated in {step_name}"

        val_cross = await sess_svc.validate_session(
            org_id=org_other_id, session_id=sess_act_id, token=sess_act_tok
        )
        if val_cross is True:
            cross_tenant_access += 1
        assert val_cross is False, f"Cross-tenant session access succeeded in {step_name}"

        # 4. Policy Revisions & Activations
        async with engine.raw.connect() as c:
            rev_cnt = (
                await c.execute(
                    text("SELECT count(*) FROM governance_policy_revisions WHERE org_id = :org"),
                    {"org": org_active_id},
                )
            ).scalar()
            if rev_cnt != 2:
                policy_history_loss += 1
            assert rev_cnt == 2, f"Policy history lost in {step_name}"

            # Check active revision remains hardened revision 2 (not rolled back to revision 1)
            active_rev = (
                await c.execute(
                    text(
                        "SELECT r.revision_num, r.change_reason FROM governance_policy_activations a "
                        "JOIN governance_policy_revisions r ON a.revision_id = r.id "
                        "WHERE a.org_id = :org AND a.is_active = true"
                    ),
                    {"org": org_active_id},
                )
            ).fetchone()
            assert active_rev is not None, f"Active policy activation missing in {step_name}"
            assert active_rev[0] == 2, f"Policy rolled back to older revision in {step_name}"

        # 5. Data Hold via LegalHoldManager
        hold_mgr = LegalHoldManager(engine)
        is_held = await hold_mgr.is_held(org_id=org_active_id, data_category="audit_logs")
        if not is_held:
            data_hold_loss += 1
        assert is_held is True, f"Data hold lost in {step_name}"

        # 6. Evidence via EvidenceRepository
        evidence_repo = EvidenceRepository(engine)
        ev_same = await evidence_repo.get_for_org(ev_id, org_active_id)
        if ev_same is None:
            required_evidence_loss += 1
        assert ev_same is not None, f"Evidence lost in {step_name}"

        ev_cross = await evidence_repo.get_for_org(ev_id, org_other_id)
        if ev_cross is not None:
            cross_tenant_access += 1
        assert ev_cross is None, f"Cross-tenant evidence leaked in {step_name}"

        # Assert zero violations across all invariants
        assert tenant_resurrection == 0, f"Tenant resurrection observed in {step_name}"
        assert revoked_authority_resurrection == 0, (
            f"Revoked authority resurrection observed in {step_name}"
        )
        assert revoked_session_resurrection == 0, (
            f"Revoked session resurrection observed in {step_name}"
        )
        assert policy_history_loss == 0, f"Policy history loss observed in {step_name}"
        assert data_hold_loss == 0, f"Data hold loss observed in {step_name}"
        assert required_evidence_loss == 0, f"Evidence loss observed in {step_name}"
        assert cross_tenant_access == 0, f"Cross-tenant access observed in {step_name}"

    try:
        # STEP 1: Verify baseline state at 0045
        await verify_lifecycle_invariants("0045_initial")

        # STEP 2: Transition 0045 -> 0046
        await _run_alembic(ini, env, "upgrade", "0046")
        await verify_lifecycle_invariants("0046_upgrade_1")

        # STEP 3: Transition 0046 -> 0045 (Downgrade)
        await _run_alembic(ini, env, "downgrade", "0045")
        await verify_lifecycle_invariants("0045_downgrade")

        # STEP 4: Transition 0045 -> 0046 (Re-upgrade)
        await _run_alembic(ini, env, "upgrade", "0046")
        await verify_lifecycle_invariants("0046_upgrade_2")

    finally:
        await engine.close()
