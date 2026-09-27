# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from responsibleai.formula.errors import InvalidCapability


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

    def validate(self) -> None:
        if self.max_iterations <= 0:
            raise InvalidCapability("max_iterations must be positive")
        if self.max_facts <= 0:
            raise InvalidCapability("max_facts must be positive")
        if self.max_derivations <= 0:
            raise InvalidCapability("max_derivations must be positive")
        if self.max_rule_applications <= 0:
            raise InvalidCapability("max_rule_applications must be positive")
        if self.max_path_depth <= 0:
            raise InvalidCapability("max_path_depth must be positive")
