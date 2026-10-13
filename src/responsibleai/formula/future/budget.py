# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.errors import InvalidCausalRule


@dataclass(frozen=True, slots=True)
class FutureEnvelopeBudget:
    max_horizon_steps: int = 8
    max_states: int = 5000
    max_consequences: int = 10000
    max_derivations: int = 20000
    max_rule_applications: int = 20000
    max_trajectories: int = 5000
    max_frontier: int = 5000
    max_path_depth: int = 16

    def validate(self) -> None:
        for name, value in (
            ("max_horizon_steps", self.max_horizon_steps),
            ("max_states", self.max_states),
            ("max_consequences", self.max_consequences),
            ("max_derivations", self.max_derivations),
            ("max_rule_applications", self.max_rule_applications),
            ("max_trajectories", self.max_trajectories),
            ("max_frontier", self.max_frontier),
            ("max_path_depth", self.max_path_depth),
        ):
            if value <= 0:
                raise InvalidCausalRule(f"{name} must be positive")
