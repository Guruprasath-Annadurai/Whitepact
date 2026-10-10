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
