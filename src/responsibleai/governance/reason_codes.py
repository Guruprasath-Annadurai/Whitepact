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

Currently wired into:
- `db/approval_repository.py`'s `consume()` — `APPROVAL_ACTION_MISMATCH`.
- `db/approval_repository.py`'s `resolve()` — `SELF_APPROVAL_REJECTED`
  (not in the original list of examples, added because the invariant
  needed a code and inventing one under the same naming convention was
  more honest than reusing an unrelated existing code).
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
