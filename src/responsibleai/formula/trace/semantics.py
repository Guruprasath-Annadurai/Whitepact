# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trace semantics — path history vs state-only authorization."""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.trace.trace import FormulaTrace, FormulaTraceEvent


def TraceAuthorized(trace: FormulaTrace, authorized_event_ids: frozenset[str]) -> bool:
    """Every event must carry an authorized witness id in the set."""
    if not trace.events:
        return True
    return all(e.event_id in authorized_event_ids for e in trace.events)


def TraceAdmissible(trace: FormulaTrace, admissible_event_ids: frozenset[str]) -> bool:
    return all(e.event_id in admissible_event_ids for e in trace.events)


def TraceCapabilityReach(trace: FormulaTrace) -> frozenset[str]:
    return frozenset({e.resource for e in trace.events})


def trace_authority_violation(trace: FormulaTrace, authorized_event_ids: frozenset[str]) -> bool:
    return not TraceAuthorized(trace, authorized_event_ids)


@dataclass(frozen=True, slots=True)
class StatePathSemantics:
    """
    - exists_authorized: state reachable via ≥1 authorized trace
    - all_paths_authorized: every modeled trace to state is authorized
    """

    @staticmethod
    def exists_authorized_path(
        traces_to_state: tuple[FormulaTrace, ...], authorized_ids: frozenset[str]
    ) -> bool:
        return any(TraceAuthorized(t, authorized_ids) for t in traces_to_state)

    @staticmethod
    def all_paths_authorized(
        traces_to_state: tuple[FormulaTrace, ...], authorized_ids: frozenset[str]
    ) -> bool:
        if not traces_to_state:
            return True
        return all(TraceAuthorized(t, authorized_ids) for t in traces_to_state)


def demonstrate_exists_vs_all(
    event_a: FormulaTraceEvent,
    event_b: FormulaTraceEvent,
    auth_a_only: frozenset[str],
) -> tuple[bool, bool]:
    """Test helper: same end state, different path authorization."""
    trace_ok = FormulaTrace(tenant_id=event_a.tenant_id, events=(event_a,))
    trace_bad = FormulaTrace(tenant_id=event_b.tenant_id, events=(event_b,))
    exists = StatePathSemantics.exists_authorized_path((trace_ok, trace_bad), auth_a_only)
    all_ok = StatePathSemantics.all_paths_authorized((trace_ok, trace_bad), auth_a_only)
    return exists, all_ok
