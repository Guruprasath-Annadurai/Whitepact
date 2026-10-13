# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.formula.future.envelope import SafeFutureEnvelope
from responsibleai.formula.future.facts import ConsequenceSemanticKey
from responsibleai.formula.future.models import ConsequenceReachability, EnvelopeStatus


def query_consequence_reachability(
    envelope: SafeFutureEnvelope,
    key: ConsequenceSemanticKey,
) -> ConsequenceReachability:
    """Interpret absence vs presence without implying Gate 5 judgment."""
    if any(f.semantic_key() == key for f in envelope.consequence_facts):
        return ConsequenceReachability.SUPPORTED
    if envelope.status == EnvelopeStatus.COMPLETE:
        return ConsequenceReachability.NOT_DERIVED
    return ConsequenceReachability.UNKNOWN
