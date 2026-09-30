# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-1: WhitePact CLI entrypoint must not alias biasbuster.cli:main."""

from __future__ import annotations

import importlib.metadata
import re
from pathlib import Path

from click.testing import CliRunner

from biasbuster.cli import main as biasbuster_main
from whitepact.cli import main as whitepact_main


def test_pyproject_whitepact_entrypoint_target() -> None:
    text = Path("pyproject.toml").read_text(encoding="utf-8")
    assert 'whitepact          = "whitepact.cli:main"' in text
    assert 'whitepact          = "biasbuster.cli:main"' not in text


def test_installed_console_script_metadata() -> None:
    eps = importlib.metadata.entry_points(group="console_scripts")
    mapping = {ep.name: ep.value for ep in eps}
    assert mapping.get("whitepact") == "whitepact.cli:main"
    assert mapping.get("biasbuster") == "biasbuster.cli:main"


def test_whitepact_help_is_product_cli() -> None:
    runner = CliRunner()
    result = runner.invoke(whitepact_main, ["--help"])
    assert result.exit_code == 0
    assert "WhitePact" in result.output
    assert "AI governance platform" in result.output
    assert not re.search(
        r"^Usage: whitepact.*\n\n\s+BiasBuster — open-source",
        result.output,
        re.MULTILINE,
    )


def test_biasbuster_help_unchanged_branding() -> None:
    runner = CliRunner()
    result = runner.invoke(biasbuster_main, ["--help"])
    assert result.exit_code == 0
    assert "BiasBuster" in result.output


def test_whitepact_has_sovereign_doctor_not_on_biasbuster_top_level() -> None:
    wp = CliRunner().invoke(whitepact_main, ["doctor", "--json"])
    assert wp.exit_code == 0
    bb = CliRunner().invoke(biasbuster_main, ["doctor", "--json"])
    assert bb.exit_code != 0
    assert "No such command" in bb.output or bb.exit_code == 2


def test_whitepact_bias_subcommand_delegates_run_help() -> None:
    runner = CliRunner()
    result = runner.invoke(whitepact_main, ["bias", "run", "--help"])
    assert result.exit_code == 0
    assert "bias probes" in result.output.lower() or "LLM provider" in result.output


def test_whitepact_info_command() -> None:
    runner = CliRunner()
    result = runner.invoke(whitepact_main, ["info"])
    assert result.exit_code == 0
    assert "rai-governance-platform" in result.output
