# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evaluation vs commit fence — stale authority rejection."""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.formula.errors import VersionMismatch


@dataclass(frozen=True, slots=True)
class EvaluationPin:
    evaluation_id: str
    formula_version: str
    graph_version: int
    authority_version: int
    policy_version: str


@dataclass(frozen=True, slots=True)
class CommitFence:
    """Authority at execution commit must match or supersede evaluation pin."""

    required_authority_version: int
    required_graph_version: int

    def validate(
        self, pin: EvaluationPin, current_authority_version: int, current_graph_version: int
    ) -> None:
        if current_authority_version != pin.authority_version:
            raise VersionMismatch("authority changed since evaluation")
        if current_graph_version != pin.graph_version:
            raise VersionMismatch("graph changed since evaluation")
