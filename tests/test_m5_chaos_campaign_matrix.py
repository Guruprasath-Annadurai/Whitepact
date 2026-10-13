# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 full-system chaos / fail-closed campaign index (no new authority on infra failure)."""

from __future__ import annotations

import importlib

import pytest

M5_CHAOS_MODULES: tuple[str, ...] = (
    "tests.test_m5_chaos_fail_closed",
    "tests.test_m4_chaos_fail_closed",
    "tests.test_m4_revocation_under_failure",
    "tests.test_m4_telemetry_fail_closed",
    "tests.test_mcp_ws2_failclosed_dependency_matrix",
    "tests.test_mcp_ws2_worker_retry_matrix",
    "tests.test_siem_delivery_m3",
    "tests.test_restore_admission_chokepoint",
)


@pytest.mark.parametrize("module_name", M5_CHAOS_MODULES)
def test_m5_chaos_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_m5_chaos_doctrine_documented() -> None:
    from pathlib import Path

    plan = Path(__file__).resolve().parent.parent / "docs" / "ws6" / "M5_REBUILD_PLAN.md"
    text = plan.read_text(encoding="utf-8")
    assert "must never create new authority" in text.lower() or "never create new authority" in text
