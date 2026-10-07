# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Failure combination campaign (A–F) — suite index."""

from __future__ import annotations

import importlib

import pytest

COMBO_MODULES: tuple[str, ...] = (
    "tests.test_m4_chaos_fail_closed",
    "tests.test_m4_revocation_under_failure",
    "tests.test_m4_telemetry_fail_closed",
    "tests.test_mcp_ws2_failclosed_dependency_matrix",
    "tests.test_restore_admission_chokepoint",
    "tests.test_siem_delivery_m3",
)


@pytest.mark.parametrize("module_name", COMBO_MODULES)
def test_failure_combination_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)
