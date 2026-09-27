# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.actors import CapabilityActor


def consequence_subject_from_actor(actor: CapabilityActor) -> str:
    """Deterministic subject identity preserving full coalition membership."""
    return "|".join(actor.member_ids)


def consequence_subject_from_members(tenant_id: str, member_ids: tuple[str, ...]) -> str:
    return consequence_subject_from_actor(CapabilityActor.coalition(tenant_id, member_ids))
