# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Product acceptance blockers; real service + isolated SQLite, NOT golden journey.

Intentionally normal failing tests until the security owner corrects the contract.
No production fixture or security implementation is changed.
"""

from unittest.mock import AsyncMock

import pytest

from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from tests.test_m12fs_root_hardening import (
    _configure_test_env,  # noqa: F401 -- imports the isolated autouse fixture
    _create_test_owner,
)


@pytest.mark.asyncio
async def test_containment_must_not_confirm_when_termination_fails(monkeypatch):
    actor, _, org_id, _, _ = await _create_test_owner()
    terminate = AsyncMock(side_effect=RuntimeError("isolated termination failure"))
    monkeypatch.setattr(InFlightExecutionRegistry.get_instance(), "terminate_in_flight", terminate)
    result = await CustomerAuthorityService(get_enterprise_engine()).execute_emergency_containment(
        actor,
        org_id=org_id,
        target_type="ORGANIZATION",
        target_id=org_id,
        containment_action="LOCKDOWN",
        reason="Local product acceptance failure injection",
    )
    terminate.assert_awaited_once()
    assert result["status"] != "CONTAINED", (
        "P0: failed termination must remain unresolved, not confirmed containment"
    )


@pytest.mark.asyncio
async def test_privileged_containment_requires_server_enforced_stepup():
    actor, _, org_id, _, _ = await _create_test_owner()
    with pytest.raises(Exception) as error:
        await CustomerAuthorityService(get_enterprise_engine()).execute_emergency_containment(
            actor,
            org_id=org_id,
            target_type="ORGANIZATION",
            target_id=org_id,
            containment_action="LOCKDOWN",
            reason="Omitted privileged assertion must not pass",
        )
    assert getattr(error.value, "code", None) == "PASSKEY_STEP_UP_REQUIRED"
