# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Probe contract tests, not substitutes for actual native Docker qualification."""

import json
import subprocess
from pathlib import Path

import pytest


def test_complete_workflows_retain_fail_closed_docker_evidence():
    root = Path(__file__).resolve().parents[1]
    r1 = (root / ".github/workflows/m13-r1-operator-recovery.yml").read_text()
    absolute = (root / ".github/workflows/m13-absolute-runtime-review.yml").read_text()
    assert "m13_docker_qualification_probe.py --phase before" in r1
    assert "m13_docker_qualification_probe.py --phase after" in r1
    assert "m13_docker_qualification_probe.py --phase before" in absolute
    assert "m13_docker_qualification_probe.py --phase after" in absolute
    assert "/tmp/r1-docker-before.json" in r1
    assert "/tmp/r1-docker-after.json" in r1
    assert "/tmp/native-docker-before.json" in absolute
    assert "/tmp/native-docker-after.json" in absolute
    assert "tests/test_m13_fortress_restore_independent.py" not in absolute
    assert "scripts/engineering/reproducers/test_m13_fortress_restore_independent.py" in absolute
    assert (
        "tests/test_m13_absolute_native_runtime.py tests/test_docker_ownership_regression.py"
        in absolute
    )


def invoke(monkeypatch, *, identity="daemon-id", changed=None, fail=None, inventory=None):
    from scripts.engineering import m13_docker_qualification_probe as probe

    calls = []

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert kwargs["timeout"] == 10
        if command[1] == "info" and command[-1] == "{{json .}}":
            if fail == "timeout":
                raise subprocess.TimeoutExpired(command, 10)
            if fail == "exit":
                return subprocess.CompletedProcess(command, 1, "", "private-secret")
            value = {"ID": identity, "ServerVersion": "test-only", "Labels": ["secret"]}
            return subprocess.CompletedProcess(command, 0, json.dumps(value), "")
        if command[1] == "info":
            return subprocess.CompletedProcess(command, 0, changed or identity, "")
        if command[1] == "ps":
            return subprocess.CompletedProcess(command, 0, inventory or "", "")
        if command[1] == "version":
            return subprocess.CompletedProcess(command, 0, '{"Version":"test-only"}', "")
        return subprocess.CompletedProcess(command, 0, "ActiveState=active", "")

    monkeypatch.setattr(probe.subprocess, "run", run)
    return probe.collect("before"), calls


def test_real_identity_required_and_no_authority_issued(monkeypatch):
    report, calls = invoke(monkeypatch)
    assert report["ready"] is True
    assert report["execution_authority"] is False
    assert report["daemon_identity"] == "daemon-id"
    assert "secret" not in json.dumps(report)
    assert all(command[1] in {"info", "ps", "version", "show"} for command, _ in calls)


@pytest.mark.parametrize("identity", ["", "wrong identity", "/tmp/socket", "x" * 129])
def test_invalid_identity_never_qualifies(monkeypatch, identity):
    report, _ = invoke(monkeypatch, identity=identity)
    assert report["ready"] is False


@pytest.mark.parametrize("fail", ["timeout", "exit"])
def test_probe_failure_is_not_retried_or_qualified(monkeypatch, fail):
    report, calls = invoke(monkeypatch, fail=fail)
    assert report["ready"] is False
    assert "private-secret" not in json.dumps(report)
    assert sum(command[1] == "info" and command[-1] == "{{json .}}" for command, _ in calls) == 1


def test_changed_daemon_identity_never_qualifies(monkeypatch):
    report, _ = invoke(monkeypatch, changed="other-daemon")
    assert report["ready"] is False


def test_malformed_inventory_never_qualifies(monkeypatch):
    report, _ = invoke(monkeypatch, inventory="not-json")
    assert report["ready"] is False


def test_inventory_is_evidence_not_an_allowlist(monkeypatch):
    report, _ = invoke(
        monkeypatch,
        inventory=json.dumps({"ID": "a" * 64, "Names": "unknown", "Labels": "secret"}),
    )
    assert report["inventory"][0]["Names"] == "unknown"
    assert "Labels" not in report["inventory"][0]
    assert report["execution_authority"] is False


def test_failed_probe_exits_nonzero_and_keeps_receipt(monkeypatch, tmp_path):
    from scripts.engineering import m13_docker_qualification_probe as probe

    output = tmp_path / "failed.json"
    report, _ = invoke(monkeypatch, fail="timeout")
    monkeypatch.setattr(probe, "collect", lambda phase: report)
    monkeypatch.setattr("sys.argv", ["probe", "--phase", "before", "--output", str(output)])
    assert probe.main() == 1
    assert json.loads(output.read_text())["ready"] is False


@pytest.mark.parametrize(
    "baseline", [{}, {"ready": False}, {"ready": True, "daemon_identity": "other"}]
)
def test_after_probe_cannot_accept_missing_or_changed_baseline(monkeypatch, tmp_path, baseline):
    from scripts.engineering import m13_docker_qualification_probe as probe

    before, output = tmp_path / "before.json", tmp_path / "after.json"
    before.write_text(json.dumps(baseline))
    report, _ = invoke(monkeypatch)
    monkeypatch.setattr(probe, "collect", lambda phase: report)
    monkeypatch.setattr(
        "sys.argv",
        ["probe", "--phase", "after", "--baseline", str(before), "--output", str(output)],
    )
    assert probe.main() == 1
    assert json.loads(output.read_text())["ready"] is False
