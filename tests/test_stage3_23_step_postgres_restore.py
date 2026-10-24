# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Separately identified modernization of the immutable historical restore attack.

Real PostgreSQL transport and independently signed offline recovery. Disposable
identity/root fixtures do not establish production enrollment or native Linux
containment. The original test and its failures remain independently preserved.
"""

import base64
import hashlib
import json
import secrets
import sqlite3
import uuid
from dataclasses import asdict
from datetime import UTC, datetime

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13i1_customer_journey import serve
from sdk.python.rai_client.governance import GovernanceRequestError, GovernanceRuntimeClient
from sqlalchemy import insert, text

import responsibleai.dashboard.app as dashboard
from responsibleai.data_governance.backup_defense import (
    LifecycleState,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    get_restore_readiness_gate,
    set_restore_readiness_gate,
)
from responsibleai.data_governance.deletion_orchestrator import TenantDeletionOrchestrator
from responsibleai.data_governance.operator_recovery import RecoveryManifest
from responsibleai.data_governance.operator_recovery_control import (
    assert_completed_binding,
    assert_database_recovery_binding,
)
from responsibleai.data_governance.provisioning_manifest import ProvisionerTrust
from responsibleai.data_governance.tenant_controller import (
    ProtectedTenantController,
    postgres_identity,
    store_b_identity,
)
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    PublicationAuthorizationLedger,
)
from responsibleai.db.engine import create_engine, eval_runs, governance_policies
from responsibleai.db.org_repository import OrgRepository
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.runtime.authority_kernel import AuthorityKernelError, Phase7AAuthorityKernel
from tests.stage3_controller_helpers import controller_process
from tests.stage3_restore_transport import (
    fence_restore_incident,
    offline_cli,
    postgres_snapshot,
    restarted_dashboard,
    write_signed_request,
)
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign
from tests.test_v1_customer_journey import (
    PURPOSE,
    _apply_idv,
    _onboard,
    _register,
    _token_from_url,
    _verify_login,
)


async def _count(engine, table, column, tenant):
    async with engine.raw.connect() as connection:
        return await connection.scalar(
            text(f"SELECT count(*) FROM {table} WHERE {column}=:tenant"), {"tenant": tenant}
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_modernized_23_step_postgres_restore_requires_signed_recovery(
    real_recovery, tmp_path, monkeypatch, seed_runtime_authority, request
):
    engine, provider, gate, profile, operators = real_recovery
    url = engine.raw.url.render_as_string(hide_password=False)
    observed = []
    previous = get_restore_readiness_gate()
    set_restore_readiness_gate(gate)
    new_engine = None
    try:
        # A distinct fixture incident, initialized before any recovery approval.
        incident_profile = json.loads(profile.read_text())
        incident_profile["incident_id"] = "restore-23-" + uuid.uuid4().hex
        profile = tmp_path / "restore-incident-profile.json"
        write_signed_request(profile, incident_profile)
        monkeypatch.setenv("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG", str(profile))
        # 1. Supported real PostgreSQL schema, not a SQLite substitute.
        async with engine.raw.connect() as connection:
            assert 160000 <= int(await connection.scalar(text("SHOW server_version_num"))) < 170000
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0067"
            )
            pg = await postgres_identity(connection)
        observed.append(1)
        # 2. Independently durable Store B, private nonproduction signing trust.
        assert provider.list_all() == []
        provider._secret_key = secrets.token_hex(32)
        controller_key = Ed25519PrivateKey.generate()
        trust = ProvisionerTrust(
            "restore-test-controller",
            controller_key.public_key().public_bytes_raw(),
            "restore-test",
            "staging",
            pg,
            store_b_identity(provider),
        )
        PendingTenantReservations(provider).initialize()
        PublicationAuthorizationLedger(provider).initialize(trust)
        service = ProtectedTenantController(engine, provider, trust, controller_key)
        monkeypatch.setenv("WHITEPACT_STORE_B_PATH", str(provider.path))
        monkeypatch.setenv("WHITEPACT_STORE_B_KEY", provider._secret_key)
        monkeypatch.setenv("WHITEPACT_OPERATOR_RECOVERY_DATABASE_URL", url)
        monkeypatch.setenv("WHITEPACT_ALLOW_SYNTHETIC_HOST_TOOL", "1")
        observed.append(2)
        for name, value in {
            "database_url": url,
            "auto_migrate": False,
            "auth_enabled": True,
            "api_keys": [],
            "web_auth_dev_tokens": True,
            "web_session_secure": False,
            "web_verification_delivery_url": None,
            "environment": "development",
        }.items():
            monkeypatch.setattr(dashboard.settings, name, value)
        monkeypatch.setattr(dashboard.limiter, "enabled", False)
        async with controller_process(service, monkeypatch) as child:
            controller_pid = child.pid
            async with serve(dashboard.app) as origin:
                async with httpx.AsyncClient(base_url=origin, timeout=30) as browser:
                    # 3. Genuine HTTP identity/session and protected onboarding.
                    email = f"restore-{uuid.uuid4().hex}@example.com"
                    registration_status, registration = await _register(
                        browser, name="Restore Owner", email=email
                    )
                    assert registration_status in {200, 201, 202}
                    assert "verification_url" in registration
                    csrf = await _verify_login(
                        browser, email, _token_from_url(registration["verification_url"])
                    )
                    session = await _onboard(browser, csrf, "Enterprise Delta Corp")
                    tenant = session["organization"]["id"]
                    user = session["user"]["id"]
                    org_name = session["organization"]["name"]
                    await _apply_idv(browser, user, "restore-identity")
                    generation = provider.get_state(tenant).generation_id
                    assert service.ledger.completion(tenant).generation_id == generation
                    assert await _count(engine, "web_sessions", "org_id", tenant) == 1
                    stale_cookies = dict(browser.cookies)
                    observed.append(3)
                    # 4. Real API-key endpoint and explicitly test-only root/consent.
                    response = await browser.post(
                        "/api/v1/web/api-keys",
                        headers={"X-WP-CSRF": browser.cookies["wp_csrf"]},
                        json={
                            "name": "restore-agent",
                            "environment": "test",
                            "scopes": ["governance:read", "governance:write", "evidence:read"],
                        },
                    )
                    assert response.status_code == 201
                    api_key = response.json()["api_key"]
                    context = await OrgRepository(engine).authenticate(api_key)
                    assert context is not None
                    await seed_runtime_authority(
                        engine,
                        organization_id=tenant,
                        principal_id=context.key_id,
                        action_types=(SYNTHETIC_COUNTER_TOOL,),
                        targets=(SYNTHETIC_COUNTER_TOOL,),
                        purpose=PURPOSE,
                    )
                    assert await _count(engine, "org_api_keys", "org_id", tenant) == 1
                    observed.append(4)
                    # 5. Pre-existing governance and erasable customer data.
                    async with engine.raw.begin() as connection:
                        now = datetime.now(UTC).isoformat()
                        await connection.execute(
                            insert(eval_runs).values(
                                id=uuid.uuid4().hex,
                                run_type="benchmark",
                                model="test-model",
                                provider="test",
                                suite="restore",
                                org_id=tenant,
                                created_at=now,
                                payload=json.dumps({"accuracy": 0.98}),
                            )
                        )
                        await connection.execute(
                            insert(governance_policies).values(
                                id=uuid.uuid4().hex,
                                org_id=tenant,
                                rule_id="r_confidential",
                                reason_code="RC_CONFIDENTIAL",
                                effect="ALLOW",
                                position=0,
                                created_at=now,
                                updated_at=now,
                            )
                        )
                    assert await _count(engine, "eval_runs", "org_id", tenant) == 1
                    observed.append(5)
                    # 6. Retain a real internal server-issued grant, never start
                    # a worker or apply its effect; this is a test authority fixture.
                    issued = await Phase7AAuthorityKernel(engine).issue(
                        organization_id=tenant,
                        principal_id=context.key_id,
                        agent_id=context.key_id,
                        identity_id=context.key_id,
                        intent=PURPOSE,
                        action_type=SYNTHETIC_COUNTER_TOOL,
                        target=SYNTHETIC_COUNTER_TOOL,
                        action_digest=hashlib.sha256(b"restore-action").hexdigest(),
                        canonical_action_payload="{}",
                        approved_arguments={},
                        idempotency_key=uuid.uuid4().hex,
                    )
                    assert issued.authorization_id
                    observed.append(6)
        assert child.poll() is not None  # Actual controller process is gone.
        # 7. Consistent custom-format PG snapshot of the real pre-deletion state.
        archive = tmp_path / "pre-deletion.dump"
        await postgres_snapshot(engine, archive)
        snapshot_digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        observed.append(7)
        # 8. Genuine deletion, not direct synthetic tombstone insertion.
        deletion = await TenantDeletionOrchestrator(engine, provider).delete_tenant(
            tenant,
            deleted_by=user,
            reason="23-step restore qualification",
        )
        assert deletion.verification_passed is True
        observed.append(8)
        # 9. Durable independent tombstone preserves original generation/floors.
        tombstone = provider.get_state(tenant)
        assert tombstone.state == LifecycleState.TOMBSTONED
        assert tombstone.generation_id == generation
        observed.append(9)
        # 10. Deleted credentials actually absent in post-deletion Store A.
        assert await _count(engine, "web_sessions", "org_id", tenant) == 0
        assert await _count(engine, "org_api_keys", "org_id", tenant) == 0
        observed.append(10)
        # 11. Close Store A connections and restore only the older Store A.
        fencing = await fence_restore_incident(engine, provider, profile)
        request.node.user_properties.append(("restore_fencing", json.dumps(fencing)))
        await engine.close()
        await postgres_snapshot(engine, archive, restore=True, provider=provider)
        assert hashlib.sha256(archive.read_bytes()).hexdigest() == snapshot_digest
        observed.append(11)
        # 12. Store B is NEVER copied back or reconstructed from Store A.
        assert provider.get_state(tenant) == tombstone
        observed.append(12)
        # 13. New connection initialization proves actual credential resurrection.
        new_engine = create_engine(url)
        async with new_engine.raw.connect() as connection:
            row = (
                await connection.execute(
                    text("SELECT name FROM organizations WHERE id=:tenant"), {"tenant": tenant}
                )
            ).one()
            assert row.name == org_name
        assert await _count(new_engine, "web_sessions", "org_id", tenant) == 1
        assert await _count(new_engine, "org_api_keys", "org_id", tenant) == 1
        assert await _count(new_engine, "tenant_tombstones", "org_id", tenant) == 0
        assert await _count(new_engine, "governance_policies", "org_id", tenant) == 1
        observed.append(13)
        # 14. Fresh Store B object and fail-closed gate, no direct READY call.
        restarted = SqliteDurableLifecycleStateProvider(
            provider.path, secret_key=provider._secret_key
        )
        assert restarted.get_state(tenant) == tombstone
        restarted_gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.RESTORE_PENDING,
            provider=restarted,
            db_engine=new_engine,
        )
        set_restore_readiness_gate(restarted_gate)
        with pytest.raises(RestoreQuarantineError):
            await restarted_gate.assert_current_traffic_admitted()
        with pytest.raises(AuthorityKernelError):
            await Phase7AAuthorityKernel(new_engine).acquire_lease(
                request_id=issued.request_id,
                worker_id="stale-worker",
                organization_id=tenant,
            )
        async with restarted_dashboard(url) as (blocked_origin, blocked_pid):
            blocked_sdk = GovernanceRuntimeClient(api_key, base_url=blocked_origin, timeout=30)
            with pytest.raises(GovernanceRequestError) as blocked:
                await blocked_sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
            assert blocked.value.status_code == 503
            async with httpx.AsyncClient(
                base_url=blocked_origin, cookies=stale_cookies, timeout=30
            ) as browser:
                assert (await browser.get("/api/v1/web/session")).status_code == 503
        observed.append(14)
        # Independent fresh requests for each negative attempt: a rejected
        # authorization is never relabelled or reused as a successful grant.
        negative_receipts = []
        for case in ("missing", "forged", "stale"):
            negative_plan = tmp_path / f"negative-{case}-plan.json"
            negative_signed = tmp_path / f"negative-{case}-signed.json"
            await offline_cli(profile, operation="prepare", output=negative_plan)
            negative_manifest = RecoveryManifest(
                **json.loads(negative_plan.read_text())["manifest"]
            )
            negative_approvals = sign(negative_manifest, operators)
            if case == "missing":
                negative_approvals.pop("security")
            elif case == "forged":
                negative_approvals["security"] = base64.b64encode(b"x" * 64).decode("ascii")
            else:
                # Explicit disposable-state freshness attack: retain native PG
                # type/precision; never erase or stringify timestamp evidence.
                async with new_engine.raw.begin() as connection:
                    await connection.execute(
                        text(
                            "UPDATE governance_execution_authorizations "
                            "SET expires_at=expires_at+interval '1 microsecond' "
                            "WHERE authorization_id=:authorization"
                        ),
                        {"authorization": issued.authorization_id},
                    )
            write_signed_request(
                negative_signed,
                {
                    "manifest": asdict(negative_manifest),
                    "signatures": negative_approvals,
                },
            )
            await offline_cli(
                profile, operation="execute", request=negative_signed, expect_rejection=True
            )
            with pytest.raises(RestoreQuarantineError):
                await restarted_gate.assert_current_traffic_admitted()
            assert restarted.get_readiness_state() != RestoreReadinessState.READY
            async with new_engine.raw.connect() as connection:
                assert (
                    await connection.scalar(
                        text("SELECT count(*) FROM test_consequential_counters")
                    )
                    == 0
                )
            negative_receipts.append(case)
        request.node.user_properties.append(
            ("rejected_recovery_cases", json.dumps(negative_receipts))
        )
        # 15. Newly launched prepare/execute processes, two distinct real fixture
        # signatures. No application-generated operator signature or direct engine call.
        envelope_path, signed_path = tmp_path / "prepared.json", tmp_path / "signed.json"
        prepared = await offline_cli(profile, operation="prepare", output=envelope_path)
        assert prepared["status"] == "PREPARED_NOT_AUTHORIZED"
        envelope = json.loads(envelope_path.read_text())
        manifest = RecoveryManifest(**envelope["manifest"])
        approvals = sign(manifest, operators)
        assert len(approvals) == 2 and len(set(approvals.values())) == 2
        write_signed_request(signed_path, {"manifest": asdict(manifest), "signatures": approvals})
        recovered = await offline_cli(profile, operation="execute", request=signed_path)
        assert recovered["status"] == "RECONCILED"
        assert recovered["reconciliation_id"]
        async with new_engine.raw.connect() as connection:
            report = (
                await connection.execute(
                    text(
                        "SELECT status,details_json FROM restore_reconciliation_records WHERE id=:id"
                    ),
                    {"id": recovered["reconciliation_id"]},
                )
            ).one()
            details = json.loads(report.details_json)
            assert report.status == "RECONCILED"
            assert tenant in details["quarantined_orgs"]
            assert details["revoked_sessions"] >= 1
            assert details["revoked_keys"] >= 1
            assert details["erased_records"] >= 1
        await offline_cli(profile, operation="execute", request=signed_path, expect_rejection=True)
        assert controller_pid > 0
        observed.append(15)
        # 16. Quarantined, schema-valid tenant, not authority restoration.
        async with new_engine.raw.connect() as connection:
            row = (
                await connection.execute(
                    text("SELECT name,governance_status FROM organizations WHERE id=:tenant"),
                    {"tenant": tenant},
                )
            ).one()
            assert "RESTORE_QUARANTINED" in row.name
            assert row.governance_status == "DISABLED"
        observed.append(16)
        # 17-20. Resurrected sessions, keys, erasable data, governance all removed.
        for objective, table in (
            (17, "web_sessions"),
            (18, "org_api_keys"),
            (19, "eval_runs"),
            (20, "governance_policies"),
        ):
            assert await _count(new_engine, table, "org_id", tenant) == 0
            observed.append(objective)
        # 21. Synchronized tombstone and monotonic revocation/root invalidation.
        assert await _count(new_engine, "tenant_tombstones", "org_id", tenant) == 1
        assert restarted.get_state(tenant).generation_id == generation
        async with new_engine.raw.connect() as connection:
            epoch = await connection.scalar(
                text(
                    "SELECT epoch FROM governance_revocation_epochs WHERE organization_id=:tenant AND scope='governance'"
                ),
                {"tenant": tenant},
            )
            assert epoch >= max(tombstone.security_epoch, tombstone.revocation_floor)
            assert (
                await connection.scalar(
                    text(
                        "SELECT count(*) FROM governance_root_authority_records WHERE organization_id=:tenant AND revoked_at IS NULL"
                    ),
                    {"tenant": tenant},
                )
                == 0
            )
        observed.append(21)
        # 22. Persisted signed completion/replay consumption and zero effect.
        assert assert_completed_binding(restarted)
        await assert_database_recovery_binding(new_engine)
        profile_data = json.loads(profile.read_text())
        with sqlite3.connect(profile_data["ledger_path"]) as connection:
            assert connection.execute(
                "SELECT phase FROM recovery_operations WHERE request_id=?", (manifest.request_id,)
            ).fetchone() == ("COMPLETE",)
            assert connection.execute(
                "SELECT state FROM recovery_receipts WHERE request_id=?", (manifest.request_id,)
            ).fetchone() == ("CONSUMED",)
        async with new_engine.raw.connect() as connection:
            assert (
                await connection.scalar(
                    text("SELECT COALESCE(sum(counter),0) FROM test_consequential_counters")
                )
                == 0
            )
            assert (
                await connection.scalar(
                    text(
                        "SELECT COALESCE(sum(downstream_call_count),0) FROM test_consequential_counters"
                    )
                )
                == 0
            )
        observed.append(22)
        # 23. Global readiness only through verified signed recovery, while this
        # deleted tenant's stale session, key, SDK request and grant remain denied.
        await restarted_gate.assert_current_traffic_admitted()
        assert restarted_gate.state == RestoreReadinessState.READY
        with pytest.raises(AuthorityKernelError):
            await Phase7AAuthorityKernel(new_engine).acquire_lease(
                request_id=issued.request_id,
                worker_id="revoked-worker",
                organization_id=tenant,
            )
        async with restarted_dashboard(url) as (origin, recovered_pid):
            assert recovered_pid != blocked_pid
            sdk = GovernanceRuntimeClient(api_key, base_url=origin, timeout=30)
            with pytest.raises(GovernanceRequestError) as denied:
                await sdk.call_tool(SYNTHETIC_COUNTER_TOOL, purpose=PURPOSE)
            assert denied.value.status_code == 401
            async with httpx.AsyncClient(
                base_url=origin, cookies=stale_cookies, timeout=30
            ) as browser:
                response = await browser.get("/api/v1/web/session")
                assert response.status_code == 401
        observed.append(23)
        assert observed == list(range(1, 24))
    finally:
        request.node.user_properties.append(("completed_restore_objectives", json.dumps(observed)))
        set_restore_readiness_gate(previous)
        if new_engine is not None:
            await new_engine.close()
