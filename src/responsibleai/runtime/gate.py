# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A activation gate.

Production Gate B remains CLOSED. Infrastructure, QueueTickets, Redis,
leases, subscriptions, and API keys are never execution authority.

``PHASE7A_DISPATCHER_ENABLED`` defaults to false. Production must refuse
activation even if the environment variable is tampered to true.
"""

from __future__ import annotations

import os

from responsibleai.dashboard.config import is_production_environment
from responsibleai.runtime.errors import (
    Phase7ADispatcherDisabledError,
    Phase7AProductionGateClosedError,
)

# Compiled-in. Do not derive this from environment variables.
PRODUCTION_GATE_B_OPEN = False

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def phase7a_dispatcher_flag_from_env() -> bool:
    raw = os.environ.get("PHASE7A_DISPATCHER_ENABLED")
    if raw is None:
        raw = os.environ.get("WHITEPACT_PHASE7A_DISPATCHER_ENABLED")
    if raw is None:
        raw = os.environ.get("RAI_PHASE7A_DISPATCHER_ENABLED")
    if raw is None:
        return False
    return raw.strip().lower() in _TRUTHY


def refuse_production_phase7a(*, environment: str, enabled: bool) -> None:
    """Settings / hosted preflight hook. Production cannot enable Phase 7A."""
    if not is_production_environment(environment):
        return
    if enabled or not PRODUCTION_GATE_B_OPEN:
        if enabled and not PRODUCTION_GATE_B_OPEN:
            raise Phase7AProductionGateClosedError(
                "Production Gate B is CLOSED. PHASE7A_DISPATCHER_ENABLED cannot "
                "be true in production."
            )
        if enabled and not PRODUCTION_GATE_B_OPEN:
            raise Phase7AProductionGateClosedError("Production Gate B is CLOSED.")


def assert_phase7a_dispatcher_may_start(
    *,
    environment: str,
    enabled: bool,
) -> None:
    """Fail closed unless development/staging explicitly enables the dispatcher."""
    if is_production_environment(environment) and not PRODUCTION_GATE_B_OPEN:
        raise Phase7AProductionGateClosedError(
            "Production Gate B is CLOSED. Phase 7A dispatcher must not start "
            "in production. Infrastructure is not authority."
        )
    if is_production_environment(environment) and PRODUCTION_GATE_B_OPEN is False:
        raise Phase7AProductionGateClosedError(
            "Production Gate B is CLOSED. Phase 7A dispatcher must not start in production."
        )
    if not enabled:
        raise Phase7ADispatcherDisabledError(
            "PHASE7A_DISPATCHER_ENABLED=false. Dispatcher remains inactive."
        )
