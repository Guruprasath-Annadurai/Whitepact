# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Duplicate execution final campaign index."""

from __future__ import annotations

import importlib

import pytest

DUPLICATE_MODULES: tuple[str, ...] = (
    "tests.test_v1_exactly_one_effect",
    "tests.test_mcp_ws2_worker_retry_matrix",
    "tests.test_phase7a_authority_kernel",
    "tests.test_mcp_ws2_upstream_reconciliation",
)


@pytest.mark.parametrize("module_name", DUPLICATE_MODULES)
def test_duplicate_execution_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)
