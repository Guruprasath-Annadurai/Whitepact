# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.shadow import evaluate_shadow
from responsibleai.sovereign.shadow_store import PersistedShadowRecord, global_shadow_store
from responsibleai.sovereign.zero_effect import zero_effect_operation


@zero_effect_operation
def evaluate_shadow_persisted(
    ctx: SovereignContext,
    **kwargs: object,
) -> PersistedShadowRecord:
    obs = evaluate_shadow(ctx, **kwargs)  # type: ignore[arg-type]
    return global_shadow_store().save(obs)
