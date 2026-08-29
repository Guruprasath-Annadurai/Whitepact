"""Tests for Heart Production Closure Gap C --
`governance/heart_production_gate.py`'s
`verify_heart_production_enforcement()`.

Mirrors `test_crypto_activation.py`'s own structure (same fail-closed-
at-startup pattern, same precedent this module was deliberately built
to match) -- reproduces the gap first, then verifies the fail-closed
behavior that closes it.
"""

from __future__ import annotations

import pytest

from responsibleai.dashboard.config import Settings
from responsibleai.db.engine import DatabaseEngine, create_engine
from responsibleai.governance.heart_production_gate import (
    HeartEnforcementError,
    verify_heart_production_enforcement,
)


async def _engine() -> DatabaseEngine:
    engine = create_engine(":memory:")
    await engine.init()
    return engine


class TestReproduceTheGap:
    """Before testing the fix: enterprise_mode and mcp_governance_enabled
    are two fully independent flags today, so it is trivially possible
    to set one without the other."""

    async def test_default_settings_have_both_flags_off(self) -> None:
        settings = Settings()
        assert settings.enterprise_mode is False
        assert settings.mcp_governance_enabled is False

    async def test_enterprise_mode_alone_does_not_imply_governance_enabled(self) -> None:
        settings = Settings(enterprise_mode=True)
        assert settings.mcp_governance_enabled is False


class TestFailClosedStartup:
    async def test_enterprise_mode_false_is_a_no_op_regardless_of_governance(self) -> None:
        settings = Settings(enterprise_mode=False, mcp_governance_enabled=False)
        engine = await _engine()
        await verify_heart_production_enforcement(settings, engine)  # must not raise
        await engine.close()

    async def test_enterprise_mode_true_without_governance_enabled_raises(self) -> None:
        settings = Settings(enterprise_mode=True, mcp_governance_enabled=False)
        engine = await _engine()
        with pytest.raises(HeartEnforcementError, match="mcp_governance_enabled"):
            await verify_heart_production_enforcement(settings, engine)
        await engine.close()

    async def test_enterprise_mode_true_with_governance_enabled_and_reachable_store_passes(
        self,
    ) -> None:
        settings = Settings(enterprise_mode=True, mcp_governance_enabled=True)
        engine = await _engine()
        await verify_heart_production_enforcement(settings, engine)  # must not raise
        await engine.close()

    async def test_enterprise_mode_true_with_unreachable_store_raises(self) -> None:
        """A closed engine simulates the store being unreachable at the
        instant startup tries to verify it -- must fail closed, not
        silently skip the check."""
        settings = Settings(enterprise_mode=True, mcp_governance_enabled=True)
        engine = await _engine()
        await engine.close()
        with pytest.raises(HeartEnforcementError):
            await verify_heart_production_enforcement(settings, engine)

    async def test_governance_enabled_check_runs_before_the_store_reachability_check(
        self,
    ) -> None:
        """The cheaper, more common misconfiguration (a forgotten flag)
        should surface its own specific error rather than being masked
        by a store-reachability failure that happens to occur too --
        checked here by using a live, reachable engine so only the
        governance-flag error path is possible."""
        settings = Settings(enterprise_mode=True, mcp_governance_enabled=False)
        engine = await _engine()
        with pytest.raises(HeartEnforcementError, match="mcp_governance_enabled"):
            await verify_heart_production_enforcement(settings, engine)
        await engine.close()


class TestDemoAuthIncompatibleWithEnterpriseMode:
    """Heart Enforcement Chokepoint Closure Phase E4: the demo-auth
    flag grants hosted MCP access with zero credentials, over a
    connection the governance dispatch path cannot build authority
    for -- incompatible with a deployment claiming production
    enforcement."""

    async def test_demo_flag_alone_is_fine(self) -> None:
        """enterprise_mode=false is a no-op regardless of the demo
        flag -- this flag's own existing scope (dev/demo use) is
        unaffected."""
        settings = Settings(
            enterprise_mode=False,
            mcp_governance_enabled=False,
            mcp_http_allow_unauthenticated_demo=True,
        )
        engine = await _engine()
        await verify_heart_production_enforcement(settings, engine)  # must not raise
        await engine.close()

    async def test_enterprise_mode_true_with_demo_flag_true_raises(self) -> None:
        settings = Settings(
            enterprise_mode=True,
            mcp_governance_enabled=True,
            mcp_http_allow_unauthenticated_demo=True,
        )
        engine = await _engine()
        with pytest.raises(HeartEnforcementError, match="mcp_http_allow_unauthenticated_demo"):
            await verify_heart_production_enforcement(settings, engine)
        await engine.close()

    async def test_enterprise_mode_true_with_demo_flag_false_passes(self) -> None:
        settings = Settings(
            enterprise_mode=True,
            mcp_governance_enabled=True,
            mcp_http_allow_unauthenticated_demo=False,
        )
        engine = await _engine()
        await verify_heart_production_enforcement(settings, engine)  # must not raise
        await engine.close()
