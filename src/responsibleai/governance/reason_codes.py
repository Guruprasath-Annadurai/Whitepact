"""Stable reason codes for governance decisions — a first, partial step
toward replacing scattered free-form `reason_codes` strings
(`f"authority_not_granted:{action.action_type}"`,
`f"quarantine:recent_denials={n}"`, etc.) with a fixed vocabulary a
SIEM, a metrics dashboard, or a compliance auditor can match against
without parsing prose.

**Honestly partial**: this enum exists and is used at the specific call
sites listed below; it has not replaced every free-form reason string
in `gateway.py`/`quarantine.py`/`policy.py` — that's a larger, separate
migration (each existing string carries context, like the exact
violation count or policy rule ID, that a bare enum member would lose
without also keeping a detail field). Treat this as the seed of the
stable-vocabulary system, not the finished one.

Now wired into every branch of `WhitePactRuntimeGateway.evaluate()`
(`governance/gateway.py`) and the approval execution-binding invariants
in `db/approval_repository.py` — no longer "partial" in the sense of
"barely used"; every `DecisionResult.reason_codes` entry now starts
with a stable `ReasonCode.value` prefix, produced by `format_reason()`
below, which appends per-call detail (violation counts, rule IDs, field
names) after a `:` so the SIEM-matchable prefix and the human-readable
detail both survive in one string. Still "partial" in one honest sense:
`format_reason()` is a convention this module's callers follow, not a
type the `DecisionResult.reason_codes: list[str]` field enforces —
a caller could still append an arbitrary string.

Four codes below aren't in the original spec list; each is documented
at its definition as invented, following the precedent set by
`SELF_APPROVAL_REJECTED` (the invariant needed a code and inventing one
under the same naming convention was more honest than reusing an
unrelated existing one): `IDENTITY_QUARANTINED`, `LOW_TRUST_SCORE`,
`CONTENT_POLICY_VIOLATION`, `SELF_APPROVAL_REJECTED`.
"""

from __future__ import annotations

from enum import StrEnum


class ReasonCode(StrEnum):
    AUTHENTICATION_FAILED = "AUTHENTICATION_FAILED"
    AUTHORITY_NOT_DELEGATED = "AUTHORITY_NOT_DELEGATED"
    AUTHORITY_EXPIRED = "AUTHORITY_EXPIRED"
    ACTION_NOT_ALLOWED = "ACTION_NOT_ALLOWED"
    TARGET_NOT_ALLOWED = "TARGET_NOT_ALLOWED"
    VALUE_LIMIT_EXCEEDED = "VALUE_LIMIT_EXCEEDED"
    HIGH_VALUE_TRANSACTION = "HIGH_VALUE_TRANSACTION"
    POLICY_EXPLICIT_DENY = "POLICY_EXPLICIT_DENY"
    POLICY_REQUIRES_APPROVAL = "POLICY_REQUIRES_APPROVAL"
    PII_EXTERNAL_TRANSFER = "PII_EXTERNAL_TRANSFER"
    REDACTION_REQUIRED = "REDACTION_REQUIRED"
    UNTRUSTED_MCP_SERVER = "UNTRUSTED_MCP_SERVER"
    UNAPPROVED_MCP_SERVER = "UNAPPROVED_MCP_SERVER"
    TARGET_QUARANTINED = "TARGET_QUARANTINED"
    TRUST_ASSESSMENT_STALE = "TRUST_ASSESSMENT_STALE"
    GOVERNANCE_DEPENDENCY_UNAVAILABLE = "GOVERNANCE_DEPENDENCY_UNAVAILABLE"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
    APPROVAL_ACTION_MISMATCH = "APPROVAL_ACTION_MISMATCH"
    # Not in the original list; added for the self-approval invariant
    # (Section 26) — no existing code covered it.
    SELF_APPROVAL_REJECTED = "SELF_APPROVAL_REJECTED"
    # Not in the original list; added when migrating gateway.py off
    # free-form strings — no existing code covered a cross-request
    # violation-pattern quarantine trigger (distinct from
    # TARGET_QUARANTINED, which names a target/tool being quarantined,
    # not the requesting identity).
    IDENTITY_QUARANTINED = "IDENTITY_QUARANTINED"
    # Not in the original list; the closest existing code
    # (TRUST_ASSESSMENT_STALE) means something different (a stale
    # lookup, not a real low score).
    LOW_TRUST_SCORE = "LOW_TRUST_SCORE"
    # Not in the original list; covers GuardrailsEngine hard-block
    # findings (toxicity, custom pattern match) — distinct from
    # PII_EXTERNAL_TRANSFER/REDACTION_REQUIRED, which apply to the
    # PII-only, non-blocking case.
    CONTENT_POLICY_VIOLATION = "CONTENT_POLICY_VIOLATION"
    # Not in the original list; marks the synthetic ALLOW decision the
    # resume-after-approval flow (governance/approval.py's
    # build_resume_action(), mcp/governance_integration.py's
    # resume_approval()) constructs to authorize execution of an
    # action a human approved earlier — distinct from a real-time
    # ALLOW the gateway itself produced.
    RESUMED_AFTER_APPROVAL = "RESUMED_AFTER_APPROVAL"
    # Not in the original list; added for the authority-attenuation
    # invariant (`AuthorityContext`/`validate_attenuation()` in
    # models.py) — no existing code covered "a delegated authority
    # grants more than its own parent authority held."
    DELEGATION_AUTHORITY_ESCALATION = "DELEGATION_AUTHORITY_ESCALATION"
    # Not in the original list; added for the Workflow Authority Engine
    # (governance/workflow.py) -- no existing code covered "each action
    # in this sequence was individually permitted, but the sequence
    # itself matches a forbidden composition."
    AUTHORITY_COMPOSITION_VIOLATION = "AUTHORITY_COMPOSITION_VIOLATION"
    # Not in the original list; added for the Delegation Graph's
    # cascading revocation (db/delegation_repository.py's
    # revoke_branch()) -- distinct from AUTHORITY_EXPIRED (a natural
    # time-based lapse) since this is a deliberate admin action.
    AUTHORITY_REVOKED = "AUTHORITY_REVOKED"
    # Not in the original list; added for the Memory Firewall
    # (governance/memory_firewall.py) -- no existing code covered "this
    # content matches a known prompt-injection pattern aimed at
    # persistent memory specifically."
    MEMORY_FIREWALL_VIOLATION = "MEMORY_FIREWALL_VIOLATION"
    # Not in the original list; added for Memory Authority's scope
    # isolation (AuthorityContext.constraints["memory_scope"]) -- reuses
    # the allowed_targets/denied_targets pattern but for a memory
    # namespace rather than an action target.
    MEMORY_SCOPE_VIOLATION = "MEMORY_SCOPE_VIOLATION"
    # Not in the original list; added for the Autonomy Budget
    # (governance/autonomy_budget.py) -- no existing code covered "this
    # identity has executed too many autonomous actions in the window
    # and needs a human check-in," distinct from IDENTITY_QUARANTINED
    # (a pattern of bad outcomes) and APPROVAL_REQUIRED (a caller- or
    # ceiling-declared per-action-type requirement, not a volume cap).
    AUTONOMY_BUDGET_EXCEEDED = "AUTONOMY_BUDGET_EXCEEDED"


def format_reason(code: ReasonCode, /, **details: object) -> str:
    """`"{code}"` with no details, or `"{code}:k1=v1;k2=v2"` when the
    caller has context worth keeping (a violation count, a rule ID, a
    field name) — keeps the stable, SIEM-matchable prefix
    (`reason.split(":", 1)[0] == ReasonCode.X.value`) while not
    discarding the detail free-form strings used to carry, which is
    exactly the tradeoff this module's docstring flagged as the reason
    a bare enum member wasn't enough on its own."""
    if not details:
        return code.value
    detail = ";".join(f"{key}={value}" for key, value in details.items())
    return f"{code.value}:{detail}"
