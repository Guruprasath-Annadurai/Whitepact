# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for WhitePact FastStart V1 — Ultra-fast verification and first protected action."""

from __future__ import annotations

import json

from click.testing import CliRunner

from whitepact.cli import main
from whitepact.faststart import FastStartReport, run_faststart_workflow


def test_faststart_workflow_programmatic() -> None:
    """Validate full lifecycle: ALLOW -> DENY -> REQUIRE_APPROVAL -> APPROVE -> EXECUTE -> REVOKE -> VERIFY EVIDENCE."""
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

    # APPROVE_AND_EXECUTE
    assert "APPROVE_AND_EXECUTE" in step_map
    assert step_map["APPROVE_AND_EXECUTE"].decision == "APPROVED"
    assert step_map["APPROVE_AND_EXECUTE"].details["execution_grant_id"].startswith("grant-")

    # REVOKE
    assert "REVOKE" in step_map
    assert step_map["REVOKE"].decision == "DENY"
    assert step_map["REVOKE"].details["post_revocation_decision"] == "DENY"

    # VERIFY_EVIDENCE
    assert "VERIFY_EVIDENCE" in step_map
    assert step_map["VERIFY_EVIDENCE"].decision == "SEALED"
    assert step_map["VERIFY_EVIDENCE"].details["canonical_hash"] == report.evidence_hash
    assert step_map["VERIFY_EVIDENCE"].details["integrity_status"] == "CANONICAL_CHAINED"


def test_faststart_cli_text() -> None:
    """Test CLI output in human-readable format."""
    runner = CliRunner()
    result = runner.invoke(main, ["faststart"])
    assert result.exit_code == 0
    assert "WhitePact FastStart V1 — Core Governance & Doctrine Verification" in result.stdout
    assert "[ALLOW]" in result.stdout
    assert "[DENY]" in result.stdout
    assert "[REQUIRE_APPROVAL]" in result.stdout
    assert "[APPROVED]" in result.stdout
    assert "[SEALED]" in result.stdout
    assert "Result: VERIFIED" in result.stdout
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


def test_faststart_fail_closed_on_unauthorized_and_unknown_action() -> None:
    """Enforcement fails closed when action is not explicitly authorized."""
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
    identity = IdentityContext(identity_id="id-user", kind="api_key", org_id="org-test")
    agent = AgentContext(identity=identity, organization_id="org-test", agent_id="agent-1")
    authority = AuthorityContext(
        delegated_by="root",
        granted_action_types=frozenset({"read_only"}),
        require_approval_for=frozenset(),
        delegation_chain=("root",),
    )
    policy = Policy(org_id="org-test", rules=[])

    # 1. Unlisted action type fails closed
    req = ActionRequest(
        action_id="act-unauth",
        action_type="delete_all",
        target="db",
        arguments={},
        agent=agent,
        purpose="test",
    )
    res = gateway.evaluate(req, authority=authority, policy=policy)
    assert res.decision == GovernanceDecision.DENY
    assert "AUTHORITY_NOT_DELEGATED" in res.reason_codes[0]

    # 2. Revoked/empty authority fails closed
    revoked_auth = AuthorityContext(
        delegated_by="root",
        granted_action_types=frozenset(),
        require_approval_for=frozenset(),
        delegation_chain=("root",),
    )
    res_no_auth = gateway.evaluate(req, authority=revoked_auth, policy=policy)
    assert res_no_auth.decision == GovernanceDecision.DENY
    assert "AUTHORITY_NOT_DELEGATED" in res_no_auth.reason_codes[0]
