# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A production feature-flag refusal. Gate B remains CLOSED."""

from __future__ import annotations

import pytest

from responsibleai.runtime.dispatcher import start_phase7a_dispatcher
from responsibleai.runtime.errors import (
    Phase7ADispatcherDisabledError,
    Phase7AProductionGateClosedError,
)
from responsibleai.runtime.gate import (
    PRODUCTION_GATE_B_OPEN,
    assert_phase7a_dispatcher_may_start,
    phase7a_dispatcher_flag_from_env,
    refuse_production_phase7a,
)


def test_gate_b_is_compiled_closed() -> None:
    assert PRODUCTION_GATE_B_OPEN is False


def test_flag_defaults_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PHASE7A_DISPATCHER_ENABLED", raising=False)
    monkeypatch.delenv("WHITEPACT_PHASE7A_DISPATCHER_ENABLED", raising=False)
    monkeypatch.delenv("RAI_PHASE7A_DISPATCHER_ENABLED", raising=False)
    assert phase7a_dispatcher_flag_from_env() is False


def test_production_refuses_enabled_flag() -> None:
    with pytest.raises(Phase7AProductionGateClosedError, match="Gate B"):
        refuse_production_phase7a(environment="production", enabled=True)
    with pytest.raises(Phase7AProductionGateClosedError, match="Gate B"):
        start_phase7a_dispatcher(environment="production", enabled=True)
    with pytest.raises(Phase7AProductionGateClosedError):
        assert_phase7a_dispatcher_may_start(environment="prod", enabled=True)


def test_production_flag_false_does_not_start_dispatcher() -> None:
    refuse_production_phase7a(environment="production", enabled=False)
    with pytest.raises(Phase7AProductionGateClosedError):
        start_phase7a_dispatcher(environment="production", enabled=False)


def test_staging_requires_explicit_flag() -> None:
    with pytest.raises(Phase7ADispatcherDisabledError):
        start_phase7a_dispatcher(environment="staging", enabled=False)
    dispatcher = start_phase7a_dispatcher(environment="staging", enabled=True)
    assert dispatcher.enabled is True


def test_settings_production_refuses_phase7a(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_DATABASE_URL", "postgresql://wp:wp@127.0.0.1:55432/postgres")
    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", "x" * 44)
    monkeypatch.setenv("PHASE7A_DISPATCHER_ENABLED", "true")
    from cryptography.fernet import Fernet

    monkeypatch.setenv("WHITEPACT_FIELD_ENCRYPTION_KEY", Fernet.generate_key().decode())
    from pydantic import ValidationError

    from responsibleai.dashboard.config import Settings
    from responsibleai.runtime.errors import Phase7AProductionGateClosedError

    with pytest.raises((Phase7AProductionGateClosedError, ValidationError)):
        Settings()
