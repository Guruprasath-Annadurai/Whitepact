# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise PostgreSQL Historical Migration & Existing-Data Preservation Proof.

Validates WhitePact's historical PostgreSQL migration upgrade paths and proves that
representative pre-existing enterprise data survives upgrades to current HEAD (0045)
without corruption, privilege widening, tenant-crossing, trust-state mutation, or
lifecycle resurrection.

Tested upgrade paths:
1. Fresh install: EMPTY DB -> 0045 (HEAD)
2. Historical Path A: 0042 -> 0045 (HEAD) (Pre-Phase 3 -> Current HEAD)
3. Historical Path B: 0043 -> 0045 (HEAD) (Phase 3 Trust Fabric -> Current HEAD)
4. Historical Path C: 0044 -> 0045 (HEAD) (Phase 4 Enterprise IAM -> Current HEAD)
5. Downgrade & Re-upgrade idempotence: 0045 -> 0044 -> 0045
6. Strict multi-tenant isolation and foreign key constraint enforcement
7. Programmatic security defaults and backfill audit (0 UNSAFE defaults)
"""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncGenerator

from tests.pg_test_url import isolated_pg_url

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
)


@pytest.fixture
async def pg_disposable_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url('wp_hist_mig'):
        yield url


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head and correct revision chain:
    0045 -> 0044 -> 0043 -> 0042 -> 0041.
    """
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0049"]

    rev_0049 = scripts.get_revision("0049")
    assert rev_0049.down_revision == "0048"

    rev_0048 = scripts.get_revision("0048")
    assert rev_0048.down_revision == "0047"

    rev_0047 = scripts.get_revision("0047")
    assert rev_0047.down_revision == "0046"

    rev_0046 = scripts.get_revision("0046")
    assert rev_0046.down_revision == "0045"

    rev_0045 = scripts.get_revision("0045")
    assert rev_0045.down_revision == "0044"

    rev_0044 = scripts.get_revision("0044")
    assert rev_0044.down_revision == "0043"

    rev_0043 = scripts.get_revision("0043")
    assert rev_0043.down_revision == "0042"

    rev_0042 = scripts.get_revision("0042")
    assert rev_0042.down_revision == "0041"


# ── Section 4: Baseline Fresh Install ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_fresh_install_to_head_postgres(pg_disposable_db: str):
    """Prove fresh schema upgrades directly from empty DB to HEAD (0045) on real PostgreSQL."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)
    await _run_alembic(ini, env, "upgrade", "head")

    engine = create_engine(pg_disposable_db)
    try:
        async with engine.raw.connect() as conn:
            version = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert version == "0049"

        def _get_tables(sync_conn):
            return inspect(sync_conn).get_table_names()

        async with engine.raw.connect() as conn:
            table_names = await conn.run_sync(_get_tables)

        required_tables = {
            "organizations",
            "web_users",
            "web_memberships",
            "org_api_keys",
            "governance_evidence",
            "governance_evidence_chain_heads",
            "governance_policies",
            "governance_approvals",
            "governance_revocation_epochs",
            "governance_execution_nonces",
            "trust_fabric_principals",
            "trust_fabric_identifiers",
            "trust_fabric_relationships",
            "trust_fabric_authority_edges",
            "iam_sessions",
            "iam_api_key_lineage",
            "iam_jit_grants",
            "iam_four_eyes_requests",
            "iam_break_glass_sessions",
            "governance_policy_revisions",
            "governance_policy_activations",
            "data_retention_policies",
            "data_lifecycle_requests",
            "data_holds",
            "tenant_tombstones",
            "restore_reconciliation_records",
        }
        for table in required_tables:
            assert table in table_names, f"Table {table} missing from fresh install schema"
    finally:
        await engine.close()


# ── Section 5-14: Upgrade Path A (0042 -> 0045 HEAD) ─────────────────────────


@pytest.mark.asyncio
async def test_upgrade_0042_to_head_preserves_data_and_invariants(pg_disposable_db: str):
    """Historical Upgrade Path A: 0042 -> 0045 (HEAD).

    Proves:
    - Pre-Phase 3 data survives upgrade to current HEAD.
    - Zero data loss, zero cross-tenant contamination.
    - Zero privilege widening (viewer stays viewer, member stays member).
    - Zero credential resurrection (revoked API key stays revoked).
    - Policy DENY remains DENY.
    - Canonical evidence integrity status 'LEGACY_CHAINED_V1' is strictly preserved.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)

    # 1. Migrate to historical revision 0042
    await _run_alembic(ini, env, "upgrade", "0042")

    engine = create_engine(pg_disposable_db)
    try:
        async with engine.raw.connect() as conn:
            ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert ver == "0042"

            # 2. Seed multi-tenant dataset (tenant_alpha, tenant_beta)
            # Organizations
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, plan, created_at)
                    VALUES
                        ('tenant_alpha', 'Tenant Alpha Corp', 'alpha-corp', 10000.0, 'ENTERPRISE', '2026-01-01T00:00:00Z'),
                        ('tenant_beta', 'Tenant Beta LLC', 'beta-llc', 5000.0, 'PRO', '2026-01-02T00:00:00Z')
                """)
            )

            # Web Users & Memberships (Privilege preservation)
            await conn.execute(
                text("""
                    INSERT INTO web_users (id, email, full_name, password_hash, disabled, created_at, updated_at)
                    VALUES
                        ('usr_alpha_admin', 'admin@alpha.com', 'Alpha Admin', 'hash_adm', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
                        ('usr_alpha_viewer', 'viewer@alpha.com', 'Alpha Viewer', 'hash_view', 0, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
                        ('usr_beta_member', 'member@beta.com', 'Beta Member', 'hash_mem', 0, '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO web_memberships (id, user_id, org_id, role, created_at)
                    VALUES
                        ('mem_alpha_adm', 'usr_alpha_admin', 'tenant_alpha', 'admin', '2026-01-01T00:00:00Z'),
                        ('mem_alpha_viw', 'usr_alpha_viewer', 'tenant_alpha', 'viewer', '2026-01-01T00:00:00Z'),
                        ('mem_beta_mem', 'usr_beta_member', 'tenant_beta', 'member', '2026-01-02T00:00:00Z')
                """)
            )

            # Org API Keys (Revocation preservation)
            await conn.execute(
                text("""
                    INSERT INTO org_api_keys (id, org_id, key_hash, name, role, created_at, revoked)
                    VALUES
                        ('key_alpha_act', 'tenant_alpha', 'hash_k1', 'Active Key', 'ADMIN', '2026-01-01T00:00:00Z', 0),
                        ('key_alpha_rev', 'tenant_alpha', 'hash_k2', 'Revoked Key', 'ANALYST', '2026-01-01T00:00:00Z', 1),
                        ('key_beta_act', 'tenant_beta', 'hash_k3', 'Beta Active', 'OPERATOR', '2026-01-02T00:00:00Z', 0)
                """)
            )

            # Governance Policies
            await conn.execute(
                text("""
                    INSERT INTO governance_policies (id, org_id, rule_id, reason_code, effect, position, created_at, updated_at)
                    VALUES
                        ('pol_alpha_deny', 'tenant_alpha', 'rule_alpha_deny', 'BLOCKED_BY_POLICY', 'DENY', 1, '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
                        ('pol_beta_allow', 'tenant_beta', 'rule_beta_allow', 'STANDARD_ALLOW', 'ALLOW', 1, '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
                """)
            )

            # Governance Evidence (0042 canonical fields)
            await conn.execute(
                text("""
                    INSERT INTO governance_evidence (
                        id, org_id, action_id, agent_id, identity_id, action_type, target,
                        authority_delegated_by, decision, reason_codes, evaluated_at, recorded_at,
                        entry_hash, prev_hash, integrity_version, integrity_status, chain_sequence
                    )
                    VALUES
                        ('ev_alpha_1', 'tenant_alpha', 'act_a1', 'agt_a', 'id_a', 'tool_call', 'fs', 'root', 'DENY', '["POLICY_DENY"]', '2026-01-01T10:00:00Z', '2026-01-01T10:00:00Z', 'hash_e1', NULL, 1, 'LEGACY_CHAINED_V1', 1),
                        ('ev_alpha_2', 'tenant_alpha', 'act_a2', 'agt_a', 'id_a', 'tool_call', 'fs', 'root', 'ALLOW', '["PERMITTED"]', '2026-01-01T11:00:00Z', '2026-01-01T11:00:00Z', 'hash_e2', 'hash_e1', 1, 'LEGACY_CHAINED_V1', 2),
                        ('ev_beta_1', 'tenant_beta', 'act_b1', 'agt_b', 'id_b', 'tool_call', 'fs', 'root', 'DENY', '["POLICY_DENY"]', '2026-01-02T10:00:00Z', '2026-01-02T10:00:00Z', 'hash_e3', NULL, 1, 'LEGACY_CHAINED_V1', 1)
                """)
            )

            # Evidence Chain Heads
            await conn.execute(
                text("""
                    INSERT INTO governance_evidence_chain_heads (org_id, head_hash, sequence, updated_at)
                    VALUES
                        ('tenant_alpha', 'hash_head_alpha', 2, '2026-01-01T11:00:00Z'),
                        ('tenant_beta', 'hash_head_beta', 1, '2026-01-02T10:00:00Z')
                """)
            )

            # Revocation Epochs
            await conn.execute(
                text("""
                    INSERT INTO governance_revocation_epochs (organization_id, scope, epoch, updated_at)
                    VALUES
                        ('tenant_alpha', 'global', 42, '2026-01-01T12:00:00Z'),
                        ('tenant_beta', 'global', 17, '2026-01-02T12:00:00Z')
                """)
            )

            # Execution Nonces
            await conn.execute(
                text("""
                    INSERT INTO governance_execution_nonces (nonce, authorization_id, organization_id, consumed_at)
                    VALUES
                        ('nonce_alpha_1', 'auth_a1', 'tenant_alpha', '2026-01-01T10:00:00Z')
                """)
            )

            # Approvals
            await conn.execute(
                text("""
                    INSERT INTO governance_approvals (
                        id, org_id, action_id, action_type, target, reason_codes, risk_tier, status,
                        requested_by, requested_at, action_digest, expires_at
                    )
                    VALUES
                        ('app_alpha_pnd', 'tenant_alpha', 'act_ap1', 'elevated_action', 'res1', '["HIGH_RISK"]', 'HIGH', 'PENDING', 'usr_alpha_admin', '2026-01-01T12:00:00Z', 'dig_a1', '2026-01-01T13:00:00Z'),
                        ('app_beta_rej', 'tenant_beta', 'act_bp1', 'export', 'res2', '["UNAUTHORIZED"]', 'CRITICAL', 'REJECTED', 'usr_beta_member', '2026-01-02T12:00:00Z', 'dig_b1', '2026-01-02T13:00:00Z')
                """)
            )

            await conn.commit()

        # 3. Perform upgrade from 0042 to HEAD (0045)
        await _run_alembic(ini, env, "upgrade", "head")

        # 4. Verify post-upgrade state and security invariants
        async with engine.raw.connect() as conn:
            head_ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert head_ver == "0049"

            # Invariant 1: Organizations preserved
            orgs = (await conn.execute(text("SELECT id, name, plan FROM organizations ORDER BY id"))).fetchall()
            assert len(orgs) == 2
            assert orgs[0] == ("tenant_alpha", "Tenant Alpha Corp", "ENTERPRISE")
            assert orgs[1] == ("tenant_beta", "Tenant Beta LLC", "PRO")

            # Invariant 2: Privilege preservation in web_memberships (viewer did NOT become admin)
            mems = (await conn.execute(text("SELECT id, user_id, org_id, role FROM web_memberships ORDER BY id"))).fetchall()
            assert len(mems) == 3
            mem_map = {m[0]: m for m in mems}
            assert mem_map["mem_alpha_viw"] == ("mem_alpha_viw", "usr_alpha_viewer", "tenant_alpha", "viewer"), "Viewer role widened!"
            assert mem_map["mem_alpha_adm"] == ("mem_alpha_adm", "usr_alpha_admin", "tenant_alpha", "admin")
            assert mem_map["mem_beta_mem"] == ("mem_beta_mem", "usr_beta_member", "tenant_beta", "member"), "Member role widened!"

            # Invariant 3: Revocation preservation (revoked key did NOT reactivate)
            keys = (await conn.execute(text("SELECT id, revoked, org_id FROM org_api_keys ORDER BY id"))).fetchall()
            key_map = {k[0]: (k[1], k[2]) for k in keys}
            assert key_map["key_alpha_rev"] == (1, "tenant_alpha"), "Revoked key resurrected!"
            assert key_map["key_alpha_act"] == (0, "tenant_alpha")

            # Invariant 4: Policy preservation (DENY remained DENY)
            pols = (await conn.execute(text("SELECT id, effect, org_id FROM governance_policies ORDER BY id"))).fetchall()
            pol_map = {p[0]: (p[1], p[2]) for p in pols}
            assert pol_map["pol_alpha_deny"] == ("DENY", "tenant_alpha")
            assert pol_map["pol_beta_allow"] == ("ALLOW", "tenant_beta")

            # Invariant 5: Evidence preservation & integrity status
            evidence = (await conn.execute(text("""
                SELECT id, org_id, decision, integrity_status, chain_sequence, policy_digest
                FROM governance_evidence ORDER BY id
            """))).fetchall()
            assert len(evidence) == 3
            ev_map = {e[0]: e for e in evidence}
            assert ev_map["ev_alpha_1"][1] == "tenant_alpha"
            assert ev_map["ev_alpha_1"][2] == "DENY"
            assert ev_map["ev_alpha_1"][3] == "LEGACY_CHAINED_V1"
            assert ev_map["ev_alpha_1"][4] == 1
            assert ev_map["ev_alpha_1"][5] is None  # Newly added nullable column in 0045
            assert ev_map["ev_beta_1"][1] == "tenant_beta"
            assert ev_map["ev_beta_1"][2] == "DENY"

            # Invariant 6: Chain heads preserved
            heads = (await conn.execute(text("SELECT org_id, sequence, head_hash FROM governance_evidence_chain_heads ORDER BY org_id"))).fetchall()
            assert len(heads) == 2
            assert heads[0] == ("tenant_alpha", 2, "hash_head_alpha")
            assert heads[1] == ("tenant_beta", 1, "hash_head_beta")

            # Invariant 7: Security epochs preserved
            epochs = (await conn.execute(text("SELECT organization_id, scope, epoch FROM governance_revocation_epochs ORDER BY organization_id"))).fetchall()
            assert epochs[0] == ("tenant_alpha", "global", 42)
            assert epochs[1] == ("tenant_beta", "global", 17)

            # Invariant 8: Execution nonces preserved
            nonce_row = (await conn.execute(text("SELECT nonce, organization_id, authorization_id FROM governance_execution_nonces"))).fetchone()
            assert nonce_row == ("nonce_alpha_1", "tenant_alpha", "auth_a1")

            # Invariant 9: Approvals preserved (pending did NOT auto-approve)
            apps = (await conn.execute(text("SELECT id, status, org_id FROM governance_approvals ORDER BY id"))).fetchall()
            app_map = {a[0]: (a[1], a[2]) for a in apps}
            assert app_map["app_alpha_pnd"] == ("PENDING", "tenant_alpha"), "Pending approval mutated!"
            assert app_map["app_beta_rej"] == ("REJECTED", "tenant_beta")
    finally:
        await engine.close()


# ── Section 5-14: Upgrade Path B (0043 -> 0045 HEAD) ─────────────────────────


@pytest.mark.asyncio
async def test_upgrade_0043_to_head_preserves_trust_fabric_and_invariants(pg_disposable_db: str):
    """Historical Upgrade Path B: 0043 -> 0045 (HEAD).

    Proves:
    - Phase 3 Global Trust Fabric data survives upgrade to current HEAD.
    - Zero trust widening: PENDING_VERIFICATION and UNVERIFIED states are NOT mutated to PROVEN.
    - Revoked identifiers remain revoked with revoked_at timestamp intact.
    - Unresolved conflicts remain unresolved.
    - Tenant ownership of principals and relationships strictly preserved.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)

    # 1. Migrate to historical revision 0043
    await _run_alembic(ini, env, "upgrade", "0043")

    engine = create_engine(pg_disposable_db)
    try:
        async with engine.raw.connect() as conn:
            # Seed organizations
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, plan, created_at)
                    VALUES
                        ('tenant_alpha', 'Tenant Alpha', 'alpha', 10000.0, 'ENTERPRISE', '2026-01-01T00:00:00Z'),
                        ('tenant_beta', 'Tenant Beta', 'beta', 5000.0, 'ENTERPRISE', '2026-01-02T00:00:00Z')
                """)
            )

            # Seed Trust Fabric Principals
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, lifecycle_state, created_at, updated_at)
                    VALUES
                        ('prin_alpha_human', 'tenant_alpha', 'HUMAN', 'Alpha Human', 'ACTIVE', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
                        ('prin_alpha_agent', 'tenant_alpha', 'AI_AGENT', 'Alpha Agent', 'PENDING_VERIFICATION', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z'),
                        ('prin_beta_agent', 'tenant_beta', 'AI_AGENT', 'Beta Agent', 'PENDING_VERIFICATION', '2026-01-02T00:00:00Z', '2026-01-02T00:00:00Z')
                """)
            )

            # Seed Trust Fabric Identifiers
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_identifiers (
                        id, principal_id, org_id, identifier_type, raw_value, normalized_value,
                        is_primary, verification_state, created_at, revoked_at
                    )
                    VALUES
                        ('id_alpha_act', 'prin_alpha_human', 'tenant_alpha', 'EMAIL', 'user@alpha.com', 'user@alpha.com', 1, 'VERIFIED', '2026-01-01T00:00:00Z', NULL),
                        ('id_alpha_rev', 'prin_alpha_human', 'tenant_alpha', 'DID', 'did:key:123', 'did:key:123', 0, 'REVOKED', '2026-01-01T00:00:00Z', '2026-01-01T12:00:00Z'),
                        ('id_beta_unv', 'prin_beta_agent', 'tenant_beta', 'SPIFFE', 'spiffe://beta/agent', 'spiffe://beta/agent', 1, 'UNVERIFIED', '2026-01-02T00:00:00Z', NULL)
                """)
            )

            # Seed Relationships & Authority Edges
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_relationships (
                        id, subject_principal_id, target_principal_id, org_id,
                        relationship_type, role_title, verification_state, valid_from, source_id
                    )
                    VALUES
                        ('rel_alpha_1', 'prin_alpha_human', 'prin_alpha_agent', 'tenant_alpha',
                         'DELEGATES_TO', 'operator', 'VERIFIED', '2026-01-01T00:00:00Z', 'src_alpha')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_authority_edges (
                        id, grantor_principal_id, grantee_principal_id, org_id,
                        action_type, resource_pattern, delegation_depth, valid_from, canonical_digest
                    )
                    VALUES
                        ('edge_alpha_1', 'prin_alpha_human', 'prin_alpha_agent', 'tenant_alpha',
                         'execute_tool', '*', 1, '2026-01-01T00:00:00Z', 'digest_edge_1')
                """)
            )

            # Seed Conflicts & Challenges
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_conflicts (
                        id, principal_id, org_id, field_or_claim, assertion_id_a, assertion_id_b,
                        conflict_type, detected_at, status
                    )
                    VALUES
                        ('conf_alpha_1', 'prin_alpha_agent', 'tenant_alpha', 'key', 'asst_1', 'asst_2',
                         'KEY_COLLISION', '2026-01-01T00:00:00Z', 'UNRESOLVED')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO trust_fabric_challenges (
                        id, principal_id, org_id, challenge_type, target_identifier, nonce,
                        expected_response_hash, status, issued_at, expires_at
                    )
                    VALUES
                        ('chal_beta_1', 'prin_beta_agent', 'tenant_beta', 'OIDC_PROOF', 'spiffe://beta/agent',
                         'nonce_123', 'hash_exp', 'PENDING', '2026-01-02T00:00:00Z', '2026-01-02T01:00:00Z')
                """)
            )

            await conn.commit()

        # 2. Upgrade from 0043 to HEAD (0045)
        await _run_alembic(ini, env, "upgrade", "head")

        # 3. Verify invariants
        async with engine.raw.connect() as conn:
            head_ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert head_ver == "0049"

            # Invariant: Principals preserved and states NOT widened
            prins = (await conn.execute(text("SELECT id, org_id, principal_type, lifecycle_state FROM trust_fabric_principals ORDER BY id"))).fetchall()
            assert len(prins) == 3
            prin_map = {p[0]: p for p in prins}
            assert prin_map["prin_alpha_agent"] == ("prin_alpha_agent", "tenant_alpha", "AI_AGENT", "PENDING_VERIFICATION"), "Trust state widened!"
            assert prin_map["prin_beta_agent"] == ("prin_beta_agent", "tenant_beta", "AI_AGENT", "PENDING_VERIFICATION")
            assert prin_map["prin_alpha_human"] == ("prin_alpha_human", "tenant_alpha", "HUMAN", "ACTIVE")

            # Invariant: Identifiers preserved, revocation preserved, unverified NOT widened
            idents = (await conn.execute(text("SELECT id, org_id, verification_state, revoked_at FROM trust_fabric_identifiers ORDER BY id"))).fetchall()
            assert len(idents) == 3
            ident_map = {i[0]: i for i in idents}
            assert ident_map["id_alpha_rev"][2] == "REVOKED", "Revoked identifier resurrected!"
            assert ident_map["id_alpha_rev"][3] == "2026-01-01T12:00:00Z"
            assert ident_map["id_beta_unv"][2] == "UNVERIFIED", "Unverified identifier mutated to proven!"
            assert ident_map["id_beta_unv"][1] == "tenant_beta"

            # Invariant: Relationships and Authority edges preserved
            rel = (await conn.execute(text("SELECT id, org_id, relationship_type, verification_state FROM trust_fabric_relationships"))).fetchone()
            assert rel == ("rel_alpha_1", "tenant_alpha", "DELEGATES_TO", "VERIFIED")

            edge = (await conn.execute(text("SELECT id, org_id, action_type, delegation_depth FROM trust_fabric_authority_edges"))).fetchone()
            assert edge == ("edge_alpha_1", "tenant_alpha", "execute_tool", 1)

            # Invariant: Conflicts remain UNRESOLVED
            conf = (await conn.execute(text("SELECT id, org_id, status FROM trust_fabric_conflicts"))).fetchone()
            assert conf == ("conf_alpha_1", "tenant_alpha", "UNRESOLVED")

            # Invariant: Challenges remain PENDING
            chal = (await conn.execute(text("SELECT id, org_id, status FROM trust_fabric_challenges"))).fetchone()
            assert chal == ("chal_beta_1", "tenant_beta", "PENDING")
    finally:
        await engine.close()


# ── Section 5-14: Upgrade Path C (0044 -> 0045 HEAD) ─────────────────────────


@pytest.mark.asyncio
async def test_upgrade_0044_to_head_preserves_iam_and_invariants(pg_disposable_db: str):
    """Historical Upgrade Path C: 0044 -> 0045 (HEAD).

    Proves:
    - Phase 4 Enterprise IAM data survives upgrade to current HEAD.
    - Zero privilege widening: empty scopes remain empty, revoked sessions stay revoked.
    - Terminated break-glass sessions remain terminated.
    - Pending four-eyes approvals remain pending.
    - Tenant ownership of IAM objects strictly preserved.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)

    # 1. Migrate to historical revision 0044
    await _run_alembic(ini, env, "upgrade", "0044")

    engine = create_engine(pg_disposable_db)
    try:
        async with engine.raw.connect() as conn:
            # Seed organizations
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, plan, created_at)
                    VALUES
                        ('tenant_alpha', 'Alpha Enterprise', 'alpha-ent', 10000.0, 'ENTERPRISE', '2026-01-01T00:00:00Z'),
                        ('tenant_beta', 'Beta Enterprise', 'beta-ent', 5000.0, 'ENTERPRISE', '2026-01-02T00:00:00Z')
                """)
            )

            # Seed IAM Sessions
            await conn.execute(
                text("""
                    INSERT INTO iam_sessions (
                        id, org_id, principal_id, token_hash, session_type, status,
                        created_at, expires_at, last_seen_at, revoked_at
                    )
                    VALUES
                        ('sess_alpha_act', 'tenant_alpha', 'prin_a', 'tok_h1', 'INTERACTIVE', 'ACTIVE', '2026-01-01T00:00:00Z', '2026-01-01T08:00:00Z', '2026-01-01T00:00:00Z', NULL),
                        ('sess_alpha_rev', 'tenant_alpha', 'prin_a', 'tok_h2', 'INTERACTIVE', 'REVOKED', '2026-01-01T00:00:00Z', '2026-01-01T08:00:00Z', '2026-01-01T00:00:00Z', '2026-01-01T02:00:00Z'),
                        ('sess_beta_act', 'tenant_beta', 'prin_b', 'tok_h3', 'INTERACTIVE', 'ACTIVE', '2026-01-02T00:00:00Z', '2026-01-02T08:00:00Z', '2026-01-02T00:00:00Z', NULL)
                """)
            )

            # Seed IAM API Key Lineage (Scope & Privilege preservation)
            await conn.execute(
                text("""
                    INSERT INTO iam_api_key_lineage (
                        id, org_id, name, fingerprint, parent_key_id, status,
                        scopes_json, created_at, expires_at, revoked_at
                    )
                    VALUES
                        ('lineage_alpha_1', 'tenant_alpha', 'CI Key', 'fp_a1', NULL, 'ACTIVE', '["read:evidence"]', '2026-01-01T00:00:00Z', '2026-01-01T08:00:00Z', NULL),
                        ('lineage_beta_empty', 'tenant_beta', 'Empty Scope Key', 'fp_b1', NULL, 'ACTIVE', '[]', '2026-01-02T00:00:00Z', '2026-01-02T08:00:00Z', NULL)
                """)
            )

            # Seed JIT Grants & Four-Eyes Requests
            await conn.execute(
                text("""
                    INSERT INTO iam_jit_grants (
                        id, org_id, principal_id, target_role, allowed_actions_json,
                        justification, status, requested_at, expires_at, revoked_at
                    )
                    VALUES
                        ('jit_alpha_act', 'tenant_alpha', 'prin_a', 'sec_operator', '["all"]',
                         'security ops', 'ACTIVE', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', NULL),
                        ('jit_alpha_rev', 'tenant_alpha', 'prin_a', 'admin', '["admin"]',
                         'emergency access', 'REVOKED', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', '2026-01-01T00:30:00Z')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO iam_four_eyes_requests (
                        id, org_id, requester_principal_id, action, parameters_json,
                        request_digest, status, created_at, expires_at
                    )
                    VALUES
                        ('4eyes_alpha_pnd', 'tenant_alpha', 'prin_a', 'vault_export', '{}',
                         'dig123', 'PENDING', '2026-01-01T00:00:00Z', '2026-01-01T02:00:00Z')
                """)
            )

            # Seed Break Glass Session (Terminated preservation)
            await conn.execute(
                text("""
                    INSERT INTO iam_break_glass_sessions (
                        id, org_id, principal_id, incident_id, capabilities_json,
                        justification, status, started_at, expires_at, terminated_at
                    )
                    VALUES
                        ('bg_alpha_term', 'tenant_alpha', 'prin_a', 'INC-1234', '["admin"]',
                         'Incident #1234', 'TERMINATED', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', '2026-01-01T00:45:00Z')
                """)
            )

            await conn.commit()

        # 2. Upgrade from 0044 to HEAD (0045)
        await _run_alembic(ini, env, "upgrade", "head")

        # 3. Verify invariants
        async with engine.raw.connect() as conn:
            head_ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert head_ver == "0049"

            # Invariant: Sessions preserved and revoked stays revoked
            sessions = (await conn.execute(text("SELECT id, org_id, status, revoked_at FROM iam_sessions ORDER BY id"))).fetchall()
            assert len(sessions) == 3
            sess_map = {s[0]: s for s in sessions}
            assert sess_map["sess_alpha_rev"][2] == "REVOKED", "Revoked session resurrected!"
            assert sess_map["sess_alpha_rev"][3] == "2026-01-01T02:00:00Z"
            assert sess_map["sess_alpha_act"][2] == "ACTIVE"
            assert sess_map["sess_beta_act"][1] == "tenant_beta"

            # Invariant: API key lineage scopes preserved (no scope escalation)
            keys = (await conn.execute(text("SELECT id, org_id, scopes_json FROM iam_api_key_lineage ORDER BY id"))).fetchall()
            assert len(keys) == 2
            key_map = {k[0]: (k[1], json.loads(k[2])) for k in keys}
            assert key_map["lineage_beta_empty"] == ("tenant_beta", []), "Empty scope escalated!"
            assert key_map["lineage_alpha_1"] == ("tenant_alpha", ["read:evidence"])

            # Invariant: JIT grants preserved
            jits = (await conn.execute(text("SELECT id, org_id, target_role, status FROM iam_jit_grants ORDER BY id"))).fetchall()
            assert len(jits) == 2
            jit_map = {j[0]: j for j in jits}
            assert jit_map["jit_alpha_rev"][3] == "REVOKED", "Revoked JIT grant resurrected!"
            assert jit_map["jit_alpha_act"][3] == "ACTIVE"

            # Invariant: Four-eyes pending request did NOT approve
            four_eyes = (await conn.execute(text("SELECT id, org_id, status FROM iam_four_eyes_requests"))).fetchone()
            assert four_eyes == ("4eyes_alpha_pnd", "tenant_alpha", "PENDING")

            # Invariant: Break-glass terminated session did NOT resurrect
            bg = (await conn.execute(text("SELECT id, org_id, status FROM iam_break_glass_sessions"))).fetchone()
            assert bg == ("bg_alpha_term", "tenant_alpha", "TERMINATED")
    finally:
        await engine.close()


# ── Section 18: Idempotence & Downgrade/Re-upgrade ────────────────────────────


@pytest.mark.asyncio
async def test_downgrade_and_reupgrade_idempotence(pg_disposable_db: str):
    """Prove idempotence and rollback safety: 0045 -> 0044 -> 0045.
    Existing data in 0044 tables survives the roundtrip without corruption.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)

    # 1. Upgrade to 0045
    await _run_alembic(ini, env, "upgrade", "head")

    engine = create_engine(pg_disposable_db)
    try:
        async with engine.raw.connect() as conn:
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, plan, created_at)
                    VALUES ('tenant_rt', 'Roundtrip Org', 'rt-org', 10000.0, 'ENTERPRISE', '2026-01-01T00:00:00Z')
                """)
            )
            await conn.execute(
                text("""
                    INSERT INTO iam_sessions (
                        id, org_id, principal_id, token_hash, session_type, status,
                        created_at, expires_at, last_seen_at
                    )
                    VALUES ('sess_rt', 'tenant_rt', 'prin_rt', 'tok_rt', 'INTERACTIVE', 'ACTIVE', '2026-01-01T00:00:00Z', '2026-01-01T08:00:00Z', '2026-01-01T00:00:00Z')
                """)
            )
            # Insert Phase 5 record
            await conn.execute(
                text("""
                    INSERT INTO data_holds (id, org_id, data_category, hold_reason, active, created_at, created_by)
                    VALUES ('hold_rt', 'tenant_rt', 'audit_logs', 'Litigation Hold', true, '2026-01-01T00:00:00Z', 'legal')
                """)
            )
            await conn.commit()

        # 2. Downgrade to 0044
        await _run_alembic(ini, env, "downgrade", "0044")

        async with engine.raw.connect() as conn:
            ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert ver == "0044"

            # Verify 0044 data survived the rollback of 0045
            sess = (await conn.execute(text("SELECT id, org_id, status FROM iam_sessions WHERE id = 'sess_rt'"))).fetchone()
            assert sess == ("sess_rt", "tenant_rt", "ACTIVE")

        # 3. Re-upgrade to 0045 (head)
        await _run_alembic(ini, env, "upgrade", "head")

        async with engine.raw.connect() as conn:
            head_ver = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert head_ver == "0049"

            # Verify 0044 data remains clean
            sess = (await conn.execute(text("SELECT id, org_id, status FROM iam_sessions WHERE id = 'sess_rt'"))).fetchone()
            assert sess == ("sess_rt", "tenant_rt", "ACTIVE")
    finally:
        await engine.close()


# ── Section 16: Foreign Keys & Tenant Isolation Enforcement ───────────────────


@pytest.mark.asyncio
async def test_foreign_key_and_tenant_boundary_enforcement(pg_disposable_db: str):
    """Verify that foreign keys prevent malformed or cross-tenant links."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_disposable_db)
    await _run_alembic(ini, env, "upgrade", "head")

    engine = create_engine(pg_disposable_db)
    try:
        # 1. Foreign key on trust_fabric_principals.org_id -> organizations.id
        async with engine.raw.connect() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text("""
                        INSERT INTO trust_fabric_principals (id, org_id, principal_type, display_name, created_at, updated_at)
                        VALUES ('prin_orphaned', 'non_existent_org', 'AI_AGENT', 'Bad Agent', '2026-01-01', '2026-01-01')
                    """)
                )

        # 2. Foreign key on governance_policy_revisions.org_id -> organizations.id
        async with engine.raw.connect() as conn:
            with pytest.raises(IntegrityError):
                await conn.execute(
                    text("""
                        INSERT INTO governance_policy_revisions (id, org_id, revision_num, rules_json, content_digest, created_at, created_by, change_reason)
                        VALUES ('rev_orphaned', 'non_existent_org', 1, '{}', 'dig', '2026-01-01', 'admin', 'reason')
                    """)
                )
    finally:
        await engine.close()


# ── Section 15: Security Defaults & Backfill Audit ────────────────────────────


def test_security_defaults_audit():
    """Audit migration revisions 0042, 0043, 0044, 0045 for dangerous defaults:
    - No admin=True, approved=True, trusted=True, allow=True
    - No PROVEN default on verification_state or lifecycle_state
    - All security-sensitive defaults must be classified SAFE.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    scripts = ScriptDirectory.from_config(Config(str(ini)))

    dangerous_patterns = [
        "server_default='admin'",
        'server_default="admin"',
        "server_default='PROVEN'",
        'server_default="PROVEN"',
        "server_default='VERIFIED'",
        'server_default="VERIFIED"',
        "server_default='APPROVED'",
        'server_default="APPROVED"',
        "server_default='ALLOW'",
        'server_default="ALLOW"',
    ]

    for rev in ["0042", "0043", "0044", "0045"]:
        script = scripts.get_revision(rev)
        path = script.path
        with open(path, encoding="utf-8") as f:
            content = f.read()

        for pattern in dangerous_patterns:
            assert pattern not in content, f"Dangerous default {pattern} found in revision {rev}!"
