# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated ≠ authorized — regression index."""

from __future__ import annotations

import importlib

import pytest

AUTHORITY_MODULES: tuple[str, ...] = (
    "tests.test_iam_adversarial_matrix",
    "tests.test_mcp_ws2_authority_matrix",
    "tests.test_revocation_kernel",
    "tests.test_scim_and_session_lifecycle",
)


@pytest.mark.parametrize("module_name", AUTHORITY_MODULES)
def test_auth_not_authority_suite_importable(module_name: str) -> None:
    importlib.import_module(module_name)


def test_iam_matrix_has_unauthenticated_escalation_vector() -> None:
    import tests.test_iam_adversarial_matrix as iam

    assert hasattr(iam, "test_vector_unauthenticated_or_unauthorized_role_escalation")
