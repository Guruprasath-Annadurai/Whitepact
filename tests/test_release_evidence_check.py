# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The release checker must not promote local tests to a launch GO."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "release_evidence_check",
    Path(__file__).resolve().parents[1] / "scripts" / "release_evidence_check.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)
GATES = _MODULE.GATES
evaluate = _MODULE.evaluate
main = _MODULE.main


def _accepted(gate_id: str, kind: str, artifact: str | None = None) -> dict[str, str]:
    record = {"gate_id": gate_id, "kind": kind, "status": "ACCEPTED"}
    if artifact is not None:
        record["artifact"] = artifact
    return record


def _complete(**overrides: str) -> dict[str, object]:
    evidence = []
    for gate in GATES:
        artifact = f"https://evidence.example/{gate.gate_id}" if gate.requires_artifact else None
        evidence.append(_accepted(gate.gate_id, gate.kind, artifact))
    payload: dict[str, object] = {"evidence": evidence}
    payload.update(overrides)
    return payload


def test_catalog_separates_local_and_live_kinds() -> None:
    kinds = {gate.gate_id: gate.kind for gate in GATES}
    assert kinds["runtime.authority"] == "local_test"
    assert kinds["ci.canonical"] == "github_actions"
    assert kinds["independent.qualification"] == "independent_audit"
    assert kinds["staging.live"] == "live_staging"
    assert kinds["owner.legal"] == "owner_approval"


def test_local_success_alone_is_no_go() -> None:
    payload = {
        "evidence": [
            _accepted("runtime.authority", "local_test"),
            _accepted("tenant.isolation", "local_test"),
            _accepted("grant.replay", "local_test"),
        ]
    }
    result = evaluate(payload)
    assert result["decision"] == "NO-GO"
    missing = {item["gate_id"] for item in result["failures"]}
    assert "staging.live" in missing
    assert "independent.qualification" in missing
    assert "owner.infrastructure" in missing


def test_live_gate_cannot_be_satisfied_by_a_local_log() -> None:
    payload = _complete()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for record in evidence:
        assert isinstance(record, dict)
        if record["gate_id"] == "staging.live":
            record["kind"] = "local_test"
    result = evaluate(payload)
    assert result["decision"] == "NO-GO"
    assert any(item["gate_id"] == "staging.live" for item in result["failures"])


def test_accepted_live_gate_without_artifact_is_no_go() -> None:
    payload = _complete()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for record in evidence:
        assert isinstance(record, dict)
        if record["gate_id"] == "ci.canonical":
            del record["artifact"]
    result = evaluate(payload)
    assert result["decision"] == "NO-GO"
    assert "artifact" in result["failures"][0]["reason"]


def test_complete_independent_packet_is_go() -> None:
    result = evaluate(_complete())
    assert result["decision"] == "GO"
    assert result["failures"] == []


def test_explicit_scope_with_complete_evidence_is_conditional() -> None:
    result = evaluate(_complete(conditional_scope="one design partner, read-only tools"))
    assert result["decision"] == "CONDITIONAL_GO"
    assert result["conditional_scope"] == "one design partner, read-only tools"


def test_conditional_scope_does_not_hide_a_failure() -> None:
    result = evaluate({"conditional_scope": "limited rollout", "evidence": []})
    assert result["decision"] == "NO-GO"


def test_cli_exits_nonzero_for_no_go(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps({"evidence": []}), encoding="utf-8")
    assert main([str(path)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision"] == "NO-GO"
