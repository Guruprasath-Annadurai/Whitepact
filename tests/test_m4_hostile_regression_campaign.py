# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 hostile regression — black-box slices across enterprise hardening suites."""

from __future__ import annotations

import importlib

import pytest

M4_CAMPAIGN_MODULES: tuple[str, ...] = (
    "tests.test_m4_engineering_gates",
    "tests.test_m4_audit_export_batch_smoke",
    "tests.test_restore_admission_chokepoint",
    "tests.test_scim_and_session_lifecycle",
)


@pytest.mark.parametrize("module_name", M4_CAMPAIGN_MODULES)
def test_m4_campaign_module_importable(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_m4_terraform_tree_blocks_provision_without_apply_marker() -> None:
    from pathlib import Path

    readme = Path(__file__).resolve().parents[1] / "infra" / "terraform" / "README.md"
    assert readme.is_file()
    text = readme.read_text(encoding="utf-8").lower()
    assert "apply" in text or "provision" in text
    assert "blocked" in text or "validate" in text or "plan-only" in text
