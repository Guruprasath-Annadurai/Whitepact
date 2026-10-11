# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Four narrow, read-only WhitePact authority tools for the hosted MCP transport.

Founder decision 3 (Option B): an AI assistant connected to a tenant may *look at* that
tenant's authority state. It may not obtain authority, consume an approval, change a policy,
or cause a side effect. Everything here is therefore:

* hosted-only and tenant-scoped -- the organization is taken from the already-verified
  credential (``OrgContext``), never from a tool argument;
* role-gated per tool (explicit allow-lists, not a ">= level" shortcut);
* rate limited per organization and per tool through the durable, shared limiter, failing
  closed when the limiter's storage is unavailable;
* minimal in what it discloses: no rule bodies, no approval arguments or targets, no
  evidence payloads, bounded page sizes;
* built on the canonical evaluators (``Policy.evaluate``, ``classify_action_risk``,
  ``EvidenceRepository.verify_chain_status``) -- no second implementation of the logic.

What the tools deliberately never do: call the gateway's ``evaluate``/``authorize_execution``
(those mint grants and write evidence), call ``ApprovalRepository.resolve``/``consume``,
touch ``PolicyRepository`` mutators, or write anywhere. The read-only property is checked
three ways: a static test that this module never names a mutator, a test that the authority
tables are byte-identical before and after all four calls, and a Postgres test that runs the
tools as a role holding only SELECT on the authority tables (docs/launch/AUTHORITY_READ_PATH.md).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final

from mcp import types

from responsibleai.rbac.models import Role

if TYPE_CHECKING:
    from responsibleai.mcp.governance_integration import GovernanceServices
    from responsibleai.rbac.models import OrgContext

POLICY_STATUS: Final = "whitepact_policy_status"
SIMULATE_POLICY: Final = "whitepact_simulate_policy"
LIST_PENDING_APPROVALS: Final = "whitepact_list_pending_approvals"
VERIFY_EVIDENCE: Final = "whitepact_verify_evidence"

AUTHORITY_TOOL_NAMES: Final = frozenset(
    {POLICY_STATUS, SIMULATE_POLICY, LIST_PENDING_APPROVALS, VERIFY_EVIDENCE}
)

# Explicit allow-lists. A role that is not named here is refused, including any role added
# to the enum later (default deny).
_ALLOWED_ROLES: Final[dict[str, frozenset[Role]]] = {
    POLICY_STATUS: frozenset({Role.OWNER, Role.ADMIN, Role.SECURITY_ADMIN, Role.ANALYST}),
    SIMULATE_POLICY: frozenset({Role.OWNER, Role.ADMIN, Role.SECURITY_ADMIN, Role.ANALYST}),
    LIST_PENDING_APPROVALS: frozenset({Role.OWNER, Role.ADMIN, Role.SECURITY_ADMIN, Role.APPROVER}),
    VERIFY_EVIDENCE: frozenset(
        {Role.OWNER, Role.ADMIN, Role.SECURITY_ADMIN, Role.ANALYST, Role.AUDITOR}
    ),
}

# Requests per rolling minute, per organization and tool. Evidence verification walks the
# tenant's whole chain, so it is the tightest.
_RATE_LIMITS: Final[dict[str, int]] = {
    POLICY_STATUS: 30,
    SIMULATE_POLICY: 60,
    LIST_PENDING_APPROVALS: 30,
    VERIFY_EVIDENCE: 6,
}
_RATE_WINDOW_SECONDS: Final = 60.0

MAX_PAGE_SIZE: Final = 50
DEFAULT_PAGE_SIZE: Final = 20
MAX_CURSOR: Final = 150  # list_pending() caps at 200 rows; keep headroom for the +1 probe.

_TOKEN = re.compile(r"[A-Za-z0-9_.:\-/]{1,128}")
_HEX64 = re.compile(r"[0-9a-f]{64}")
_RISK_TIERS: Final = ("MINIMAL", "LOW", "MEDIUM", "HIGH")

_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def _tool(name: str, title: str, description: str, schema: dict[str, Any]) -> types.Tool:
    return types.Tool(
        name=name,
        title=title,
        description=description,
        inputSchema={"type": "object", "additionalProperties": False, **schema},
        annotations=_ANNOTATIONS.model_copy(update={"title": title}),
    )


AUTHORITY_TOOL_DEFS: Final[list[types.Tool]] = [
    _tool(
        POLICY_STATUS,
        "WhitePact policy status",
        "Read-only. Summarize this organization's policy: version, rule count by effect, and "
        "whether its change history verifies. Does not list rule contents and changes nothing.",
        {"properties": {}},
    ),
    _tool(
        SIMULATE_POLICY,
        "Simulate WhitePact policy",
        "Read-only, policy-only simulation: which effect this organization's policy rules "
        "would give an action type and target. It is NOT an authorization: trust, authority "
        "delegation, approvals, budgets, guardrails and quarantine are not evaluated, nothing "
        "is recorded, and no execution grant is issued.",
        {
            "properties": {
                "action_type": {"type": "string", "minLength": 1, "maxLength": 128},
                "target": {"type": "string", "minLength": 1, "maxLength": 128},
                "risk_tier": {
                    "type": "string",
                    "enum": list(_RISK_TIERS),
                    "description": "Optional. Defaults to the platform's own classification.",
                },
            },
            "required": ["action_type", "target"],
        },
    ),
    _tool(
        LIST_PENDING_APPROVALS,
        "List pending approvals",
        "Read-only. List this organization's pending approval requests (id, action type, risk "
        "tier, reason codes, timestamps). Arguments and targets are never returned. Cannot "
        "approve, reject or consume anything.",
        {
            "properties": {
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": MAX_PAGE_SIZE,
                    "default": DEFAULT_PAGE_SIZE,
                },
                "cursor": {
                    "type": "string",
                    "maxLength": 8,
                    "description": "Opaque value from a previous response's next_cursor.",
                },
            }
        },
    ),
    _tool(
        VERIFY_EVIDENCE,
        "Verify evidence chain",
        "Read-only. Re-verify this organization's evidence hash chain and report whether it is "
        "internally consistent. This proves internal consistency only; the chain is not "
        "externally anchored, so it cannot prove nothing was rewritten by someone with "
        "database write access. Optionally compare the head to a hash you recorded earlier.",
        {
            "properties": {
                "expected_head_hash": {
                    "type": "string",
                    "pattern": "^[0-9a-f]{64}$",
                    "description": "Optional head hash you recorded earlier.",
                }
            }
        },
    ),
]


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": code, "message": message}


@dataclass(frozen=True)
class AuthorityReadBackend:
    """The only repositories the read path may touch, built on its own database engine/role."""

    policy_repo: Any
    approval_repo: Any
    evidence_repo: Any


@dataclass(frozen=True)
class AuthorityReadService:
    """Executes the four tools against the governance repositories, read-only."""

    services: GovernanceServices
    limiter: Any  # DurableIdentityRateLimiter-compatible: await check(key, limit=, window_seconds=)

    async def call(self, name: str, arguments: dict[str, Any], ctx: OrgContext) -> dict[str, Any]:
        if name not in AUTHORITY_TOOL_NAMES:
            return _error("unknown_tool", f"Unknown authority tool: {name}")
        if not ctx.org_id or ctx.is_legacy:
            return _error(
                "tenant_credential_required",
                "Authority tools need an organization-scoped credential.",
            )
        if ctx.role not in _ALLOWED_ROLES[name]:
            return _error(
                "role_not_permitted",
                f"Your role ({ctx.role.value}) is not permitted to use {name}.",
            )
        rejection = _validate_arguments(name, arguments)
        if rejection is not None:
            return rejection
        limited = await self._rate_limit(name, ctx.org_id)
        if limited is not None:
            return limited
        handler = {
            POLICY_STATUS: self._policy_status,
            SIMULATE_POLICY: self._simulate_policy,
            LIST_PENDING_APPROVALS: self._list_pending,
            VERIFY_EVIDENCE: self._verify_evidence,
        }[name]
        try:
            return await handler(ctx.org_id, arguments)
        except Exception:
            # Never leak driver or SQL detail through a read tool.
            return _error("authority_read_unavailable", "The authority state could not be read.")

    async def _rate_limit(self, name: str, org_id: str) -> dict[str, Any] | None:
        from responsibleai.enterprise.errors import EnterpriseError

        try:
            await self.limiter.check(
                f"authority_read:{org_id}:{name}",
                limit=_RATE_LIMITS[name],
                window_seconds=_RATE_WINDOW_SECONDS,
            )
        except EnterpriseError as exc:
            if exc.code == "RATE_LIMITED":
                return _error("rate_limited", "Too many requests. Try again shortly.")
            return _error(
                "authority_read_unavailable",
                "Abuse protection is unavailable. No data was read.",
            )
        except Exception:
            return _error(
                "authority_read_unavailable",
                "Abuse protection is unavailable. No data was read.",
            )
        return None

    async def _policy_status(self, org_id: str, _arguments: dict[str, Any]) -> dict[str, Any]:
        repo = self.services.policy_repo
        policy = await repo.get_policy(org_id)
        by_effect: dict[str, int] = {}
        for rule in policy.rules:
            by_effect[rule.effect.value] = by_effect.get(rule.effect.value, 0) + 1
        return {
            "policy_version": policy.version,
            "rule_count": len(policy.rules),
            "rules_by_effect": dict(sorted(by_effect.items())),
            "history_chain_valid": bool(await repo.verify_history(org_id)),
            "rule_contents_disclosed": False,
        }

    async def _simulate_policy(self, org_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext
        from responsibleai.governance.risk import RiskTier, classify_action_risk

        action_type = arguments["action_type"]
        target = arguments["target"]
        tier = (
            RiskTier(arguments["risk_tier"])
            if "risk_tier" in arguments
            else classify_action_risk(action_type, target)
        )
        policy = await self.services.policy_repo.get_policy(org_id)
        identity = IdentityContext(identity_id="policy-simulation", kind="agent", org_id=org_id)
        request = ActionRequest(
            agent=AgentContext(identity=identity, organization_id=org_id),
            action_type=action_type,
            target=target,
        )
        match = policy.evaluate(request, tier)
        return {
            "simulation": "policy_only",
            "is_authorization": False,
            "execution_grant_issued": False,
            "recorded": False,
            "risk_tier": tier.value,
            "policy_version": policy.version,
            "policy_effect": match.rule.effect.value if match else "NO_MATCHING_RULE",
            "reason_code": match.rule.reason_code if match else None,
            "not_evaluated": [
                "agent trust state",
                "authority delegation and ceilings",
                "approval state and four-eyes requirements",
                "autonomy budgets",
                "guardrails and content scanning",
                "quarantine and revocation epochs",
            ],
        }

    async def _list_pending(self, org_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        limit = int(arguments.get("limit", DEFAULT_PAGE_SIZE))
        offset = int(arguments.get("cursor", "0"))
        rows = await self.services.approval_repo.list_pending(org_id, limit=offset + limit + 1)
        page = rows[offset : offset + limit]
        more = len(rows) > offset + limit and offset + limit <= MAX_CURSOR
        return {
            "approvals": [
                {
                    "approval_id": a.approval_id,
                    "action_type": a.action_type,
                    "risk_tier": a.risk_tier,
                    "reason_codes": list(a.reason_codes),
                    "requested_at": a.requested_at.isoformat(),
                    "expires_at": a.expires_at.isoformat() if a.expires_at else None,
                    "required_approvals": a.required_approvals,
                }
                for a in page
            ],
            "returned": len(page),
            "next_cursor": str(offset + limit) if more else None,
            "arguments_and_targets_disclosed": False,
        }

    async def _verify_evidence(self, org_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        repo = self.services.evidence_repo
        status = await repo.verify_chain_status(org_id)
        head = await repo.get_chain_head(org_id)
        head_hash, sequence = head if head else (None, 0)
        result: dict[str, Any] = {
            "chain_status": status.value,
            "scope": "internal_chain_consistency",
            "externally_anchored": False,
            "head_sequence": sequence,
            "head_hash": head_hash,
            "limitation": (
                "Internal consistency only. Without an external anchor this cannot prove the "
                "chain was not rewritten by someone able to write to the database."
            ),
        }
        expected = arguments.get("expected_head_hash")
        if expected is not None:
            result["matches_expected_head"] = head_hash == expected
        return result


def _validate_arguments(name: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
    """Reject anything the schema forbids. The SDK validates too, but a hosted tool must not
    rely on the client having done so."""
    allowed: dict[str, frozenset[str]] = {
        POLICY_STATUS: frozenset(),
        SIMULATE_POLICY: frozenset({"action_type", "target", "risk_tier"}),
        LIST_PENDING_APPROVALS: frozenset({"limit", "cursor"}),
        VERIFY_EVIDENCE: frozenset({"expected_head_hash"}),
    }
    extra = sorted(set(arguments) - allowed[name])
    if extra:
        return _error("invalid_arguments", f"Unexpected argument(s): {', '.join(extra)}.")
    if name == SIMULATE_POLICY:
        for key in ("action_type", "target"):
            value = arguments.get(key)
            if not isinstance(value, str) or not _TOKEN.fullmatch(value):
                return _error(
                    "invalid_arguments", f"{key} must be 1-128 characters of [A-Za-z0-9_.:-/]."
                )
        tier = arguments.get("risk_tier")
        if tier is not None and tier not in _RISK_TIERS:
            return _error("invalid_arguments", "risk_tier must be MINIMAL, LOW, MEDIUM or HIGH.")
    elif name == LIST_PENDING_APPROVALS:
        limit = arguments.get("limit", DEFAULT_PAGE_SIZE)
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= MAX_PAGE_SIZE:
            return _error("invalid_arguments", f"limit must be an integer 1-{MAX_PAGE_SIZE}.")
        cursor = arguments.get("cursor", "0")
        if not isinstance(cursor, str) or not cursor.isdigit() or int(cursor) > MAX_CURSOR:
            return _error("invalid_arguments", "cursor is not valid.")
    elif name == VERIFY_EVIDENCE:
        expected = arguments.get("expected_head_hash")
        if expected is not None and (
            not isinstance(expected, str) or not _HEX64.fullmatch(expected)
        ):
            return _error(
                "invalid_arguments", "expected_head_hash must be 64 lowercase hex digits."
            )
    return None
