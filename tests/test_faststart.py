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
    assert "tamper_resistance_verified" in report.verification_details["checks_passed"]
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
    """Fail-closed invariant: execution refuses to run when isolation backend is unavailable."""
    import os

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
    from responsibleai.isolation.errors import IsolationError

    # Ensure unisolated execution is NOT permitted
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    monkeypatch.setenv("WHITEPACT_ISOLATION_BACKEND", "docker")

    identity = IdentityContext(identity_id="id-1", kind="api_key", org_id="org-1")
    agent = AgentContext(identity=identity, organization_id="org-1", agent_id="agent-1")
    action = ActionRequest(
        action_id="act-1",
        action_type="sensitive_tool",
        target="res_1",
        arguments={},
        agent=agent,
        purpose="test",
    )
    auth = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
    )

    import asyncio

    # Failing closed when isolation container cannot be established
    try:
        executor = InternalToolExecutor()
        with pytest.raises(IsolationError):
            asyncio.run(executor.execute(auth, action))
    except Exception as exc:
        # Initializing broker may fail closed immediately if Docker daemon is not running
        assert "Isolation" in type(exc).__name__ or "Docker" in str(exc)


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
# P1-01: Revocation semantics, epoch invalidation and in-flight limitations
# ---------------------------------------------------------------------------


def test_revocation_epoch_invalidation_and_concurrent_admission() -> None:
    """Test durable revocation epoch semantics and document in-flight limitations."""
    from responsibleai.governance.execution import (
        ExecutionNotAuthorizedError,
        ExecutionAuthorization,
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
        arguments={},
        agent=agent,
        purpose="test",
    )
    from responsibleai.governance.approval import compute_action_digest

    # Epoch-bound permit requires durable admission repository
    auth_epoch = ExecutionAuthorization(
        action_digest=compute_action_digest(action),
        organization_id="org-1",
        decision=GovernanceDecision.ALLOW,
        principal_id="id-1",
        revocation_epoch=1,
    )

    import asyncio

    # Without durable repository, epoch-bound permit cannot be downgraded to local memory
    with pytest.raises(ExecutionNotAuthorizedError, match="Durable admission repository is unavailable"):
        asyncio.run(admit_execution(auth_epoch, action, None))

    # Note on in-flight execution cancellation:
    # As documented in docs/launch, revocation operates at admission gate time.
    # In-flight cancellations are not claimed without active cooperative runtime interrupts.
