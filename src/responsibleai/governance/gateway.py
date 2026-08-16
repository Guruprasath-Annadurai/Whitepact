"""The WhitePact Runtime Gateway — SPEC.md Section 2's missing piece:
"there is no single component that takes 'agent proposes action' as
input and returns one of the five decisions above as output."

What ``evaluate()`` checks, in order:

0. **Authority attenuation** (optional — only when a caller passes
   ``parent_authority``) — does this ``AuthorityContext`` stay within
   the authority that delegated it, per
   ``models.validate_attenuation()``? Checked before the authority's
   own action-type grant, since a delegated authority that itself
   exceeds its parent is invalid regardless of what it claims to
   permit. No ``parent_authority`` supplied (every caller before this
   existed, and any caller not tracking a delegation chain today) —
   this step is skipped entirely, identical to pre-existing behavior.
1. **Authority** — does ``AuthorityContext`` actually grant this
   ``action_type``? Deterministic, no model call.
2. **Caller-declared approval requirements** — did the caller mark this
   ``action_type`` as needing human sign-off
   (``AuthorityContext.require_approval_for``)? Deterministic and
   caller-configured, checked before risk/policy so an agent's own
   authority grant is always the first word.
3. **Risk classification** (Phase 9, ``governance/risk.py``) — every
   action gets a ``RiskTier``, always recorded on the result, whether or
   not a ``Policy`` is supplied.
3b. **Authority constraints** (``AuthorityContext.constraint_violation()``,
   v3 authority-layer work) — a granted action type can still be denied
   by a value limit, target pattern, or time window recorded on the
   authority grant itself; see that method's docstring for the fixed
   set of recognized constraint keys.
4. **Policy** (Phase 10, ``governance/policy.py``, optional) — if a
   ``Policy`` is passed and a rule matches, a ``DENY``/``REQUIRE_APPROVAL``
   effect short-circuits immediately; an ``ALLOW`` effect is recorded but
   does *not* skip the content scan below (defense in depth: an org
   allowing an action type doesn't mean skip PII/toxicity scanning of its
   arguments). No ``Policy`` supplied — behavior is identical to before
   Phase 9/10 existed; this is additive, not a required argument.
5. **Deterministic content scan** — every string-valued argument is run
   through the existing, tested ``GuardrailsEngine`` (PII/toxicity/custom
   pattern detection). Toxicity or a custom policy match is a hard
   ``DENY``; PII-only findings become ``ALLOW_WITH_REDACTION`` using
   ``GuardrailsEngine``'s own redaction, exactly as SPEC.md Section 3.6
   says this decision should reuse it.
6. **Quarantine** (``recent_violation_count``, ``governance/quarantine.py``)
   — checked *first*, before authority, so a pattern of recent ``DENY``
   decisions overrides even a valid authority grant. The count itself is
   computed by the caller (an async DB query against ``EvidenceRepository``
   — see ``quarantine.recent_violation_count()``) and passed in as a
   plain int, keeping this method itself synchronous and DB-free.
7. **Trust state** (``action.agent.trust_state``, populated by
   ``governance/trust_integration.py`` when the action names a
   third-party model/provider) — an otherwise-``ALLOW`` decision is
   downgraded to ``REQUIRE_APPROVAL`` when the Trust Index reports a
   known model scoring below ``LOW_TRUST_SCORE_THRESHOLD``. Never
   escalates a redaction or a deny, and never fires for an unknown or
   unscored model — see ``_apply_trust_state`` below.

No LLM call anywhere in this file — "prefer deterministic security
controls over LLM-based controls where possible" applies to the
runtime gateway most of all, since it's the one component every
governed action passes through. The Trust Index score consulted above
is itself a stored, previously-computed value (not a live LLM judgment
call made here), consistent with that rule.

**Risk-tiered fast/deep path split — investigated, deliberately not
built as a risk-tier gate**: the v3 spec proposes routing MINIMAL/LOW
risk actions through a cheaper path that skips full content scanning.
Investigated for this gateway specifically and rejected in that form:
``GuardrailsEngine`` (step 5) is pure ``re``-module regex matching, not
an LLM or NLP call (see its own module docstring) — there is no
"expensive deep path" to skip *to* a cheap one, cost is already
O(argument string length) regardless of risk tier. Worse, several
``LOW``-tier tools (``rai_scan``, ``rai_pii_report``, ``rai_stream_scan``)
exist specifically to carry free-text arguments through this exact
scan — gating step 5 on risk tier would skip PII/toxicity detection for
the tools whose entire purpose is PII/toxicity detection, a real
security regression, not an optimization. The one fast path that *is*
safe already exists implicitly: ``_scan_arguments`` only calls
``GuardrailsEngine.scan()`` on string-valued arguments, so an action
with zero string arguments (true of every ``MINIMAL``-tier identity/
health tool) already never invokes the engine at all — no risk-tier
branch needed to get that for free.
"""

from __future__ import annotations

from typing import Any

from responsibleai.governance.models import (
    ActionRequest,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    validate_attenuation,
)
from responsibleai.governance.policy import Policy
from responsibleai.governance.quarantine import QUARANTINE_VIOLATION_THRESHOLD
from responsibleai.governance.reason_codes import ReasonCode, format_reason
from responsibleai.governance.risk import RiskTier, classify_action_risk
from responsibleai.guardrails.engine import GuardrailsEngine, GuardrailsResult

LOW_TRUST_SCORE_THRESHOLD = 40.0

_POLICY_EFFECT_CODES = {
    GovernanceDecision.DENY: ReasonCode.POLICY_EXPLICIT_DENY,
    GovernanceDecision.REQUIRE_APPROVAL: ReasonCode.POLICY_REQUIRES_APPROVAL,
}


class WhitePactRuntimeGateway:
    """Stateless evaluator: one ``GuardrailsEngine`` instance, reused
    across calls (it has no per-request state — see its own docstring).
    ``Policy`` is passed per call, not to the constructor, since it's
    per-organization and one gateway instance may serve many orgs."""

    def __init__(self, guardrails: GuardrailsEngine | None = None) -> None:
        self._guardrails = guardrails or GuardrailsEngine()

    def evaluate(
        self,
        action: ActionRequest,
        authority: AuthorityContext,
        policy: Policy | None = None,
        *,
        recent_violation_count: int = 0,
        parent_authority: AuthorityContext | None = None,
    ) -> DecisionResult:
        risk_tier = classify_action_risk(action.action_type, action.target)

        if recent_violation_count >= QUARANTINE_VIOLATION_THRESHOLD:
            return DecisionResult(
                decision=GovernanceDecision.QUARANTINE,
                action_id=action.action_id,
                reason_codes=[
                    format_reason(
                        ReasonCode.IDENTITY_QUARANTINED,
                        recent_denials=recent_violation_count,
                        threshold=QUARANTINE_VIOLATION_THRESHOLD,
                    ),
                ],
                risk_tier=risk_tier,
            )

        if parent_authority is not None:
            escalation_reason = validate_attenuation(parent_authority, authority)
            if escalation_reason is not None:
                return DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[escalation_reason],
                    risk_tier=risk_tier,
                )

        if not authority.permits(action.action_type):
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=[
                    format_reason(
                        ReasonCode.AUTHORITY_NOT_DELEGATED, action_type=action.action_type
                    )
                ],
                risk_tier=risk_tier,
            )

        if action.action_type in authority.require_approval_for:
            return DecisionResult(
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                action_id=action.action_id,
                reason_codes=[
                    format_reason(ReasonCode.APPROVAL_REQUIRED, action_type=action.action_type)
                ],
                risk_tier=risk_tier,
            )

        constraint_violation = authority.constraint_violation(action)
        if constraint_violation is not None:
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=[constraint_violation],
                risk_tier=risk_tier,
            )

        policy_reason_codes: list[str] = []
        policy_version = policy.version if policy is not None else None

        if policy is not None:
            match = policy.evaluate(action, risk_tier)
            if match is not None:
                policy_code = _POLICY_EFFECT_CODES.get(match.rule.effect)
                reason = (
                    format_reason(
                        policy_code, rule_id=match.rule.rule_id, rule_reason=match.rule.reason_code
                    )
                    if policy_code is not None
                    # ALLOW effect: no dedicated ReasonCode (an explicit
                    # allow isn't a "reason to block/flag"), keep the
                    # rule_id/reason_code trail as plain detail so
                    # evidence still shows which rule matched.
                    else f"policy_allow:rule_id={match.rule.rule_id};rule_reason={match.rule.reason_code}"
                )
                if match.rule.effect in (
                    GovernanceDecision.DENY,
                    GovernanceDecision.REQUIRE_APPROVAL,
                ):
                    return DecisionResult(
                        decision=match.rule.effect,
                        action_id=action.action_id,
                        reason_codes=[reason],
                        risk_tier=risk_tier,
                        policy_version=policy_version,
                    )
                policy_reason_codes.append(reason)

        field_results, redacted_arguments = self._scan_arguments(action.arguments)
        return self._decide_from_scan(
            action,
            field_results,
            redacted_arguments,
            risk_tier,
            policy_reason_codes,
            policy_version,
        )

    def _scan_arguments(
        self,
        arguments: dict[str, Any],
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
        risk_tier: RiskTier,
        policy_reason_codes: list[str],
        policy_version: int | None = None,
    ) -> DecisionResult:
        hard_block_reasons = [
            format_reason(ReasonCode.CONTENT_POLICY_VIOLATION, field=field, detail=reason)
            for field, result in field_results.items()
            if result.has_toxicity or result.custom_pattern_matches
            for reason in result.block_reasons
        ]
        if hard_block_reasons:
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=[*policy_reason_codes, *hard_block_reasons],
                risk_tier=risk_tier,
                policy_version=policy_version,
            )

        pii_fields = [field for field, result in field_results.items() if result.has_pii]
        if pii_fields:
            return DecisionResult(
                decision=GovernanceDecision.ALLOW_WITH_REDACTION,
                action_id=action.action_id,
                reason_codes=[
                    *policy_reason_codes,
                    *[
                        format_reason(ReasonCode.REDACTION_REQUIRED, field=field)
                        for field in pii_fields
                    ],
                ],
                redacted_arguments=redacted_arguments,
                risk_tier=risk_tier,
                policy_version=policy_version,
            )

        low_trust_reason = self._low_trust_reason(action)
        if low_trust_reason is not None:
            return DecisionResult(
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                action_id=action.action_id,
                reason_codes=[*policy_reason_codes, low_trust_reason],
                risk_tier=risk_tier,
                policy_version=policy_version,
            )

        return DecisionResult(
            decision=GovernanceDecision.ALLOW,
            action_id=action.action_id,
            reason_codes=policy_reason_codes,
            risk_tier=risk_tier,
            policy_version=policy_version,
        )

    @staticmethod
    def _low_trust_reason(action: ActionRequest) -> str | None:
        """None unless the Trust Index has scored this action's model as
        both *known* and below ``LOW_TRUST_SCORE_THRESHOLD`` — an unknown
        or unscored model is not treated as untrustworthy (same
        fail-open-on-unknown reasoning ``TrustCheckResult.passes()``
        documents), only a model with a real, low score escalates."""
        trust_state = action.agent.trust_state
        if trust_state is None or not trust_state.known:
            return None
        score = trust_state.overall_score
        if score is None or score >= LOW_TRUST_SCORE_THRESHOLD:
            return None
        return format_reason(
            ReasonCode.LOW_TRUST_SCORE, score=f"{score:.1f}", threshold=LOW_TRUST_SCORE_THRESHOLD
        )
