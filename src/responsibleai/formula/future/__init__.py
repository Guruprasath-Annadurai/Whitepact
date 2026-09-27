# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Gate 4 — Safe Future Envelope + causal consequence engine."""

from responsibleai.formula.future.engine import compute_safe_future_envelope
from responsibleai.formula.future.envelope import SafeFutureEnvelope
from responsibleai.formula.future.query import query_consequence_reachability
from responsibleai.formula.future.rules import CausalRule

__all__ = [
    "CausalRule",
    "SafeFutureEnvelope",
    "compute_safe_future_envelope",
    "query_consequence_reachability",
]
