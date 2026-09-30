# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 worker / retry / resume safety (Phase 7A gate + resume path)."""

from __future__ import annotations

import pytest

from responsibleai.runtime.dispatcher import start_phase7a_dispatcher
from responsibleai.runtime.gate import assert_phase7a_dispatcher_may_start, refuse_production_phase7a


def test_phase7a_dispatcher_blocked_in_production() -> None:
    with pytest.raises(Exception):
        refuse_production_phase7a(environment="production", enabled=True)
    with pytest.raises(Exception):
        start_phase7a_dispatcher(environment="production", enabled=True)
    with pytest.raises(Exception):
        assert_phase7a_dispatcher_may_start(environment="prod", enabled=True)


def test_phase7a_dispatcher_allowed_in_staging_only_when_enabled() -> None:
    refuse_production_phase7a(environment="production", enabled=False)
    dispatcher = start_phase7a_dispatcher(environment="staging", enabled=True)
    assert dispatcher is not None


def test_settings_production_rejects_phase7a_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import Settings

    monkeypatch.setenv("WHITEPACT_ENV", "production")
    monkeypatch.setenv("WHITEPACT_PHASE7A_DISPATCHER_ENABLED", "true")
    monkeypatch.setenv("WHITEPACT_MCP_TRUST_DOMAIN", "enterprise")
    with pytest.raises(Exception):
        Settings(_env_file=None)


def test_hosted_production_preflight_rejects_phase7a(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    from responsibleai.mcp.server import HostedProductionSecurityError, hosted_production_preflight

    settings = SimpleNamespace(
        environment="production",
        is_production=True,
        mcp_governance_enabled=True,
        mcp_trust_domain="enterprise",
        mcp_http_allow_unauthenticated_demo=False,
        phase7a_dispatcher_enabled=True,
        multi_replica=False,
        api_keys=[],
    )
    with pytest.raises(HostedProductionSecurityError, match="Gate B"):
        hosted_production_preflight(settings, allowed_hosts=["mcp.example.com"])
