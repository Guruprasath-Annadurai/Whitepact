# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial regression test suite for M13-S using real PostgreSQL and actual supported paths.

Verifies:
- P0-01: Migrations supply all four authority tables and support clean upgrade/downgrade.
- P0-02: Privileged containment strictly enforces phishing-resistant step-up, rejecting missing,
         replayed, tampered, or mismatched assertions.
- P0-03: In-flight execution termination failures or unresolved tasks strictly mark containment
         as UNRESOLVED in the return payload, database record, and audit log. Never confirmed as CONTAINED.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock

import asyncpg
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import select

from responsibleai.db.engine import (
    authority_containment_records,
    create_engine,
    enterprise_security_audit,
    passkey_credentials,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.webauthn import b64url_decode, b64url_encode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from responsibleai.enterprise.runtime import configure_enterprise
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from tests.pg_test_url import isolated_pg_url
from tests.webauthn_fakes import assertion_blob


def _register_fake_passkey(user_id: str):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()
    uncompressed = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    cred_id = hashlib.sha256(numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")).digest()[:16]
    cred_id_b64 = b64url_encode(cred_id)
    pub_b64 = b64url_encode(uncompressed)
    return private_key, cred_id_b64, pub_b64


async def _setup_postgres_workspace(url: str):
    ini = _find_alembic_ini()
    assert ini is not None
    await _run_alembic(ini, _migration_env(url), "upgrade", "head")

    engine = create_engine(url)
    configure_enterprise(engine)
    web_repo = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)

    user_id, token = await web_repo.register("Postgres Owner", "pg_owner@whitepact.test", "ComplexPass123!@#")
    await web_repo.verify_email(token)
    org = await iam.create_workspace(
        actor_user_id=user_id,
        name="Postgres Test Org",
        slug="pg-test-org",
        kind="ORGANIZATION",
    )
    org_id = org["id"] if isinstance(org, dict) else org.id
    actor = Actor(
        actor_type="USER",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=Role.OWNER,
        membership_status="ACTIVE",
    )
    return engine, actor, user_id, org_id


async def _create_test_assertion(
    svc: CustomerAuthorityService,
    engine: Any,
    actor: Actor,
    org_id: str,
    target_type: str,
    target_id: str,
    containment_action: str,
) -> dict[str, Any]:
    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(actor.user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=actor.user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                aaguid="00000000-0000-0000-0000-000000000000",
                backup_eligible=1,
                backup_state=1,
                display_name="Test Postgres Passkey",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    op_digest = compute_canonical_operation_digest(
        "EMERGENCY_CONTAINMENT",
        {
            "org_id": org_id,
            "target_type": target_type.upper(),
            "target_id": target_id,
            "containment_action": containment_action.upper(),
        },
    )
    ch_res = await svc.create_authority_stepup_challenge(
        actor, org_id=org_id, action="EMERGENCY_CONTAINMENT", operation_digest=op_digest
    )
    raw_challenge = b64url_decode(ch_res["challenge"])
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    return {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }


@pytest.mark.asyncio
async def test_real_postgres_migration_lifecycle():
    """P0-01: Verify all 4 tables exist on head, roll back cleanly to 0063, and re-upgrade."""
    async for url in isolated_pg_url("wp_m13s_mig"):
        ini = _find_alembic_ini()
        assert ini is not None
        env = _migration_env(url)

        # 1. Upgrade to head
        await _run_alembic(ini, env, "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            tables = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname = 'public'"
                )
            )
            required = {
                "authority_step_up_challenges",
                "authority_containment_records",
                "authority_recovery_requests",
                "authority_recovery_votes",
            }
            assert required <= tables, f"Missing authority tables on head: {required - tables}"

            # 2. Downgrade to 0063
            await _run_alembic(ini, env, "downgrade", "0063")
            tables_after_down = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname = 'public'"
                )
            )
            assert not (required & tables_after_down), f"Tables remained after downgrade: {required & tables_after_down}"

            # 3. Re-upgrade to head
            await _run_alembic(ini, env, "upgrade", "head")
            tables_after_reup = set(
                await conn.fetchval(
                    "SELECT array_agg(tablename) FROM pg_tables WHERE schemaname = 'public'"
                )
            )
            assert required <= tables_after_reup, "Failed to re-upgrade tables"
        finally:
            await conn.close()


@pytest.mark.asyncio
async def test_real_postgres_privileged_containment_enforces_stepup():
    """P0-02: Missing WebAuthn assertion must raise PASSKEY_STEP_UP_REQUIRED on real PostgreSQL."""
    async for url in isolated_pg_url("wp_m13s_p02"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            svc = CustomerAuthorityService(engine)
            with pytest.raises(EnterpriseError) as exc_info:
                await svc.execute_emergency_containment(
                    actor,
                    org_id=org_id,
                    target_type="ORGANIZATION",
                    target_id=org_id,
                    containment_action="LOCKDOWN",
                    reason="Step-up bypass attempt with omitted assertion",
                    webauthn_assertion=None,
                )
            assert exc_info.value.code == "PASSKEY_STEP_UP_REQUIRED"
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_stepup_replay_and_tampering_rejected():
    """P0-02: Replayed challenge or mismatched operation digest must be rejected on real PostgreSQL."""
    async for url in isolated_pg_url("wp_m13s_p02_adv"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            svc = CustomerAuthorityService(engine)

            # 1. Assertion digest mismatch: assertion created for AGENT cannot be used for ORGANIZATION
            agent_assertion = await _create_test_assertion(
                svc, engine, actor, org_id, "AGENT", "agent_xyz", "QUARANTINE"
            )
            with pytest.raises(EnterpriseError) as exc_mismatch:
                await svc.execute_emergency_containment(
                    actor,
                    org_id=org_id,
                    target_type="ORGANIZATION",
                    target_id=org_id,
                    containment_action="LOCKDOWN",
                    reason="Digest mismatch injection",
                    webauthn_assertion=agent_assertion,
                )
            assert exc_mismatch.value.code == "WEBAUTHN_ASSERTION_INVALID"

            # 2. Replay attack: Execute successfully once, replaying the same assertion must fail
            org_assertion = await _create_test_assertion(
                svc, engine, actor, org_id, "ORGANIZATION", org_id, "LOCKDOWN"
            )
            res1 = await svc.execute_emergency_containment(
                actor,
                org_id=org_id,
                target_type="ORGANIZATION",
                target_id=org_id,
                containment_action="LOCKDOWN",
                reason="First legitimate execution",
                webauthn_assertion=org_assertion,
            )
            assert res1["status"] == "CONTAINED"

            # Replay attempt
            with pytest.raises(EnterpriseError) as exc_replay:
                await svc.execute_emergency_containment(
                    actor,
                    org_id=org_id,
                    target_type="ORGANIZATION",
                    target_id=org_id,
                    containment_action="LOCKDOWN",
                    reason="Replayed assertion attempt",
                    webauthn_assertion=org_assertion,
                )
            assert exc_replay.value.code == "WEBAUTHN_CHALLENGE_REPLAY"
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_termination_failure_marks_unresolved(monkeypatch):
    """P0-03: Injected termination failure must return UNRESOLVED and persist UNRESOLVED in DB and audit."""
    async for url in isolated_pg_url("wp_m13s_p03_fail"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            svc = CustomerAuthorityService(engine)
            assertion = await _create_test_assertion(
                svc, engine, actor, org_id, "ORGANIZATION", org_id, "LOCKDOWN"
            )

            # Inject in-flight termination failure
            terminate_mock = AsyncMock(side_effect=RuntimeError("simulated kill failure"))
            monkeypatch.setattr(
                InFlightExecutionRegistry.get_instance(),
                "terminate_in_flight",
                terminate_mock,
            )

            res = await svc.execute_emergency_containment(
                actor,
                org_id=org_id,
                target_type="ORGANIZATION",
                target_id=org_id,
                containment_action="LOCKDOWN",
                reason="Adversarial termination failure test",
                webauthn_assertion=assertion,
            )
            terminate_mock.assert_awaited_once()

            # Must NEVER report CONTAINED
            assert res["status"] == "UNRESOLVED"
            assert res["status"] != "CONTAINED"
            assert "simulated kill failure" in res.get("termination_error", "")

            # Verify in PostgreSQL database
            async with engine.raw.connect() as conn:
                record = (
                    await conn.execute(
                        select(authority_containment_records).where(
                            authority_containment_records.c.id == res["containment_id"]
                        )
                    )
                ).first()
                assert record is not None
                assert record.status == "UNRESOLVED"
                assert record.status != "CONTAINED"

                audit_row = (
                    await conn.execute(
                        select(enterprise_security_audit).where(
                            enterprise_security_audit.c.action == "EMERGENCY_CONTAINMENT_EXECUTED",
                            enterprise_security_audit.c.org_id == org_id,
                        )
                    )
                ).first()
                assert audit_row is not None
                assert audit_row.result == "UNRESOLVED"
                assert audit_row.result != "SUCCESS"
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_unresolved_inflight_count_marks_unresolved(monkeypatch):
    """P0-03: Surviving in-flight executions must return and record UNRESOLVED."""
    async for url in isolated_pg_url("wp_m13s_p03_count"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            svc = CustomerAuthorityService(engine)
            assertion = await _create_test_assertion(
                svc, engine, actor, org_id, "ORGANIZATION", org_id, "LOCKDOWN"
            )

            # Mock termination without exception, but count_unresolved returns > 0
            terminate_mock = AsyncMock(return_value=None)
            monkeypatch.setattr(
                InFlightExecutionRegistry.get_instance(),
                "terminate_in_flight",
                terminate_mock,
            )
            monkeypatch.setattr(
                InFlightExecutionRegistry.get_instance(),
                "count_unresolved",
                lambda oid: 3,
            )

            res = await svc.execute_emergency_containment(
                actor,
                org_id=org_id,
                target_type="ORGANIZATION",
                target_id=org_id,
                containment_action="LOCKDOWN",
                reason="Adversarial surviving in-flight tasks test",
                webauthn_assertion=assertion,
            )
            terminate_mock.assert_awaited_once()

            # Must NEVER report CONTAINED
            assert res["status"] == "UNRESOLVED"
            assert res["status"] != "CONTAINED"

            # Verify in PostgreSQL database
            async with engine.raw.connect() as conn:
                record = (
                    await conn.execute(
                        select(authority_containment_records).where(
                            authority_containment_records.c.id == res["containment_id"]
                        )
                    )
                ).first()
                assert record is not None
                assert record.status == "UNRESOLVED"

                audit_row = (
                    await conn.execute(
                        select(enterprise_security_audit).where(
                            enterprise_security_audit.c.action == "EMERGENCY_CONTAINMENT_EXECUTED",
                            enterprise_security_audit.c.org_id == org_id,
                        )
                    )
                ).first()
                assert audit_row is not None
                assert audit_row.result == "UNRESOLVED"
        finally:
            await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_confirmed_containment_success():
    """P0-03 Happy Path: When termination is clean, status is confirmed CONTAINED."""
    async for url in isolated_pg_url("wp_m13s_p03_ok"):
        engine, actor, user_id, org_id = await _setup_postgres_workspace(url)
        try:
            svc = CustomerAuthorityService(engine)
            assertion = await _create_test_assertion(
                svc, engine, actor, org_id, "ORGANIZATION", org_id, "LOCKDOWN"
            )

            res = await svc.execute_emergency_containment(
                actor,
                org_id=org_id,
                target_type="ORGANIZATION",
                target_id=org_id,
                containment_action="LOCKDOWN",
                reason="Legitimate clean containment",
                webauthn_assertion=assertion,
            )

            assert res["status"] == "CONTAINED"

            # Verify in PostgreSQL database
            async with engine.raw.connect() as conn:
                record = (
                    await conn.execute(
                        select(authority_containment_records).where(
                            authority_containment_records.c.id == res["containment_id"]
                        )
                    )
                ).first()
                assert record is not None
                assert record.status == "CONTAINED"

                audit_row = (
                    await conn.execute(
                        select(enterprise_security_audit).where(
                            enterprise_security_audit.c.action == "EMERGENCY_CONTAINMENT_EXECUTED",
                            enterprise_security_audit.c.org_id == org_id,
                        )
                    )
                ).first()
                assert audit_row is not None
                assert audit_row.result == "SUCCESS"
        finally:
            await engine.close()
