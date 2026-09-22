# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest

from responsibleai.db import create_engine
from responsibleai.governance.synthetic_counter import bind_counter_engine, increment
from responsibleai.sovereign.zero_effect import ZeroEffectScope, consequential_invocation_count


@pytest.mark.asyncio
async def test_synthetic_increment_counts_as_consequential_in_zero_effect() -> None:
    engine = create_engine(":memory:")
    await engine.init()
    bind_counter_engine(engine)
    with ZeroEffectScope():
        await increment("org-test")
        assert consequential_invocation_count() == 1
