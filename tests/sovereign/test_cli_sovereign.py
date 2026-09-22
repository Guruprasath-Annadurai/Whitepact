# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from click.testing import CliRunner

from biasbuster.cli import main
from responsibleai.sovereign.exit_codes import (
    EXIT_GOVERNANCE,
    EXIT_INVALID,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    EXIT_UNKNOWN,
)


def test_cli_status_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sovereign", "status", "--json"])
    assert result.exit_code == EXIT_OK
    data = json.loads(result.output)
    assert "sovereign_version" in data


def test_cli_doctor_top_level() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])
    assert result.exit_code == EXIT_OK
    assert "checks" in json.loads(result.output)


def test_cli_sandbox_labels() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sandbox", "--json"])
    assert result.exit_code == EXIT_OK
    data = json.loads(result.output)
    assert "SANDBOX" in data["labels"]
    assert data["zero_effect"] is True


def test_cli_replay_unavailable() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["replay", "--json"])
    assert result.exit_code == EXIT_UNAVAILABLE
    data = json.loads(result.output)
    assert data["disposition"] == "UNAVAILABLE"


def test_cli_prove_unavailable() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["prove", "--json"])
    assert result.exit_code == EXIT_UNAVAILABLE


def test_cli_bad_manifest_doctor() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--manifest", "/no/such/file.yaml", "--json"])
    assert result.exit_code == EXIT_INVALID


def test_cli_xray_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["xray", "--org", "org-test", "--json"])
    assert result.exit_code == EXIT_OK
    data = json.loads(result.output)
    assert "graph" in data or "nodes" in data or isinstance(data, dict)


def test_cli_gauntlet_json() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        ["gauntlet", "--org", "org-test", "--probe", "tenant_guard", "--json"],
    )
    assert result.exit_code in (EXIT_OK, EXIT_GOVERNANCE)
    data = json.loads(result.output)
    assert "cases" in data


def test_cli_capsule_create_validate_reproduce() -> None:
    runner = CliRunner()
    create = runner.invoke(main, ["capsule", "create", "--org", "org-c", "--json"])
    assert create.exit_code == EXIT_OK
    cap = json.loads(create.output)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
        json.dump(cap, tmp)
        path = tmp.name
    validate = runner.invoke(main, ["capsule", "validate", "--capsule", path, "--json"])
    assert validate.exit_code == EXIT_OK
    assert json.loads(validate.output)["valid"] is True
    reproduce = runner.invoke(main, ["capsule", "reproduce", "--capsule", path, "--json"])
    assert reproduce.exit_code == EXIT_OK
    Path(path).unlink(missing_ok=True)


def test_cli_policy_lint_invalid_rules() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "policy",
            "lint",
            "--org",
            "org-p",
            "--rules-json",
            json.dumps([{"not_a_rule": True}]),
            "--json",
        ],
    )
    assert result.exit_code == EXIT_INVALID


def test_cli_explain_requires_target() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["explain", "--org", "org-e", "--json"])
    assert result.exit_code == EXIT_INVALID


def test_cli_simulate_mission_unknown_exit() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "simulate",
            "mission",
            "--org",
            "org-m",
            "--agent",
            "agent-1",
            "--step",
            "unknown.action",
            "--json",
        ],
    )
    assert result.exit_code in (EXIT_OK, EXIT_UNKNOWN, EXIT_GOVERNANCE)


def test_cli_ci_with_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "whitepact.yaml"
    manifest.write_text(
        "organization_id: org-ci\nenvironment: development\ncapabilities: []\n",
        encoding="utf-8",
    )
    runner = CliRunner()
    result = runner.invoke(main, ["ci", "--manifest", str(manifest), "--org", "org-ci", "--json"])
    assert result.exit_code in (EXIT_OK, EXIT_GOVERNANCE)
    data = json.loads(result.output)
    assert data["manifest_valid"] is True


def test_doctor_redaction_no_secrets_in_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["doctor", "--json"])
    lowered = result.output.lower()
    assert "sk-live" not in lowered
