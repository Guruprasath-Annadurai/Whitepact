# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ClosureStatus(StrEnum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class CapabilityClosureBudget:
    max_iterations: int = 64
    max_facts: int = 5000
    max_derivations: int = 20000
    max_rule_applications: int = 20000
    max_path_depth: int = 16
