# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""MCP final regression matrix index — governed paths must not bypass WhitePact."""

from __future__ import annotations

import importlib

import pytest

MCP_MATRIX_MODULES: tuple[str, ...] = (
    "tests.test_mcp_ws2_authority_matrix",
    "tests.test_mcp_ws2_failclosed_dependency_matrix",
    "tests.test_mcp_ws2_upstream_reconciliation",
    "tests.test_mcp_ws2_worker_retry_matrix",
    "tests.test_mcp_trust_check",
)


@pytest.mark.parametrize("module_name", MCP_MATRIX_MODULES)
def test_mcp_regression_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)
