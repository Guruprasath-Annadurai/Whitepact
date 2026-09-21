# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.zero_effect import (
    ZeroEffectScope,
    consequential_invocation_count,
    is_zero_effect_context,
    record_consequential_invocation,
)


def test_zero_effect_decorator_sets_context() -> None:
    svc = SovereignService()
    assert not is_zero_effect_context()
    svc.build_xray(SovereignContext(organization_id="org-1", principal_id="p1"))
    assert not is_zero_effect_context()


def test_consequential_counter_inside_zero_effect_scope() -> None:
    with ZeroEffectScope():
        assert is_zero_effect_context()
        record_consequential_invocation()
        assert consequential_invocation_count() == 1
