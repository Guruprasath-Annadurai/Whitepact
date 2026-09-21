# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json

from click.testing import CliRunner

from biasbuster.cli import main
from responsibleai.sovereign.exit_codes import EXIT_OK, EXIT_UNAVAILABLE


def test_cli_status_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sovereign", "status", "--json"])
    assert result.exit_code == EXIT_OK
    data = json.loads(result.output)
    assert "sovereign_version" in data


def test_cli_sandbox_labels() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sandbox", "--json"])
    assert result.exit_code == EXIT_OK
    data = json.loads(result.output)
    assert "SANDBOX" in data["labels"]


def test_cli_replay_unavailable() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["replay", "--json"])
    assert result.exit_code == EXIT_UNAVAILABLE
    data = json.loads(result.output)
    assert data["disposition"] == "UNAVAILABLE"


def test_cli_bad_manifest_doctor() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sovereign", "doctor", "--manifest", "/no/such/file.yaml"])
    assert result.exit_code != EXIT_OK


def test_doctor_redaction_no_secrets_in_json() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["sovereign", "doctor", "--json"])
    assert "api_key" not in result.output.lower() or "secret" not in result.output
