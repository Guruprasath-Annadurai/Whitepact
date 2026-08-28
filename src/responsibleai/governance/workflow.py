# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Workflow Authority: detects an authority-composition violation — a
sequence of individually-permitted actions that becomes dangerous only
in combination (e.g. ``beneficiary.create`` -> ``payment.limit.raise``
-> ``payment.execute`` inside a short window, each step legitimately
authorized on its own).

Deliberately not an LLM-based or fuzzy match: a fixed, ordered
``action_types`` sequence per rule, checked as a subsequence (order
preserved, not necessarily contiguous — an unrelated action between two
matched steps doesn't reset the match) within a per-rule time window.
No behavioral inference, no natural-language rule authoring — matches
this codebase's "prefer deterministic security controls" rule, same as
`governance/policy.py` and `governance/risk.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from responsibleai.governance.reason_codes import ReasonCode, format_reason


@dataclass(frozen=True)
class WorkflowSequenceRule:
    """*action_types* is the forbidden ordered sequence — e.g.
    ``("beneficiary.create", "payment.limit.raise", "payment.execute")``.
    *window_minutes* bounds how far apart the first and last matched
    step may be; there's no lower bound (three steps seconds apart still
    counts)."""

    rule_id: str
    action_types: tuple[str, ...]
    window_minutes: int


@dataclass(frozen=True)
class TimestampedAction:
    """One entry from an agent's recent action history — see
    ``db.EvidenceRepository.list_recent_actions()``, the real source of
    this in the live MCP dispatch path."""

    action_type: str
    at: datetime


def _is_subsequence(pattern: tuple[str, ...], timeline: list[str]) -> bool:
    """True if every element of *pattern*, in order, appears somewhere
    in *timeline* (not necessarily contiguous — a "beneficiary.create"
    then an unrelated "rai_health" then "payment.limit.raise" still
    matches ``("beneficiary.create", "payment.limit.raise")``)."""
    it = iter(timeline)
    return all(any(item == step for item in it) for step in pattern)


def check_composition_violation(
    recent_actions: list[TimestampedAction],
    new_action_type: str,
    new_action_at: datetime,
    rules: list[WorkflowSequenceRule],
) -> str | None:
    """``None`` unless *new_action_type* is the step that completes one
    of *rules*' forbidden sequences right now — checked as "the pattern
    doesn't already match history alone, but does once this action is
    appended," so a rule fires exactly once, on the completing action,
    not on every action afterward (a completed pattern is trivially
    still a subsequence of any longer timeline containing it, which
    would otherwise flag every subsequent unrelated call forever).

    *recent_actions* should already be roughly bounded (the caller's
    query window) — this function applies each rule's own
    *window_minutes* on top, relative to *new_action_at*, so a single
    fetched history can serve rules with different window lengths.
    """
    for rule in rules:
        window_start = new_action_at - timedelta(minutes=rule.window_minutes)
        windowed = [a.action_type for a in recent_actions if a.at >= window_start]
        already_matched = _is_subsequence(rule.action_types, windowed)
        with_new = _is_subsequence(rule.action_types, [*windowed, new_action_type])
        if with_new and not already_matched:
            return format_reason(
                ReasonCode.AUTHORITY_COMPOSITION_VIOLATION,
                rule_id=rule.rule_id,
                sequence="->".join(rule.action_types),
            )
    return None
