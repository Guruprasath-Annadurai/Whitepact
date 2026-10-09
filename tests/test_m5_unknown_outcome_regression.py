# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""UNKNOWN / RECONCILIATION_REQUIRED regression index."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent

UNKNOWN_MODULES: tuple[str, ...] = (
    "tests.test_mcp_ws2_upstream_reconciliation",
    "tests.test_sdk_governance_reconciliation_m3",
    "tests.test_mcp_ws2_worker_retry_matrix",
)


@pytest.mark.parametrize("module_name", UNKNOWN_MODULES)
def test_unknown_outcome_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_executor_unknown_runbook_present() -> None:
    runbook = ROOT.parent / "docs" / "operations" / "runbooks" / "EXECUTOR_UNKNOWN_OUTCOME.md"
    assert runbook.is_file()
    text = runbook.read_text(encoding="utf-8")
    assert "RECONCILIATION_REQUIRED" in text


def test_database_outage_runbook_mentions_unknown() -> None:
    runbook = ROOT.parent / "docs" / "operations" / "runbooks" / "DATABASE_OUTAGE.md"
    assert runbook.is_file()
    assert "UNKNOWN" in runbook.read_text(encoding="utf-8")
