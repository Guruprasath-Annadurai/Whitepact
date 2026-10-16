# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M5 revocation stress — sessions, grants, MCP, workers (campaign index)."""

from __future__ import annotations

import importlib

import pytest

REVOCATION_MODULES: tuple[str, ...] = (
    "tests.test_revocation_kernel",
    "tests.test_m4_revocation_under_failure",
    "tests.test_iam_adversarial_matrix",
    "tests.test_scim_and_session_lifecycle",
    "tests.test_mcp_ws2_authority_matrix",
    "tests.test_phase7a_authority_kernel",
)


@pytest.mark.parametrize("module_name", REVOCATION_MODULES)
def test_revocation_stress_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)
