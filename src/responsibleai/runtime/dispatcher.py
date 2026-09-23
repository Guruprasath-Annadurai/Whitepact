# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Phase 7A dispatcher entry. Must not start in production while Gate B is closed."""

from __future__ import annotations

from responsibleai.runtime.errors import Phase7AProductionGateClosedError
from responsibleai.runtime.gate import (
    PRODUCTION_GATE_B_OPEN,
    assert_phase7a_dispatcher_may_start,
    phase7a_dispatcher_flag_from_env,
)


class Phase7ADispatcher:
    def __init__(self, *, environment: str, enabled: bool) -> None:
        assert_phase7a_dispatcher_may_start(environment=environment, enabled=enabled)
        self.environment = environment
        self.enabled = True


def start_phase7a_dispatcher(*, environment: str, enabled: bool | None = None) -> Phase7ADispatcher:
    flag = phase7a_dispatcher_flag_from_env() if enabled is None else enabled
    if environment.strip().lower() in {"production", "prod"} and not PRODUCTION_GATE_B_OPEN:
        raise Phase7AProductionGateClosedError(
            "Production Gate B is CLOSED. Phase 7A dispatcher must not start in production."
        )
    return Phase7ADispatcher(environment=environment, enabled=flag)
