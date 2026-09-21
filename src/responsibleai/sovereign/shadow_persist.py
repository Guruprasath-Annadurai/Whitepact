# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.db.shadow_observation_repository import ShadowObservationRepository
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.shadow import ShadowObservation, evaluate_shadow
from responsibleai.sovereign.shadow_store import PersistedShadowRecord
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


@zero_effect_operation
def evaluate_shadow_persisted(
    ctx: SovereignContext,
    **kwargs: object,
) -> ShadowObservation:
    return evaluate_shadow(ctx, **kwargs)  # type: ignore[arg-type]


@zero_effect_operation
async def evaluate_shadow_persisted_async(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    **kwargs: object,
) -> PersistedShadowRecord:
    obs = evaluate_shadow(ctx, **kwargs)  # type: ignore[arg-type]
    agent_id = str(kwargs.get("agent_id", ""))
    action_type = str(kwargs.get("action_type", ""))
    target = str(kwargs.get("target", "shadow:target"))
    policy_version = None
    try:
        policy = await store.policies.get_policy(ctx.organization_id)
        policy_version = policy.version
    except Exception:  # noqa: BLE001 — optional metadata
        policy_version = None
    row = await ShadowObservationRepository(store.engine).save(
        ctx,
        obs,
        agent_id=agent_id,
        action_type=action_type,
        target=target,
        policy_version=policy_version,
    )
    return PersistedShadowRecord(
        shadow_id=row.shadow_observation_id,
        organization_id=row.org_id,
        observation=obs,
        created_at=row.created_at,
    )
