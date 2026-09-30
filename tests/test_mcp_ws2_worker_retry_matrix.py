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
