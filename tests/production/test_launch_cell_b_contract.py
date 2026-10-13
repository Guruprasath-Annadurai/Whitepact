# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Launch Cell B — production contract and config validation smoke tests."""

from __future__ import annotations

import importlib

import pytest

from responsibleai.operations.config_validate import validate
from responsibleai.operations.production_contract import (
    STRUCTURED_LOG_CORE_FIELDS,
    FormulaRolloutMode,
)


def test_structured_log_core_fields_non_empty() -> None:
    assert "request_id" in STRUCTURED_LOG_CORE_FIELDS
    assert "tenant_id" in STRUCTURED_LOG_CORE_FIELDS


def test_formula_rollout_modes_ordered_for_gate8() -> None:
    assert FormulaRolloutMode.OFF.value == "OFF"
    assert FormulaRolloutMode.SHADOW.value == "SHADOW"


def test_config_validate_dev_defaults_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("WHITEPACT_DATABASE_URL", raising=False)
    errors = validate(expect_production=False)
    assert errors == []


def test_config_validate_expect_production_fails_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    errors = validate(expect_production=True)
    assert any("expected_production" in e for e in errors)


def test_config_validate_module_cli_importable() -> None:
    mod = importlib.import_module("responsibleai.operations.config_validate")
    assert callable(mod.main)
