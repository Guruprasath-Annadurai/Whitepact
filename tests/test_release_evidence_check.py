# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Untrusted evidence JSON cannot authorize a production launch."""

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

HEAD = "47adb948d76746ce7166ae4a49503b671006049d"
TREE = "c0401db2533bba9b8dfaab2a5902bf88aa17e434"
DIGEST = "sha256:" + ("ab" * 32)


def _record(gate_id: str, kind: str, *, artifact: bool) -> dict[str, str]:
    record = {
        "gate_id": gate_id,
        "kind": kind,
        "status": "ACCEPTED",
        "head": HEAD,
        "tree": TREE,
        "environment": "recorded-ci" if kind != "live_staging" else "staging",
        "verification_authority": "unverified-packet-claim",
    }
    if kind == "owner_approval":
        record["environment"] = "owner-record"
    if kind == "independent_audit":
        record["environment"] = "antigravity-record"
    if artifact:
        record["artifact"] = f"https://github.com/Guruprasath-Annadurai/Whitepact/actions/{gate_id}"
        record["artifact_digest"] = DIGEST
    return record


def _shaped() -> dict[str, object]:
    return {
        "candidate": {"head": HEAD, "tree": TREE},
        "evidence": [
            _record(gate.gate_id, gate.kind, artifact=gate.requires_artifact) for gate in GATES
        ],
    }


def test_catalog_separates_local_and_live_kinds() -> None:
    kinds = {gate.gate_id: gate.kind for gate in GATES}
    assert kinds["runtime.authority"] == "local_test"
    assert kinds["ci.canonical"] == "github_actions"
    assert kinds["independent.qualification"] == "independent_audit"
    assert kinds["staging.live"] == "live_staging"
    assert kinds["owner.legal"] == "owner_approval"


def test_placeholder_urls_are_incomplete() -> None:
    payload = _shaped()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for record in evidence:
        assert isinstance(record, dict)
        if record["gate_id"] == "ci.canonical":
            record["artifact"] = "https://evidence.example/ci"
    result = evaluate(payload)
    assert result["packet_completeness"] == "INCOMPLETE"
    assert result["production_authorization"] == "NO-GO"
    assert any(item["gate_id"] == "ci.canonical" for item in result["failures"])


def test_mismatched_head_is_incomplete() -> None:
    payload = _shaped()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    evidence[0]["head"] = "0" * 40
    result = evaluate(payload)
    assert result["packet_completeness"] == "INCOMPLETE"
    assert "head or tree" in result["failures"][0]["reason"]


def test_live_gate_cannot_be_satisfied_by_a_local_log() -> None:
    payload = _shaped()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for record in evidence:
        assert isinstance(record, dict)
        if record["gate_id"] == "staging.live":
            record["kind"] = "local_test"
            record["environment"] = "offline"
    result = evaluate(payload)
    assert result["decision"] == "NO-GO"
    assert any(item["gate_id"] == "staging.live" for item in result["failures"])


def test_shaped_packet_is_complete_and_still_no_go() -> None:
    result = evaluate(_shaped())
    assert result["failures"] == []
    assert result["packet_completeness"] == "COMPLETE"
    assert result["independent_verification"] == "UNVERIFIED"
    assert result["owner_approval"] == "NOT_AUTHORIZED"
    assert result["production_authorization"] == "NO-GO"
    assert result["decision"] == "NO-GO"
    assert "Antigravity" in result["verifier_procedure"]


def test_conditional_scope_does_not_authorize_launch() -> None:
    payload = _shaped()
    payload["conditional_scope"] = "one design partner"
    result = evaluate(payload)
    assert result["production_authorization"] == "NO-GO"
    assert result["decision"] == "NO-GO"


@pytest.mark.parametrize(
    "artifact",
    [
        "http://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/1",
        "file:///tmp/approval.txt",
        "https://127.0.0.1/ci",
        "https://localhost/ci",
        "https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/1 ",
    ],
)
def test_unverifiable_artifact_urls_are_incomplete(artifact: str) -> None:
    payload = _shaped()
    evidence = payload["evidence"]
    assert isinstance(evidence, list)
    for record in evidence:
        assert isinstance(record, dict)
        if record["gate_id"] == "ci.canonical":
            record["artifact"] = artifact
    result = evaluate(payload)
    assert result["packet_completeness"] == "INCOMPLETE"
    assert result["production_authorization"] == "NO-GO"
    assert any(item["gate_id"] == "ci.canonical" for item in result["failures"])


def test_self_declared_authorization_fields_are_ignored() -> None:
    payload = _shaped()
    payload["decision"] = "GO"
    payload["production_authorization"] = "GO"
    payload["independent_verification"] = "VERIFIED"
    payload["owner_approval"] = "AUTHORIZED"
    payload["conditional_scope"] = "one design partner"
    result = evaluate(payload)
    assert result["packet_completeness"] == "COMPLETE"
    assert result["independent_verification"] == "UNVERIFIED"
    assert result["owner_approval"] == "NOT_AUTHORIZED"
    assert result["production_authorization"] == "NO-GO"
    assert result["decision"] == "NO-GO"


def test_predecessor_packet_cannot_authorize_this_successor() -> None:
    path = Path(__file__).resolve().parents[1] / "docs" / "launch" / "evidence" / "rc-0cdef394.json"
    result = evaluate(json.loads(path.read_text(encoding="utf-8")))
    assert result["packet_completeness"] == "INCOMPLETE"
    assert result["independent_verification"] == "UNVERIFIED"
    assert result["owner_approval"] == "NOT_AUTHORIZED"
    assert result["production_authorization"] == "NO-GO"
    assert result["decision"] == "NO-GO"


def test_cli_never_exits_zero_for_an_untrusted_packet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(_shaped()), encoding="utf-8")
    assert main([str(path)]) == 1
    printed = json.loads(capsys.readouterr().out)
    assert printed["production_authorization"] == "NO-GO"
