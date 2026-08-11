"""The WhitePact Runtime Gateway — SPEC.md Section 2's missing piece:
"there is no single component that takes 'agent proposes action' as
input and returns one of the five decisions above as output." This is
that component's first, deliberately minimal version.

What ``evaluate()`` actually checks, in order:

1. **Authority** — does ``AuthorityContext`` actually grant this
   ``action_type``? Deterministic, no model call.
2. **Caller-declared approval requirements** — did the caller mark this
   ``action_type`` as needing human sign-off
   (``AuthorityContext.require_approval_for``)? Also deterministic and
   caller-configured, not a fabricated risk classification — Phase 9's
   risk-tiered routing (which *would* classify action types by risk
   automatically) is explicitly not implemented yet, per
   ``models.py``'s module docstring.
3. **Deterministic content scan** — every string-valued argument is run
   through the existing, tested ``GuardrailsEngine`` (PII/toxicity/custom
   pattern detection). Toxicity or a custom policy match is a hard
   ``DENY``; PII-only findings become ``ALLOW_WITH_REDACTION`` using
   ``GuardrailsEngine``'s own redaction, exactly as SPEC.md Section 3.6
   says this decision should reuse it.

No LLM call anywhere in this file — "prefer deterministic security
controls over LLM-based controls where possible" applies to the
runtime gateway most of all, since it's the one component every
governed action passes through.
"""

from __future__ import annotations

from typing import Any

from responsibleai.governance.models import (
    ActionRequest,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
)
from responsibleai.guardrails.engine import GuardrailsEngine, GuardrailsResult


class WhitePactRuntimeGateway:
    """Stateless evaluator: one ``GuardrailsEngine`` instance, reused
    across calls (it has no per-request state — see its own docstring),
    injectable so callers can supply an org-specific policy."""

    def __init__(self, guardrails: GuardrailsEngine | None = None) -> None:
        self._guardrails = guardrails or GuardrailsEngine()

    def evaluate(
        self, action: ActionRequest, authority: AuthorityContext,
    ) -> DecisionResult:
        if not authority.permits(action.action_type):
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=[f"authority_not_granted:{action.action_type}"],
            )

        if action.action_type in authority.require_approval_for:
            return DecisionResult(
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                action_id=action.action_id,
                reason_codes=[f"approval_required:{action.action_type}"],
            )

        field_results, redacted_arguments = self._scan_arguments(action.arguments)
        return self._decide_from_scan(action, field_results, redacted_arguments)

    def _scan_arguments(
        self, arguments: dict[str, Any],
    ) -> tuple[dict[str, GuardrailsResult], dict[str, Any]]:
        field_results: dict[str, GuardrailsResult] = {}
        redacted: dict[str, Any] = {}
        for key, value in arguments.items():
            if isinstance(value, str):
                result = self._guardrails.scan(value)
                field_results[key] = result
                redacted[key] = result.redacted_text if result.redacted_text is not None else value
            else:
                redacted[key] = value
        return field_results, redacted

    def _decide_from_scan(
        self,
        action: ActionRequest,
        field_results: dict[str, GuardrailsResult],
        redacted_arguments: dict[str, Any],
    ) -> DecisionResult:
        hard_block_reasons = [
            f"{field}:{reason}"
            for field, result in field_results.items()
            if result.has_toxicity or result.custom_pattern_matches
            for reason in result.block_reasons
        ]
        if hard_block_reasons:
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=hard_block_reasons,
            )

        pii_fields = [field for field, result in field_results.items() if result.has_pii]
        if pii_fields:
            return DecisionResult(
                decision=GovernanceDecision.ALLOW_WITH_REDACTION,
                action_id=action.action_id,
                reason_codes=[f"{field}:pii_redacted" for field in pii_fields],
                redacted_arguments=redacted_arguments,
            )

        return DecisionResult(decision=GovernanceDecision.ALLOW, action_id=action.action_id)
