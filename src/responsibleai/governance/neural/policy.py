"""Phase 4 (Enterprise Neural directive) — the fail-closed neural
consent policy evaluator. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md` Sec 9.

A narrow, single-purpose evaluator — not a reuse of
`governance/gateway.py`'s general action/risk policy engine, since
neural consent's decision surface (data class × consent category) is
genuinely different from action-type × risk-tier. Shares only the
ALLOW/DENY-with-reason shape this codebase already established
elsewhere, deliberately, for consistency of vocabulary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.neural.types import ConsentCategory, ConsentRecord


class NeuralPolicyDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class NeuralPolicyReason(StrEnum):
    CONSENT_GRANTED = "consent_granted"
    NO_CONSENT_RECORD = "no_consent_record"
    CONSENT_REVOKED = "consent_revoked"


@dataclass(frozen=True)
class NeuralPolicyResult:
    decision: NeuralPolicyDecision
    reason: NeuralPolicyReason
    category: ConsentCategory

    @property
    def is_allowed(self) -> bool:
        return self.decision is NeuralPolicyDecision.ALLOW


def evaluate_neural_data_flow(
    category: ConsentCategory,
    consent_records: tuple[ConsentRecord, ...],
) -> NeuralPolicyResult:
    """Evaluate whether a proposed data flow under *category* is
    permitted, given every `ConsentRecord` currently on file for the
    relevant subject (typically the latest one per category, but this
    function accepts the full set and picks the most recent itself, so
    callers don't need to pre-filter).

    Fail-closed per Law 7: no record for *category* → DENY. A record
    whose `status` is REVOKED → DENY, even if an older GRANTED record
    for the same category also exists — the most recent record by
    `version` always wins, mirroring the "latest declared, still-active
    wins" resolution this codebase's own repositories already use
    (e.g. `AuthorityPassportRepository`).
    """
    matching = [r for r in consent_records if r.category == category]
    if not matching:
        return NeuralPolicyResult(
            decision=NeuralPolicyDecision.DENY,
            reason=NeuralPolicyReason.NO_CONSENT_RECORD,
            category=category,
        )

    latest = max(matching, key=lambda r: r.version)
    if not latest.is_active:
        return NeuralPolicyResult(
            decision=NeuralPolicyDecision.DENY,
            reason=NeuralPolicyReason.CONSENT_REVOKED,
            category=category,
        )

    return NeuralPolicyResult(
        decision=NeuralPolicyDecision.ALLOW,
        reason=NeuralPolicyReason.CONSENT_GRANTED,
        category=category,
    )
