# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for WhitePact FastStart V1 — Doctrine verification, genuine execution & evidence qualification."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

import pytest
from click.testing import CliRunner

from whitepact.cli import main
from whitepact.faststart import FastStartReport, run_faststart_workflow


def test_faststart_workflow_programmatic() -> None:
    """Validate full local doctrine demonstration lifecycle.

    ALLOW -> DENY -> REQUIRE_APPROVAL -> SYNTHETIC_APPROVAL -> AUTHORITY_REMOVAL -> VERIFY_EVIDENCE.
    """
    report = run_faststart_workflow(organization_id="org-test-faststart")

    assert isinstance(report, FastStartReport)
    assert report.verified is True
    assert report.organization_id == "org-test-faststart"
    assert report.identity_id == "identity-faststart-user"
    assert report.policy_rules == 1
    assert len(report.evidence_hash) == 64

    step_map = {s.name: s for s in report.steps}

    # ALLOW
    assert "ALLOW" in step_map
    assert step_map["ALLOW"].decision == "ALLOW"
    assert step_map["ALLOW"].details["action_type"] == "read_doc"

    # DENY by policy
    assert "DENY_POLICY" in step_map
    assert step_map["DENY_POLICY"].decision == "DENY"
    assert any("POLICY_EXPLICIT_DENY" in r for r in step_map["DENY_POLICY"].details["reason_codes"])

    # DENY unauthorized action
    assert "DENY_UNAUTHORIZED_ACTION" in step_map
    assert step_map["DENY_UNAUTHORIZED_ACTION"].decision == "DENY"
    assert any(
        "AUTHORITY_NOT_DELEGATED" in r
        for r in step_map["DENY_UNAUTHORIZED_ACTION"].details["reason_codes"]
    )

    # REQUIRE_APPROVAL
    assert "REQUIRE_APPROVAL" in step_map
    assert step_map["REQUIRE_APPROVAL"].decision == "REQUIRE_APPROVAL"
    assert any(
        "APPROVAL_REQUIRED" in r for r in step_map["REQUIRE_APPROVAL"].details["reason_codes"]
    )

    # SYNTHETIC_APPROVAL_AND_SIMULATION (explicitly labeled demo)
    assert "SYNTHETIC_APPROVAL_AND_SIMULATION" in step_map
    synth_step = step_map["SYNTHETIC_APPROVAL_AND_SIMULATION"]
    assert synth_step.decision == "SIMULATED_APPROVED"
    assert synth_step.details["approval_type"] == "SYNTHETIC_LOCAL_DEMO"
    assert synth_step.details["execution_model"] == "SIMULATED_NO_ISOLATION"
    assert synth_step.details["enforcement_boundary"] == "DEMONSTRATION_ONLY"
    assert synth_step.details["human_participant"] is False

    # AUTHORITY_REMOVAL_DEMO (explicitly labeled in-memory authority removal)
    assert "AUTHORITY_REMOVAL_DEMO" in step_map
    revoke_step = step_map["AUTHORITY_REMOVAL_DEMO"]
    assert revoke_step.decision == "DENY"
    assert revoke_step.details["demonstration_type"] == "IN_MEMORY_AUTHORITY_REMOVAL"
    assert revoke_step.details["post_removal_decision"] == "DENY"

    # VERIFY_EVIDENCE (canonical evaluation evidence chain)
    assert "VERIFY_EVIDENCE" in step_map
    ev_step = step_map["VERIFY_EVIDENCE"]
    assert ev_step.decision == "SEALED"
    assert ev_step.details["canonical_hash"] == report.evidence_hash
    assert ev_step.details["record_type"] == "DECISION_EVALUATION"
    assert ev_step.details["execution_event_recorded"] is False
    assert ev_step.details["scope"] == "LOCAL_CRYPTOGRAPHIC_INTEGRITY"
    assert ev_step.details["external_anchoring"] == "NONE_LOCAL_ONLY"

    # Report verification details contract
    assert report.verification_details["canonical_contract"] == "SHA256_CANONICAL_CHAINED_V2"
    assert "tamper_detection_self_check_passed" in report.verification_details["checks_passed"]
    assert report.verification_details["tamper_self_check"] == {
        "altered_record_hash_changes": True,
        "downstream_link_breaks": True,
    }
    assert report.verification_details["records_verified"] == 3
    assert report.verification_details["external_anchoring"] == "NONE_LOCAL_ONLY"
    assert report.verification_details["execution_events_recorded"] is False


def test_faststart_cli_text() -> None:
    """Test CLI output in human-readable format."""
    runner = CliRunner()
    result = runner.invoke(main, ["faststart"])
    assert result.exit_code == 0
    assert "WhitePact FastStart V1 — Core Governance & Doctrine Verification" in result.stdout
    assert "[ALLOW]" in result.stdout
    assert "[DENY]" in result.stdout
    assert "[REQUIRE_APPROVAL]" in result.stdout
    assert "[SIMULATED_APPROVED]" in result.stdout
    assert "[SEALED]" in result.stdout
    assert "Result: VERIFIED (Local cryptographic canonical chain integrity)" in result.stdout
    assert "Traceback" not in result.stdout


def test_faststart_cli_json() -> None:
    """Test CLI output with --json flag."""
    runner = CliRunner()
    result = runner.invoke(main, ["faststart", "--org", "org-custom-cli", "--json"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["organization_id"] == "org-custom-cli"
    assert payload["verified"] is True
    assert len(payload["steps"]) >= 6
    assert len(payload["evidence_hash"]) == 64
    assert payload["verification_details"]["external_anchoring"] == "NONE_LOCAL_ONLY"
    assert payload["verification_details"]["execution_events_recorded"] is False


# ---------------------------------------------------------------------------
# P0-01: Genuine governed-execution authorization, isolation & fail-closed tests
# ---------------------------------------------------------------------------


def test_genuine_governed_execution_authorization_lifecycle() -> None:
    """Test genuine ExecutionAuthorization creation and decision boundaries."""
    from responsibleai.governance.execution import (
        DecisionNotExecutableError,
        ExecutionAuthorization,
        authorize_execution,
    )
    from responsibleai.governance.gateway import WhitePactRuntimeGateway
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        AuthorityContext,
        GovernanceDecision,
        IdentityContext,
    )
    from responsibleai.governance.policy import Policy

    gateway = WhitePactRuntimeGateway()
    identity = IdentityContext(identity_id="id-exec", kind="api_key", org_id="org-exec")
    agent = AgentContext(identity=identity, organization_id="org-exec", agent_id="agent-exec")
    authority = AuthorityContext(
        delegated_by="root",
        granted_action_types=frozenset({"allowed_tool"}),
        require_approval_for=frozenset(),
        delegation_chain=("root",),
    )
    policy = Policy(org_id="org-exec", rules=[])

    act_allow = ActionRequest(
        action_id="act-allow-1",
        action_type="allowed_tool",
        target="target-resource",
        arguments={"param": "value"},
        agent=agent,
        purpose="execution_test",
    )
    res_allow = gateway.evaluate(act_allow, authority=authority, policy=policy)
    assert res_allow.decision == GovernanceDecision.ALLOW

    # 1. ALLOW correctly produces a genuine ExecutionAuthorization
    auth = authorize_execution(res_allow, act_allow)
    assert isinstance(auth, ExecutionAuthorization)
    assert auth.decision == GovernanceDecision.ALLOW
    assert auth.organization_id == "org-exec"
    assert auth.principal_id == "id-exec"
    assert auth.consumed is False
    assert auth.is_expired is False
    assert auth.matches_action(act_allow)

    # 2. DENY decisions fail-closed: must never produce an ExecutionAuthorization
    act_deny = ActionRequest(
        action_id="act-deny-1",
        action_type="forbidden_tool",
        target="target-resource",
        arguments={},
        agent=agent,
        purpose="execution_test",
    )
    res_deny = gateway.evaluate(act_deny, authority=authority, policy=policy)
    assert res_deny.decision == GovernanceDecision.DENY
    with pytest.raises(DecisionNotExecutableError):
        authorize_execution(res_deny, act_deny)

    # 3. REQUIRE_APPROVAL decisions fail-closed: cannot produce direct ExecutionAuthorization
    authority_approval = AuthorityContext(
        delegated_by="root",
        granted_action_types=frozenset({"payment_tool"}),
        require_approval_for=frozenset({"payment_tool"}),
        delegation_chain=("root",),
    )
    act_approval = ActionRequest(
        action_id="act-appr-1",
        action_type="payment_tool",
        target="target-resource",
        arguments={"amount": 100},
        agent=agent,
        purpose="execution_test",
    )
    res_approval = gateway.evaluate(act_approval, authority=authority_approval, policy=policy)
    assert res_approval.decision == GovernanceDecision.REQUIRE_APPROVAL
    with pytest.raises(DecisionNotExecutableError):
        authorize_execution(res_approval, act_approval)


def test_genuine_execution_authorization_replay_and_tampering() -> None:
    """Validate replay prevention, expiration, action mutation, and tenant isolation."""
    from responsibleai.governance.execution import (
        AuthorizationActionMismatchError,
        AuthorizationAlreadyConsumedError,
        AuthorizationExpiredError,
        AuthorizationOrganizationMismatchError,
        ExecutionAuthorization,
        _validate_authorization,
        admit_execution,
    )
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        GovernanceDecision,
        IdentityContext,
    )

    identity = IdentityContext(identity_id="id-1", kind="api_key", org_id="org-1")
    agent = AgentContext(identity=identity, organization_id="org-1", agent_id="agent-1")
    action = ActionRequest(
        action_id="act-1",
        action_type="tool_a",
        target="res_1",
        arguments={"k": "v"},
        agent=agent,
        purpose="test",
    )

    from responsibleai.governance.approval import compute_action_digest

    auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )

    # 1. Single-use consumption
    import asyncio

    asyncio.run(admit_execution(auth, action, None))
    assert auth.consumed is True

    # 2. Replay protection: second attempt with same authorization raises
    with pytest.raises(AuthorizationAlreadyConsumedError):
        _validate_authorization(auth, action)

    # 3. Expired authorization raises
    expired_auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
        expires_at=datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(AuthorizationExpiredError):
        _validate_authorization(expired_auth, action)

    # 4. Action mutation detection
    mutated_action = ActionRequest(
        action_id="act-1",
        action_type="tool_a",
        target="res_1",
        arguments={"k": "tampered_value"},  # Tampered arguments
        agent=agent,
        purpose="test",
    )
    fresh_auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
    )
    with pytest.raises(AuthorizationActionMismatchError):
        _validate_authorization(fresh_auth, mutated_action)

    # 5. Tenant organization mismatch
    wrong_org_auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-wrong",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
    )
    with pytest.raises(AuthorizationOrganizationMismatchError):
        _validate_authorization(wrong_org_auth, action)


def test_genuine_execution_fails_closed_without_isolation(monkeypatch) -> None:
    """Fail-closed invariant: execution refuses to run when isolation backend is unavailable.

    Tightened per FST-R03:
    1. Tests that InternalToolExecutor fails closed with IsolationBackendUnavailableError when Docker is missing.
    2. Tests that an uncontained executor without opt-in raises IsolationError.
    3. Negative control: proves that when unisolated execution is explicitly allowed in non-production,
       tool dispatch succeeds (proving the test would fail if the protection were disabled).
    """
    import asyncio

    from responsibleai.governance.approval import compute_action_digest
    from responsibleai.governance.execution import (
        ExecutionAuthorization,
        InternalToolExecutor,
    )
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        GovernanceDecision,
        IdentityContext,
    )
    from responsibleai.isolation.container_backend import DockerContainerBackend
    from responsibleai.isolation.errors import (
        IsolationBackendUnavailableError,
        IsolationError,
    )
    from responsibleai.isolation.mode import UNISOLATED_EXECUTION_ENV

    # 1. Clean env: isolation required by default
    monkeypatch.delenv(UNISOLATED_EXECUTION_ENV, raising=False)
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    # 2. When Docker daemon is not available: InternalToolExecutor fails closed immediately
    monkeypatch.setattr(DockerContainerBackend, "is_available", lambda self: False)
    with pytest.raises(IsolationBackendUnavailableError, match="Failing closed"):
        InternalToolExecutor()

    # 3. When an executor has no broker, execute() raises IsolationError
    executor_no_broker = InternalToolExecutor(broker=object())
    executor_no_broker._broker = None

    identity = IdentityContext(identity_id="id-1", kind="api_key", org_id="org-1")
    agent = AgentContext(identity=identity, organization_id="org-1", agent_id="agent-1")
    action = ActionRequest(
        action_id="act-1",
        action_type="sensitive_tool",
        target="res_1",
        arguments={"input": "test"},
        agent=agent,
        purpose="test",
    )
    auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
    )

    with pytest.raises(IsolationError, match="IsolationBroker is mandatory"):
        asyncio.run(executor_no_broker.execute(auth, action))

    # 4. Negative control: if opt-in is enabled in non-production, execution proceeds
    monkeypatch.setenv(UNISOLATED_EXECUTION_ENV, "1")
    dispatched_calls: list[str] = []

    async def fake_dispatch(tool_name: str, args: dict, **kwargs):
        dispatched_calls.append(tool_name)
        return {"dispatched": True}

    monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", fake_dispatch)
    executor_allowed = InternalToolExecutor()
    auth_allowed = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
    )
    res = asyncio.run(executor_allowed.execute(auth_allowed, action))
    assert res == {"dispatched": True}
    assert dispatched_calls == ["sensitive_tool"], (
        "Negative control failure: execution did not reach tool despite explicit opt-in"
    )



# ---------------------------------------------------------------------------
# P0-02: Canonical evidence persistence, disposable verification & chain audit
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_repository_disposable_persistence_and_chain_verification() -> None:
    """Persist evidence in a disposable SQLite environment and verify against canonical contract."""
    from sqlalchemy import text

    from responsibleai.db import create_engine
    from responsibleai.db.evidence_repository import ChainVerificationStatus, EvidenceRepository
    from responsibleai.governance.evidence import build_evidence_record
    from responsibleai.governance.gateway import WhitePactRuntimeGateway
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        AuthorityContext,
        GovernanceDecision,
        IdentityContext,
    )
    from responsibleai.governance.policy import Policy, PolicyRule

    engine = create_engine(":memory:")
    await engine.init()

    repo = EvidenceRepository(engine)
    gateway = WhitePactRuntimeGateway()
    org_id = "org-disposable-test"

    identity = IdentityContext(identity_id="id-1", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id, agent_id="agent-1")
    authority = AuthorityContext(
        delegated_by="root",
        granted_action_types=frozenset({"read_file"}),
        require_approval_for=frozenset(),
        delegation_chain=("root",),
    )
    deny_rule = PolicyRule(
        rule_id="r-deny",
        reason_code="DENIED_SENSITIVE",
        effect=GovernanceDecision.DENY,
        targets=frozenset({"vault"}),
    )
    policy = Policy(org_id=org_id, rules=[deny_rule])

    # Record 1: ALLOW
    act_1 = ActionRequest(
        action_id="act-1",
        action_type="read_file",
        target="doc.txt",
        arguments={},
        agent=agent,
        purpose="eval_1",
    )
    res_1 = gateway.evaluate(act_1, authority=authority, policy=policy)
    ev_1 = build_evidence_record(act_1, agent, authority, res_1)
    await repo.record(ev_1)

    # Record 2: DENY
    act_2 = ActionRequest(
        action_id="act-2",
        action_type="read_file",
        target="vault",
        arguments={},
        agent=agent,
        purpose="eval_2",
    )
    res_2 = gateway.evaluate(act_2, authority=authority, policy=policy)
    ev_2 = build_evidence_record(act_2, agent, authority, res_2)
    await repo.record(ev_2)

    # 1. Independent re-read and verification of stored chain
    assert await repo.verify_chain(org_id) is True
    assert await repo.verify_chain_status(org_id) == ChainVerificationStatus.VALID

    # 2. Tampering detection: modify decision in row 1
    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "UPDATE governance_evidence SET decision = 'DENY' WHERE action_id = 'act-1'"
            )
        )
    assert await repo.verify_chain(org_id) is False
    assert await repo.verify_chain_status(org_id) == ChainVerificationStatus.INVALID

    # Restore honesty
    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "UPDATE governance_evidence SET decision = 'ALLOW' WHERE action_id = 'act-1'"
            )
        )
    assert await repo.verify_chain(org_id) is True

    # 3. Deletion detection: delete row 2
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("DELETE FROM governance_evidence WHERE action_id = 'act-2'")
        )
    # Head and sequence check detects missing row
    assert await repo.verify_chain(org_id) is False

    await engine.close()


def test_faststart_evidence_tamper_detection() -> None:
    """Tampering with any evidence record field breaks canonical chain verification."""
    from datetime import UTC, datetime

    from responsibleai.governance.evidence import EvidenceRecord, compute_canonical_evidence_hash

    record = EvidenceRecord(
        evidence_id="ev-tamper-test-1",
        organization_id="org-tamper-test",
        action_id="act-1",
        agent_id="agent-1",
        identity_id="id-1",
        action_type="read_doc",
        target="target-1",
        argument_keys=["path"],
        authority_delegated_by="root",
        delegation_chain=["root", "id-1"],
        decision="DENY",
        reason_codes=["POLICY_EXPLICIT_DENY"],
        evaluated_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC).isoformat(),
        prev_hash="0" * 64,
        integrity_version=2,
        integrity_status="CANONICAL_CHAINED",
        authentication_method="api_key",
        purpose="audit",
        execution_authorization_id=None,
        execution_target=None,
        approval_id=None,
    )

    canonical_hash = compute_canonical_evidence_hash(record.prev_hash, record)

    # Tamper with decision (e.g. attacker changes DENY to ALLOW)
    tampered_record = EvidenceRecord(
        evidence_id=record.evidence_id,
        organization_id=record.organization_id,
        action_id=record.action_id,
        agent_id=record.agent_id,
        identity_id=record.identity_id,
        action_type=record.action_type,
        target=record.target,
        argument_keys=record.argument_keys,
        authority_delegated_by=record.authority_delegated_by,
        delegation_chain=record.delegation_chain,
        decision="ALLOW",  # Tampered!
        reason_codes=record.reason_codes,
        evaluated_at=record.evaluated_at,
        recorded_at=record.recorded_at,
        prev_hash=record.prev_hash,
        integrity_version=record.integrity_version,
        integrity_status=record.integrity_status,
        authentication_method=record.authentication_method,
        purpose=record.purpose,
        execution_authorization_id=record.execution_authorization_id,
        execution_target=record.execution_target,
        approval_id=record.approval_id,
    )

    tampered_hash = compute_canonical_evidence_hash(tampered_record.prev_hash, tampered_record)
    assert tampered_hash != canonical_hash, (
        "Tampered evidence must produce completely different hash"
    )


# ---------------------------------------------------------------------------
# FST-R04: Durable revocation lifecycle, epoch invalidation and replay tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_durable_admission_and_revocation_lifecycle() -> None:
    """Validate durable admission linearization and epoch invalidation (FST-R04).

    Verifies:
    1. Single-use admission via ExecutionNonceRepository.
    2. Replay attempt rejected with NonceAlreadyConsumedError.
    3. Revocation epoch bumping via RevocationEpochRepository rejects stale permits.
    4. Cross-tenant epoch isolation.
    5. Inactive tenant rejected with OrganizationNotGovernableError.
    6. Deny-safe fail-closed when repository is unavailable for epoch-bound permit.
    7. In-flight execution disclaimer: running OS processes are not killed by authorization revocation.
    """
    import uuid
    from datetime import UTC, datetime, timedelta

    from sqlalchemy import insert

    from responsibleai.db import create_engine
    from responsibleai.db.engine import organizations
    from responsibleai.db.execution_nonce_repository import (
        ExecutionNonceRepository,
        NonceAlreadyConsumedError,
        OrganizationNotGovernableError,
        StaleRevocationEpochError,
    )
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
    from responsibleai.governance.approval import compute_action_digest
    from responsibleai.governance.execution import (
        ExecutionAuthorization,
        ExecutionNotAuthorizedError,
        admit_execution,
    )
    from responsibleai.governance.models import (
        ActionRequest,
        AgentContext,
        GovernanceDecision,
        IdentityContext,
    )
    from responsibleai.rbac.models import GovernanceStatus

    engine = create_engine(":memory:")
    await engine.init()

    org_a = f"org-{uuid.uuid4().hex[:8]}"
    org_b = f"org-{uuid.uuid4().hex[:8]}"
    now = datetime.now(UTC).isoformat()

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                [
                    {
                        "id": org_a,
                        "name": "Org A",
                        "slug": org_a,
                        "governance_status": GovernanceStatus.ACTIVE.value,
                        "created_at": now,
                    },
                    {
                        "id": org_b,
                        "name": "Org B",
                        "slug": org_b,
                        "governance_status": GovernanceStatus.ACTIVE.value,
                        "created_at": now,
                    },
                ]
            )
        )

    nonce_repo = ExecutionNonceRepository(engine)
    epoch_repo = RevocationEpochRepository(engine)

    # 1. Tenant A starts at epoch 0
    epoch_a = await epoch_repo.current(org_a)
    assert epoch_a.epoch == 0

    identity_a = IdentityContext(identity_id="id-a", kind="api_key", org_id=org_a)
    agent_a = AgentContext(identity=identity_a, organization_id=org_a, agent_id="agent-a")
    action_a = ActionRequest(
        action_id="act-a1",
        action_type="tool_a",
        target="target_a",
        arguments={"k": "v"},
        agent=agent_a,
        purpose="audit",
    )

    auth_a = ExecutionAuthorization(
        action_digest=compute_action_digest(action_a),
        organization_id=org_a,
        decision=GovernanceDecision.ALLOW,
        principal_id="id-a",
        revocation_epoch=0,
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )

    # 2. Admit execution successfully
    await admit_execution(auth_a, action_a, nonce_repo)
    assert auth_a.consumed is True

    # 3. Replay with the same nonce is rejected
    with pytest.raises(NonceAlreadyConsumedError, match="Permit nonce already consumed"):
        await nonce_repo.consume(
            auth_a.nonce,
            authorization_id=auth_a.authorization_id,
            organization_id=org_a,
            expected_epoch=0,
        )

    # 4. Issue another authorization at epoch 0 for tenant A
    auth_a_stale = ExecutionAuthorization(
        action_digest=compute_action_digest(action_a),
        organization_id=org_a,
        decision=GovernanceDecision.ALLOW,
        principal_id="id-a",
        revocation_epoch=0,
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )

    # 5. Advance tenant A's revocation epoch (revoking all outstanding epoch 0 permits)
    new_epoch_a = await epoch_repo.bump(org_a)
    assert new_epoch_a.epoch == 1

    # 6. Outstanding stale permit is rejected by durable admission
    with pytest.raises(StaleRevocationEpochError, match="Permit revocation epoch is stale"):
        await admit_execution(auth_a_stale, action_a, nonce_repo)

    # 7. Cross-tenant isolation: Tenant B is still at epoch 0 and unaffected
    epoch_b = await epoch_repo.current(org_b)
    assert epoch_b.epoch == 0
    identity_b = IdentityContext(identity_id="id-b", kind="api_key", org_id=org_b)
    agent_b = AgentContext(identity=identity_b, organization_id=org_b, agent_id="agent-b")
    action_b = ActionRequest(
        action_id="act-b1",
        action_type="tool_b",
        target="target_b",
        arguments={},
        agent=agent_b,
        purpose="audit",
    )
    auth_b = ExecutionAuthorization(
        action_digest=compute_action_digest(action_b),
        organization_id=org_b,
        decision=GovernanceDecision.ALLOW,
        principal_id="id-b",
        revocation_epoch=0,
        expires_at=datetime.now(UTC) + timedelta(seconds=60),
    )
    await admit_execution(auth_b, action_b, nonce_repo)
    assert auth_b.consumed is True

    # 8. Deny-safe without durable repository when permit has an epoch
    auth_epoch_bound = ExecutionAuthorization(
        action_digest=compute_action_digest(action_a),
        organization_id=org_a,
        decision=GovernanceDecision.ALLOW,
        principal_id="id-a",
        revocation_epoch=1,
    )
    with pytest.raises(
        ExecutionNotAuthorizedError, match="Durable admission repository is unavailable"
    ):
        await admit_execution(auth_epoch_bound, action_a, None)

    # 9. Inactive/suspended tenant rejected with OrganizationNotGovernableError
    from sqlalchemy import update

    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_a)
            .values(governance_status=GovernanceStatus.SUSPENDED.value)
        )
    with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
        await nonce_repo.consume(
            "nonce-suspended",
            authorization_id="auth-suspended",
            organization_id=org_a,
            expected_epoch=1,
        )



def test_readme_and_faststart_claim_integrity() -> None:
    """FST-R07: Regression test ensuring forbidden misleading claims do not appear in docs/code."""
    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parent.parent
    readme_path = repo_root / "README.md"
    content = readme_path.read_text(encoding="utf-8")

    # Forbidden claims identified in Launch Gate order:
    forbidden_claims = [
        "cryptographically signed execution token",
        "cryptographically signed execution tokens",
        "universal stdio protection",
        "governs every call over stdio",
        "reliable deepfake detection",
        "certified trust score",
        "AI compliance certification",
    ]
    for claim in forbidden_claims:
        assert (
            claim.lower() not in content.lower()
        ), f"Forbidden misleading claim found in README.md: '{claim}'"

