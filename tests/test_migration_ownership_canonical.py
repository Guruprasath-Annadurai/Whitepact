# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""One Alembic head and one Phase 7A migration ownership map."""

from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

ROOT = Path(__file__).resolve().parents[1]


def test_alembic_single_head_is_0061_sovereign_shadow() -> None:
    script = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini")))
    assert script.get_heads() == ["0061"]
    assert script.get_revision("0061").down_revision == "0060"
    assert script.get_revision("0060").down_revision == "0059"
    assert script.get_revision("0059").down_revision == "0058"
    assert script.get_revision("0058").down_revision == "0057"
    assert script.get_revision("0057").down_revision == "0056"
    assert script.get_revision("0056").down_revision == "0055"
    assert script.get_revision("0055").down_revision == "0054"
    assert script.get_revision("0054").down_revision == "0053"
    assert script.get_revision("0053").down_revision == "0052"
    assert script.get_revision("0052").down_revision == "0051"
    assert script.get_revision("0051").down_revision == "0050"
    assert script.get_revision("0050").down_revision == "0049"
    assert script.get_revision("0049").down_revision == "0048"
    for name in (
        "0050_runtime_execution_requests.py",
        "0051_runtime_execution_authorizations.py",
        "0052_runtime_execution_attempts.py",
        "0053_runtime_worker_leases.py",
        "0054_enterprise_saas_identity.py",
        "0055_verified_principal_gate.py",
        "0056_identity_security_fortress.py",
        "0057_layer2_identity_remediation.py",
        "0058_dashboard_saml_transactions.py",
        "0059_widen_audit_log_key_id.py",
        "0060_test_consequential_counters.py",
        "0061_sovereign_shadow_observations.py",
    ):
        assert (ROOT / "migrations" / "versions" / name).is_file()


def test_no_obsolete_0049_runtime_request_ownership() -> None:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in {".git", ".venv", "node_modules", "static"} for part in path.parts):
            continue
        if path.suffix not in {".md", ".py", ".txt"}:
            continue
        if path.name == "test_migration_ownership_canonical.py":
            continue
        text = path.read_text(errors="replace")
        if "0049_runtime_execution_requests" in text:
            hits.append(str(path.relative_to(ROOT)))
    assert hits == []


def test_canonical_map_matches_implemented_history() -> None:
    text = (ROOT / "docs" / "phase7a-execution" / "migration-ownership.md").read_text()
    assert "0049" in text and "Organization governance lifecycle" in text
    assert "0050" in text and "runtime_execution_requests" in text
    assert "0051" in text and "governance_execution_authorizations" in text
    assert "0052" in text and "runtime_execution_attempts" in text
    assert "0053" in text and "runtime_execution_fences" in text
    assert "0054" in text and "Enterprise SaaS Layer 1" in text
    assert "0055" in text and "Verified principal" in text
    assert "0056" in text and "identity security fortress" in text
    assert "0057" in text and "durable OAuth" in text
    assert "0058" in text and "SAML AuthnRequest" in text
    assert "0059" in text and "audit_log.key_id" in text
    assert "0060" in text and "test_consequential_counters" in text
    assert "Current implemented Alembic head" in text
    assert "`0060`" in text
    assert "`0053`" in text
