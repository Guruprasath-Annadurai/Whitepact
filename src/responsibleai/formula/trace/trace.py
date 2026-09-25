# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from responsibleai.formula.version import FORMULA_SCHEMA_VERSION, FORMULA_VERSION


class TransitionClass(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    NONDETERMINISTIC = "NONDETERMINISTIC"
    AUTHORITY_EVENT = "AUTHORITY_EVENT"
    CAPABILITY_EVENT = "CAPABILITY_EVENT"


@dataclass(frozen=True, slots=True)
class FormulaTraceEvent:
    event_id: str
    tenant_id: str
    subject_id: str
    action: str
    resource: str
    timestamp: datetime
    graph_version: int
    policy_version: str
    grant_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    transition_class: TransitionClass
    before_state_hash: str
    after_state_hash: str


@dataclass(frozen=True, slots=True)
class FormulaTrace:
    tenant_id: str
    events: tuple[FormulaTraceEvent, ...]
    formula_version: str = FORMULA_VERSION
    schema_version: str = FORMULA_SCHEMA_VERSION
