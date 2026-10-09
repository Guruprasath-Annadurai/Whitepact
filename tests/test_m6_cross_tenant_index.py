# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cross-tenant assault regression index."""

from __future__ import annotations

import importlib

import pytest

TENANT_MODULES: tuple[str, ...] = (
    "tests.test_web_invitations_adversarial",
    "tests.test_siem_audit_export",
    "tests.test_scim_and_session_lifecycle",
    "tests.test_iam_adversarial_matrix",
)


@pytest.mark.parametrize("module_name", TENANT_MODULES)
def test_cross_tenant_module_importable(module_name: str) -> None:
    importlib.import_module(module_name)
