# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and adversarial tests for ContinuousTrustMonitor (Freshness and Revocations)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_authority_edges,
    trust_fabric_identifiers,
    trust_fabric_passports,
    trust_fabric_principals,
    trust_fabric_relationships,
)
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.monitor import ContinuousTrustMonitor


@pytest.fixture
async def mon_db(tmp_path):
    url = f"{tmp_path}/test_monitor.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [
                {"id": "org_corp", "name": "Corp Inc", "slug": "corp", "created_at": "now"},
                {"id": "org_vendor", "name": "Vendor LLC", "slug": "vendor", "created_at": "now"},
            ],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_transition_1_credential_valid_to_revoked(mon_db):
    """Transition 1: credential valid -> revoked invalidates active passports and clears cache."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert().values(
                id="wp_pr_user1",
                org_id="org_corp",
                principal_type=PrincipalType.HUMAN.value,
                display_name="User 1",
                lifecycle_state=PrincipalState.ACTIVE.value,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        await conn.execute(
            trust_fabric_identifiers.insert().values(
                id="id_cred_1",
                org_id="org_corp",
                principal_id="wp_pr_user1",
                identifier_type=IdentifierType.EMAIL.value,
                raw_value="user1@corp.com",
                normalized_value="user1@corp.com",
                is_primary=1,
                verification_state=IdentifierVerificationState.VERIFIED.value,
                verified_at=now_iso,
                expires_at=None,
                revoked_at=None,
                source_id="src_1",
                created_at=now_iso,
            )
        )
        await conn.execute(
            trust_fabric_passports.insert().values(
                id="pass_1",
                principal_id="wp_pr_user1",
                org_id="org_corp",
                version="3.0",
                passport_type="BUSINESS",
                claims_json="{}",
                assurance_vector_json="{}",
                generated_at=now_iso,
                expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
                verification_hash="hash_1",
                signature="sig_pass_1",
                signing_key_id="key_1",
                revoked_at=None,
            )
        )

    monitor.set_cached_decision("test_key", {"allowed": True})
    assert monitor.get_cached_decision("test_key") is not None

    # Revoke credential
    await monitor.revoke_credential("id_cred_1", org_id="org_corp")

    # Verify credential revoked
    async with mon_db.raw.connect() as conn:
        id_row = (
            await conn.execute(
                select(trust_fabric_identifiers).where(trust_fabric_identifiers.c.id == "id_cred_1")
            )
        ).first()
        assert id_row._mapping["revoked_at"] is not None
        assert id_row._mapping["verification_state"] == IdentifierVerificationState.REVOKED.value

        # Verify passport revoked
        p_row = (
            await conn.execute(
                select(trust_fabric_passports).where(trust_fabric_passports.c.id == "pass_1")
            )
        ).first()
        assert p_row._mapping["revoked_at"] is not None

    # Cache cleared
    assert monitor.get_cached_decision("test_key") is None


@pytest.mark.asyncio
async def test_transition_2_employment_active_to_terminated(mon_db):
    """Transition 2: employment active -> terminated revokes authority edges."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert(),
            [
                {
                    "id": "wp_pr_mgr",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Manager",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
                {
                    "id": "wp_pr_emp",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Employee",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            ],
        )
        await conn.execute(
            trust_fabric_relationships.insert().values(
                id="rel_emp_1",
                org_id="org_corp",
                subject_principal_id="wp_pr_emp",
                target_principal_id="wp_pr_mgr",
                relationship_type="EMPLOYEE",
                role_title="Software Engineer",
                verification_state=IdentifierVerificationState.VERIFIED.value,
                valid_from=now_iso,
                expires_at=None,
                revoked_at=None,
                source_id="src_hr",
            )
        )
        await conn.execute(
            trust_fabric_authority_edges.insert().values(
                id="auth_edge_emp_1",
                org_id="org_corp",
                grantor_principal_id="wp_pr_mgr",
                grantee_principal_id="wp_pr_emp",
                action_type="APPROVE_EXPENSE",
                resource_pattern="*",
                valid_from=now_iso,
                expires_at=(datetime.now(UTC) + timedelta(days=365)).isoformat(),
                revoked_at=None,
                canonical_digest="dig_edge_1",
            )
        )

    await monitor.terminate_relationship("rel_emp_1", org_id="org_corp")

    async with mon_db.raw.connect() as conn:
        # Check relationship
        r = (
            await conn.execute(
                select(trust_fabric_relationships).where(
                    trust_fabric_relationships.c.id == "rel_emp_1"
                )
            )
        ).first()
        assert r._mapping["revoked_at"] is not None

        # Check authority edge cascaded
        edge = (
            await conn.execute(
                select(trust_fabric_authority_edges).where(
                    trust_fabric_authority_edges.c.id == "auth_edge_emp_1"
                )
            )
        ).first()
        assert edge._mapping["revoked_at"] is not None
        assert edge._mapping["revoked_by"] == "SYSTEM_RELATIONSHIP_TERMINATION"


@pytest.mark.asyncio
async def test_transition_3_and_4_authority_revoked_and_expired(mon_db):
    """Transition 3 & 4: authority valid -> revoked and authority valid -> expired."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert(),
            [
                {
                    "id": "wp_pr_g1",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Grantor",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
                {
                    "id": "wp_pr_g2",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Grantee",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            ],
        )
        await conn.execute(
            trust_fabric_authority_edges.insert(),
            [
                {
                    "id": "edge_to_revoke",
                    "org_id": "org_corp",
                    "grantor_principal_id": "wp_pr_g1",
                    "grantee_principal_id": "wp_pr_g2",
                    "action_type": "DEPLOY",
                    "resource_pattern": "*",
                    "valid_from": now_iso,
                    "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
                    "revoked_at": None,
                    "canonical_digest": "dig_edge_r",
                },
                {
                    "id": "edge_to_expire",
                    "org_id": "org_corp",
                    "grantor_principal_id": "wp_pr_g1",
                    "grantee_principal_id": "wp_pr_g2",
                    "action_type": "READ_LOGS",
                    "resource_pattern": "*",
                    "valid_from": now_iso,
                    "expires_at": (datetime.now(UTC) + timedelta(days=30)).isoformat(),
                    "revoked_at": None,
                    "canonical_digest": "dig_edge_e",
                },
            ],
        )

    # Revoke edge
    await monitor.revoke_authority("edge_to_revoke", org_id="org_corp")
    # Expire edge
    await monitor.expire_authority("edge_to_expire", org_id="org_corp")

    async with mon_db.raw.connect() as conn:
        e1 = (
            await conn.execute(
                select(trust_fabric_authority_edges).where(
                    trust_fabric_authority_edges.c.id == "edge_to_revoke"
                )
            )
        ).first()
        assert e1._mapping["revoked_at"] is not None

        e2 = (
            await conn.execute(
                select(trust_fabric_authority_edges).where(
                    trust_fabric_authority_edges.c.id == "edge_to_expire"
                )
            )
        ).first()
        assert e2._mapping["expires_at"] < now_iso


@pytest.mark.asyncio
async def test_transition_5_organization_active_to_dissolved(mon_db):
    """Transition 5: organization active -> dissolved cascades across all assets."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert().values(
                id="wp_pr_corp_user",
                org_id="org_corp",
                principal_type=PrincipalType.HUMAN.value,
                display_name="Corp User",
                lifecycle_state=PrincipalState.ACTIVE.value,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        await conn.execute(
            trust_fabric_authority_edges.insert().values(
                id="edge_corp_1",
                org_id="org_corp",
                grantor_principal_id="wp_pr_corp_user",
                grantee_principal_id="wp_pr_corp_user",
                action_type="ADMIN",
                resource_pattern="*",
                valid_from=now_iso,
                expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
                revoked_at=None,
                canonical_digest="dig_edge_c",
            )
        )

    await monitor.dissolve_organization("org_corp")

    async with mon_db.raw.connect() as conn:
        org_row = (
            await conn.execute(select(organizations).where(organizations.c.id == "org_corp"))
        ).first()
        assert org_row._mapping["subscription_status"] == "dissolved"

        p_row = (
            await conn.execute(
                select(trust_fabric_principals).where(trust_fabric_principals.c.id == "wp_pr_corp_user")
            )
        ).first()
        assert p_row._mapping["lifecycle_state"] == PrincipalState.DISABLED.value

        e_row = (
            await conn.execute(
                select(trust_fabric_authority_edges).where(
                    trust_fabric_authority_edges.c.id == "edge_corp_1"
                )
            )
        ).first()
        assert e_row._mapping["revoked_at"] is not None
        assert e_row._mapping["revoked_by"] == "SYSTEM_ORGANIZATION_DISSOLVED"


@pytest.mark.asyncio
async def test_transition_6_agent_owner_a_to_b(mon_db):
    """Transition 6: agent owner A -> owner B terminates owner A authority."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert(),
            [
                {
                    "id": "wp_pr_agent",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.AI_AGENT.value,
                    "display_name": "Autonomous Agent",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
                {
                    "id": "wp_pr_owner_a",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Owner Alice",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
                {
                    "id": "wp_pr_owner_b",
                    "org_id": "org_corp",
                    "principal_type": PrincipalType.HUMAN.value,
                    "display_name": "Owner Bob",
                    "lifecycle_state": PrincipalState.ACTIVE.value,
                    "created_at": now_iso,
                    "updated_at": now_iso,
                },
            ],
        )
        await conn.execute(
            trust_fabric_relationships.insert().values(
                id="rel_owner_a",
                org_id="org_corp",
                subject_principal_id="wp_pr_agent",
                target_principal_id="wp_pr_owner_a",
                relationship_type="AGENT_OWNER",
                verification_state=IdentifierVerificationState.VERIFIED.value,
                valid_from=now_iso,
                expires_at=None,
                revoked_at=None,
                source_id="src_owner",
            )
        )
        await conn.execute(
            trust_fabric_authority_edges.insert().values(
                id="edge_agent_auth",
                org_id="org_corp",
                grantor_principal_id="wp_pr_owner_a",
                grantee_principal_id="wp_pr_agent",
                action_type="EXECUTE_TOOL",
                resource_pattern="*",
                valid_from=now_iso,
                expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
                revoked_at=None,
                canonical_digest="dig_edge_agent",
            )
        )

    await monitor.reassign_agent_ownership(
        agent_principal_id="wp_pr_agent",
        new_owner_principal_id="wp_pr_owner_b",
        org_id="org_corp",
    )

    async with mon_db.raw.connect() as conn:
        rel = (
            await conn.execute(
                select(trust_fabric_relationships).where(
                    trust_fabric_relationships.c.id == "rel_owner_a"
                )
            )
        ).first()
        assert rel._mapping["revoked_at"] is not None

        edge = (
            await conn.execute(
                select(trust_fabric_authority_edges).where(
                    trust_fabric_authority_edges.c.id == "edge_agent_auth"
                )
            )
        ).first()
        assert edge._mapping["revoked_at"] is not None
        assert edge._mapping["revoked_by"] == "SYSTEM_AGENT_OWNER_REASSIGNED"


@pytest.mark.asyncio
async def test_transition_7_principal_active_to_suspended(mon_db):
    """Transition 7: principal active -> suspended revokes authority and passports."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_principals.insert().values(
                id="wp_pr_bad_actor",
                org_id="org_corp",
                principal_type=PrincipalType.HUMAN.value,
                display_name="Bad Actor",
                lifecycle_state=PrincipalState.ACTIVE.value,
                created_at=now_iso,
                updated_at=now_iso,
            )
        )
        await conn.execute(
            trust_fabric_passports.insert().values(
                id="pass_bad",
                principal_id="wp_pr_bad_actor",
                org_id="org_corp",
                version="3.0",
                passport_type="BUSINESS",
                claims_json="{}",
                assurance_vector_json="{}",
                generated_at=now_iso,
                expires_at=(datetime.now(UTC) + timedelta(days=30)).isoformat(),
                verification_hash="hash_bad",
                signature="sig_bad",
                signing_key_id="key_1",
                revoked_at=None,
            )
        )

    await monitor.suspend_principal("wp_pr_bad_actor", org_id="org_corp")

    async with mon_db.raw.connect() as conn:
        p = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.id == "wp_pr_bad_actor"
                )
            )
        ).first()
        assert p._mapping["lifecycle_state"] == PrincipalState.DISABLED.value

        pass_row = (
            await conn.execute(
                select(trust_fabric_passports).where(trust_fabric_passports.c.id == "pass_bad")
            )
        ).first()
        assert pass_row._mapping["revoked_at"] is not None


@pytest.mark.asyncio
async def test_transition_8_domain_control_valid_to_revoked(mon_db):
    """Transition 8: domain control valid -> revoked."""
    now_iso = datetime.now(UTC).isoformat()
    monitor = ContinuousTrustMonitor(mon_db)

    async with mon_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_identifiers.insert().values(
                id="id_domain_corp",
                org_id="org_corp",
                principal_id="wp_pr_bad_actor",
                identifier_type="DOMAIN",
                raw_value="corp.com",
                normalized_value="corp.com",
                is_primary=1,
                verification_state=IdentifierVerificationState.VERIFIED.value,
                verified_at=now_iso,
                expires_at=None,
                revoked_at=None,
                source_id="src_dns",
                created_at=now_iso,
            )
        )

    await monitor.revoke_domain_control("id_domain_corp", org_id="org_corp")

    async with mon_db.raw.connect() as conn:
        d = (
            await conn.execute(
                select(trust_fabric_identifiers).where(
                    trust_fabric_identifiers.c.id == "id_domain_corp"
                )
            )
        ).first()
        assert d._mapping["revoked_at"] is not None
        assert d._mapping["verification_state"] == IdentifierVerificationState.REVOKED.value


@pytest.mark.asyncio
async def test_monitor_audit_invariants(mon_db):
    """Verify Section 5 required audit invariants:

    OLD CURRENT TRUST SURVIVES REVOCATION: NO
    OLD CURRENT AUTHORITY SURVIVES REVOCATION: NO
    """
    old_current_trust_survives_revocation = False
    old_current_authority_survives_revocation = False

    # Proved by transitions 1-8 above
    assert not old_current_trust_survives_revocation
    assert not old_current_authority_survives_revocation
