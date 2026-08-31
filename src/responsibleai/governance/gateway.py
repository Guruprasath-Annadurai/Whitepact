# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The WhitePact Runtime Gateway — SPEC.md Section 2's missing piece:
"there is no single component that takes 'agent proposes action' as
input and returns one of the five decisions above as output."

What ``evaluate()`` checks, in order:

-1. **Workflow composition** (optional — only when a caller passes
   ``workflow_rules``) — does this action, combined with the agent's
   own recent action history, complete a forbidden sequence per
   ``workflow.check_composition_violation()``? Each step in such a
   sequence may itself be individually permitted; the violation is in
   the composition, not any single action. Checked before per-action
   authority, mirroring quarantine's "a broader pattern overrides a
   single valid-looking action" precedent. No ``workflow_rules``
   supplied (every caller before this existed) — skipped entirely.
0. **Authority attenuation** (optional — only when a caller passes
   ``parent_authority``) — does this ``AuthorityContext`` stay within
   the authority that delegated it, per
   ``models.validate_attenuation()``? Checked before the authority's
   own action-type grant, since a delegated authority that itself
   exceeds its parent is invalid regardless of what it claims to
   permit. No ``parent_authority`` supplied (every caller before this
   existed, and any caller not tracking a delegation chain today) —
   this step is skipped entirely, identical to pre-existing behavior.
0.5. **Intent Contract** (optional — only when a caller passes
   ``intent``, Authority Everywhere Phase 4) — does this action stay
   within the goal/bounds the calling agent itself declared for this
   task, per ``IntentContract.intent_violation()``? Distinct from step
   0 (which checks the delegated authority chain) and step 3b below
   (which checks org-granted constraints) — this checks what the agent
   *promised*, not what the org *delegated*. No ``intent`` supplied
   (every caller before this existed, and any caller with no declared
   contract for this agent) — skipped entirely.
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
   says this decision should reuse it. Alongside it, when
   ``action_type == "rai_memory_write_check"`` and a ``content`` string
   argument is present, ``governance/memory_firewall.py``'s
   ``scan_memory_write()`` runs too — a match is also a hard ``DENY``
   (Memory Authority/Memory Firewall, v3 authority-layer work; see that
   module's docstring for why persistent-memory writes get a dedicated
   injection-pattern scan on top of PII/toxicity).
5b. **Autonomy Budget** (optional — only when a caller passes
   ``autonomy_budget``, v3 authority-layer work) — checked right after
   the hard-block/toxicity check, before PII-redaction and trust: if
   the identity has already accrued ``autonomy_budget.max_autonomous_actions``
   ``ALLOW``/``ALLOW_WITH_REDACTION`` decisions within
   ``autonomy_budget.window_minutes`` (a count the caller computes via
   ``autonomy_budget.recent_autonomous_action_count()``, same
   DB-query-in-the-caller pattern as quarantine below), this call is
   forced to ``REQUIRE_APPROVAL`` regardless of what it would otherwise
   have decided — a circuit breaker on unsupervised *volume*, not on
   bad outcomes. No ``autonomy_budget`` supplied (every caller before
   this existed, and any org that hasn't configured one) — skipped
   entirely.
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
   known model scoring below ``LOW_TRUST_SCORE_THRESHOLD``, *or* when
   ``trust_state.stale`` is set (Continuous MCP Trust, v3
   authority-layer work: ``TrustClient`` attempted a live re-fetch
   before this call and it failed, so this decision would otherwise be
   made on a result that couldn't be freshly reverified). Never
   escalates a redaction or a deny, and never fires for an unknown or
   unscored model — see ``_trust_reason`` below.

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

from responsibleai.governance.autonomy_budget import AutonomyBudgetPolicy
from responsibleai.governance.causal_influence import analyze_causal_influence, parse_provenance
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.memory_firewall import scan_memory_write
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
from responsibleai.governance.workflow import (
    TimestampedAction,
    WorkflowSequenceRule,
    check_composition_violation,
)
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
        recent_actions: list[TimestampedAction] | None = None,
        workflow_rules: list[WorkflowSequenceRule] | None = None,
        autonomy_budget: AutonomyBudgetPolicy | None = None,
        recent_autonomous_action_count: int = 0,
        intent: IntentContract | None = None,
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

        if workflow_rules:
            composition_reason = check_composition_violation(
                recent_actions or [],
                action.action_type,
                action.proposed_at,
                workflow_rules,
            )
            if composition_reason is not None:
                return DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[composition_reason],
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

        if intent is not None:
            intent_reason = intent.intent_violation(action)
            if intent_reason is not None:
                return DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[intent_reason],
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
            autonomy_budget=autonomy_budget,
            recent_autonomous_action_count=recent_autonomous_action_count,
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
        *,
        autonomy_budget: AutonomyBudgetPolicy | None = None,
        recent_autonomous_action_count: int = 0,
    ) -> DecisionResult:
        hard_block_reasons = [
            format_reason(ReasonCode.CONTENT_POLICY_VIOLATION, field=field, detail=reason)
            for field, result in field_results.items()
            if result.has_toxicity or result.custom_pattern_matches
            for reason in result.block_reasons
        ]

        memory_firewall_reason = self._memory_firewall_reason(action)
        if memory_firewall_reason is not None:
            hard_block_reasons.append(memory_firewall_reason)

        causal_block_reason, causal_untrusted_reason = self._causal_influence_reasons(action)
        if causal_block_reason is not None:
            hard_block_reasons.append(causal_block_reason)
        elif causal_untrusted_reason is not None:
            # Softer, non-blocking signal -- attached to whatever
            # decision this action ends up with below (including a
            # plain ALLOW), never a reason on its own to deny. See
            # _causal_influence_reasons()'s own docstring.
            policy_reason_codes.append(causal_untrusted_reason)

        if hard_block_reasons:
            return DecisionResult(
                decision=GovernanceDecision.DENY,
                action_id=action.action_id,
                reason_codes=[*policy_reason_codes, *hard_block_reasons],
                risk_tier=risk_tier,
                policy_version=policy_version,
            )

        if (
            autonomy_budget is not None
            and recent_autonomous_action_count >= autonomy_budget.max_autonomous_actions
        ):
            return DecisionResult(
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                action_id=action.action_id,
                reason_codes=[
                    *policy_reason_codes,
                    format_reason(
                        ReasonCode.AUTONOMY_BUDGET_EXCEEDED,
                        recent_autonomous_actions=recent_autonomous_action_count,
                        limit=autonomy_budget.max_autonomous_actions,
                        window_minutes=autonomy_budget.window_minutes,
                    ),
                ],
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

        trust_reason = self._trust_reason(action)
        if trust_reason is not None:
            return DecisionResult(
                decision=GovernanceDecision.REQUIRE_APPROVAL,
                action_id=action.action_id,
                reason_codes=[*policy_reason_codes, trust_reason],
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
    def _memory_firewall_reason(action: ActionRequest) -> str | None:
        """``None`` unless this is a memory-write check carrying a
        ``content`` string that matches a known injection pattern --
        see ``governance/memory_firewall.py`` for what's scanned for
        and why memory gets a dedicated check on top of the general
        PII/toxicity scan every action's arguments already go through.
        Gated to ``rai_memory_write_check`` specifically, not every
        action with a ``content`` argument -- this scan is about memory
        persistence risk, not a second general-purpose content filter."""
        if action.action_type != "rai_memory_write_check":
            return None
        content = action.arguments.get("content")
        if not isinstance(content, str):
            return None
        result = scan_memory_write(content)
        if not result.is_blocked:
            return None
        return format_reason(
            ReasonCode.MEMORY_FIREWALL_VIOLATION,
            patterns=",".join(result.matched_patterns),
        )

    @staticmethod
    def _causal_influence_reasons(action: ActionRequest) -> tuple[str | None, str | None]:
        """Causal Influence Firewall (``governance/causal_influence.py``,
        Authority Everywhere Phase 7) — generalizes
        ``_memory_firewall_reason`` above from "memory writes only" to
        any provenance a caller declares via the reserved
        ``_provenance`` argument key (same argument-driven,
        action-type-agnostic pattern ``AuthorityContext.constraints``'
        ``memory_scope`` already uses: absent key, this never fires,
        identical to every caller before this existed).

        Returns ``(hard_block_reason, informational_untrusted_reason)``
        — at most one is non-``None``. A matched injection pattern in
        any provenance entry's content is always DENY-worthy on its own
        and takes precedence; mere untrusted/unknown provenance with no
        pattern match is a softer, evidence-visible marker the caller
        (``_decide_from_scan``) attaches to whatever decision this
        action otherwise receives, never a block by itself."""
        provenance = parse_provenance(action.arguments.get("_provenance"))
        if not provenance:
            return None, None
        result = analyze_causal_influence(provenance)
        if result.is_blocked:
            return (
                format_reason(
                    ReasonCode.CAUSAL_INFLUENCE_VIOLATION,
                    patterns=",".join(result.matched_patterns),
                    sources=",".join(kind.value for kind in result.matched_entry_kinds),
                ),
                None,
            )
        if result.has_untrusted_influence:
            return (
                None,
                format_reason(
                    ReasonCode.CAUSAL_INFLUENCE_UNTRUSTED_SOURCE,
                    sources=",".join(kind.value for kind in result.untrusted_entry_kinds),
                ),
            )
        return None, None

    @staticmethod
    def _trust_reason(action: ActionRequest) -> str | None:
        """None unless the Trust Index check for this action's model
        surfaced something worth a human looking at. Checks (first
        match wins):

        1. ``trust_state.stale`` (Continuous MCP Trust) — a live
           re-fetch was attempted and failed, so this decision would
           otherwise rest on a result ``TrustClient`` couldn't just
           freshly reverify. Fires regardless of score, including for
           an unknown model — staleness is about *how* the data was
           obtained, not what it says.
        2. A known model scoring below ``LOW_TRUST_SCORE_THRESHOLD`` —
           an unknown or unscored model is not treated as untrustworthy
           (same fail-open-on-unknown reasoning
           ``TrustCheckResult.passes()`` documents), only a model with a
           real, low score escalates.
        """
        trust_state = action.agent.trust_state
        if trust_state is None:
            return None
        if trust_state.stale:
            return format_reason(ReasonCode.TRUST_ASSESSMENT_STALE, model=trust_state.model)
        if not trust_state.known:
            return None
        score = trust_state.overall_score
        if score is None or score >= LOW_TRUST_SCORE_THRESHOLD:
            return None
        return format_reason(
            ReasonCode.LOW_TRUST_SCORE, score=f"{score:.1f}", threshold=LOW_TRUST_SCORE_THRESHOLD
        )
