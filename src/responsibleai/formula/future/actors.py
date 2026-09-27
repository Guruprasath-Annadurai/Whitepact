# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.capability.actors import CapabilityActor


def consequence_subject_from_actor(actor: CapabilityActor) -> str:
    """Deterministic subject identity preserving full coalition membership."""
    return "|".join(actor.member_ids)


def consequence_subject_from_members(tenant_id: str, member_ids: tuple[str, ...]) -> str:
    return consequence_subject_from_actor(CapabilityActor.coalition(tenant_id, member_ids))


def coalition_member_set(subject_id: str) -> frozenset[str]:
    if "|" in subject_id:
        return frozenset(subject_id.split("|"))
    return frozenset({subject_id})


def prereq_subjects_compatible_with_rule(
    rule_output_subject_id: str,
    prereq_subject_ids: tuple[str, ...],
) -> bool:
    """Ordinary rules require every prerequisite fact to share the rule subject.

    Explicit coalition rules (``output_subject_id`` contains ``|``) require each
    prerequisite to be a single coalition member and the prerequisite subjects to
    cover the full coalition exactly.
    """
    if not prereq_subject_ids:
        return True
    if "|" in rule_output_subject_id:
        coalition = coalition_member_set(rule_output_subject_id)
        for subj in prereq_subject_ids:
            if "|" in subj or subj not in coalition:
                return False
        return frozenset(prereq_subject_ids) == coalition
    expected = rule_output_subject_id
    return all(subj == expected for subj in prereq_subject_ids)
