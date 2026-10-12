# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression test for examples/09_mcp_langgraph_tutorial.py (T-14)."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

langgraph = pytest.importorskip("langgraph")

TUTORIAL_PATH = Path(__file__).resolve().parents[1] / "examples" / "09_mcp_langgraph_tutorial.py"


def test_tutorial_file_exists() -> None:
    assert TUTORIAL_PATH.is_file(), f"Tutorial script missing at {TUTORIAL_PATH}"


def test_run_tutorial_end_to_end(capsys) -> None:
    spec = importlib.util.spec_from_file_location("tutorial_mod", TUTORIAL_PATH)
    assert spec is not None and spec.loader is not None
    tutorial_mod = importlib.util.module_from_spec(spec)
    import sys

    sys.modules["tutorial_mod"] = tutorial_mod
    spec.loader.exec_module(tutorial_mod)

    # Execute the tutorial function
    tutorial_mod.run_tutorial()

    captured = capsys.readouterr()
    assert "WhitePact + LangGraph Zero-Credential Trust Gate Tutorial" in captured.out
    assert "Scenario 1: Low-Risk Tool ('safe_query')" in captured.out
    assert "Scenario 2: High-Risk Tool ('modify_production_config')" in captured.out
    assert "Scenario 3: Human Approval Path ('transfer_funds')" in captured.out
    assert "Scenario 4: Direct WhitePact Gateway Authority Evaluation" in captured.out
    assert "All tutorial scenarios passed successfully without credentials." in captured.out
