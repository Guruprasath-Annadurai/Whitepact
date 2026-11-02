# WhitePact — Current Runtime Map (Phase 0)

> Repository Reality Audit for the "Heart → WhitePact Production
> Authority Integration" initiative. This document describes the
> codebase **as it exists today, before any Heart wiring** — every
> claim below is sourced from actual file:line reads, not memory or
> documentation. Read this before writing any production integration
> code. No production code was modified to produce this document.

## 1. Where a live governed request enters WhitePact

Two, and only two, live call chains reach `WhitePactRuntimeGateway.evaluate()`:

**A. Hosted MCP tool call** (`src/responsibleai/mcp/server.py`)
- Transport handlers `handle_sse` (:657) and `_StreamableHttpEndpoint.__call__` (:690) call `_authenticate_or_error()` (:619), then set `ContextVar`s `_current_org`/`_current_usage_repo`/`_current_governance` (:662-664, :697-699).
- `_call_tool()` (:180) — the MCP SDK's `@server.call_tool()` handler. If `_current_governance` is populated *and* `ctx.org_id` is set, it calls `apply_governance()` (`mcp/governance_integration.py:152`, imported at :231-233). Otherwise it falls straight to `dispatch_tool(name, call_arguments)` (:244) with **no governance at all**.
- `apply_governance()` builds `IdentityContext`/`AgentContext`/`AuthorityContext`/`ActionRequest`, then calls `services.gateway.evaluate(...)` (:346-357).

**B. REST proxy call to a registered upstream MCP server** — `dashboard/app.py:3842` `upstream_call_tool` → `apply_upstream_governance()` (`mcp/upstream_dispatch.py:95`) → `gateway.evaluate(...)` (:203-205).

**stdio transport is never governed.** `mcp/server.py`'s `main()`/`_run_stdio()` never populates `_current_governance`, so `_call_tool()` falls to bare `dispatch_tool()`. Documented explicitly in `governance_integration.py`'s own module docstring (:20-24). Governance itself is opt-in, gated by `Settings.mcp_governance_enabled` (default `False`, `server.py:395`).

## 2. Where identity is established today

Three real credential sources feed an `OrgContext` (`rbac/models.py`), wrapped 1:1 with no added trust by `IdentityContext.from_org_context()` (`governance/models.py:82-95`):

- **Static API key** — `db/org_repository.py:207` `OrgRepository.authenticate(raw_key)`, SHA-256 hash lookup against `org_api_keys`.
- **OIDC JWT** — `auth/oidc.py` `OIDCProvider.validate_token()`, resolved by `_resolve_oidc_context()` (`server.py:503-532`).
- **VC-JWT bearer** — `auth/verifiable_credential.py`, resolved by `_resolve_vc_context()` (`server.py:534-584`); records a `PrincipalClaim` into `verified_principals` (`governance/principal.py:build_principal_claim()`).
- **SAML** (`auth/saml.py`) — human dashboard login only; not part of the MCP tool-call auth chain.

None of these paths check authority *legitimacy* — they answer "who is this," not "is this identity's authority chain legitimate/consented/purpose-bound."

## 3. Tenant/org identity

`organization_id`/`org_id` originates purely from the `OrgContext` in §2, carried unmodified through `AgentContext.organization_id` (`governance/models.py:132-134`), `AuthorityContext.delegated_by` (`governance_integration.py:248`), and every DB row. No independent tenant-identity proof exists.

## 4. Where `AgentContext` is constructed

- `governance_integration.py:179-184` — `AgentContext(identity=identity, organization_id=ctx.org_id, agent_id=ctx.key_id, framework="mcp-client")`. `agent_id` is deliberately the org's own API-key/OIDC `key_id` (docstring :164-169), not a distinct agent identity.
- `upstream_dispatch.py:123-128` — identical pattern, `framework="upstream-gateway"`.
- `governance_integration.py:516-532` `_agent_from_approval()` — reconstructed for the resume-after-approval flow.

**In every live path, `AgentContext` *is* the calling credential** — there is no separate agent identity distinct from the org credential that authenticated the call.

## 5. MCP/tool identity and trust

- **Registration = approval**: `upstream_mcp_servers` table; `apply_upstream_governance()` denies with `UNAPPROVED_MCP_SERVER` if the server row doesn't exist/match org/is disabled — a pure DB-row check, no cryptographic server attestation.
- **Tool Trust Network** (`governance/tool_trust.py`): `ToolTrustTier` (`TRUSTED`/`PROVISIONAL`/`UNTRUSTED`/`BLOCKED`) from a heuristic supply-chain scan + incident count. Only `BLOCKED` gates the call, checked in `upstream_dispatch.py:171-197` *before* `gateway.evaluate()`.
- Individual tools carry no identity of their own beyond the parent server's tier.

## 6. Where policy is evaluated

`governance/policy.py`: `PolicyRule.matches()` (:56), `Policy.evaluate()` (:90) — first-match-wins over rules from `governance_policies`. Called **inside** `WhitePactRuntimeGateway.evaluate()` (`gateway.py:268-294`), not a separate call site.

## 7. Where risk is evaluated

`governance/risk.py`: `classify_action_risk(action_type, target) -> RiskTier`. Called unconditionally as the *first* line of `evaluate()` (`gateway.py:183`) — every action gets a risk tier stamped, allowed or not.

## 8. Where approvals occur

`governance/approval.py` (pure model) + `db/approval_repository.py` (`create()`, `consume()` — single-use guard before execution, `cast_vote()`/quorum). REST: `POST /api/governance/approvals/{id}/resolve` and `/execute` (`dashboard/app.py:3078,3157`) → `resume_approval()` (`governance_integration.py:535`).

## 9. Final decision — `WhitePactRuntimeGateway.evaluate()` precedence chain

Confirmed signature (`gateway.py:169`):

```python
def evaluate(self, action, authority, policy=None, *,
             recent_violation_count=0, parent_authority=None,
             recent_actions=None, workflow_rules=None,
             autonomy_budget=None, recent_autonomous_action_count=0,
             intent=None) -> DecisionResult
```

Order actually executed (`gateway.py:169-306`):

1. `classify_action_risk()` (:183) — always first, for logging.
2. **Quarantine** (:185) — `recent_violation_count >= threshold` → `QUARANTINE`, short-circuits everything below, including authority.
3. **Workflow composition** (:199, if `workflow_rules` passed) → `DENY`.
4. **Authority attenuation** (:214, if `parent_authority` passed) → `DENY`.
5. **Intent Contract** (:224, if `intent` passed) → `DENY`.
6. **Authority grant** (:234) — `authority.permits(action.action_type)` → `DENY` if not granted.
7. **Caller-declared approval requirement** (:246) → `REQUIRE_APPROVAL`.
8. **Authority constraints** (:256) → `DENY`.
9. **Policy** (:268, if `policy` passed) → `DENY`/`REQUIRE_APPROVAL` short-circuits.
10. **Content scan** (:296+) — PII/toxicity/memory-firewall/causal-influence → `DENY`.
11. **Autonomy budget** (:365, if passed) → `REQUIRE_APPROVAL`.
12. **PII redaction** → `ALLOW_WITH_REDACTION`.
13. **Trust state** (:402) → `REQUIRE_APPROVAL`.
14. Otherwise → `ALLOW`.

**`evaluate()` does not resolve authority — it takes an already-fully-constructed `AuthorityContext` as a plain parameter.** The gateway performs zero identity/authority resolution; it is a deterministic decision function over objects the caller already assembled.

## 10. Where execution happens after a decision

`governance/execution.py`: `authorize_execution(decision, action, ttl_seconds=30, target_fingerprint=None) -> ExecutionAuthorization` (:168) — the only constructor; raises for anything but ALLOW/ALLOW_WITH_REDACTION. `ExecutionAuthorization` (:123) is **not cryptographically signed** (documented :14-29) — digest + org + 30s TTL + single-use `consumed` flag is the entire integrity mechanism.

`InternalToolExecutor.execute()` (:260-277) validates the authorization, marks consumed, then calls `mcp.tools.dispatch_tool()` (:275-277) — the single production call site reached *after* governance. `UpstreamMCPExecutor` (`governance/upstream_executor.py`) is the analogue for proxied calls.

The module docstring itself admits (:4-9): any Python code inside the process calling `mcp.tools.dispatch_tool()` directly bypasses this binding entirely.

## 11. Where audit/evidence is persisted

`governance/evidence.py` (pure model) + `db/evidence_repository.py` (`governance_evidence` table, hash-chained). Pre-execution evidence recording is **fail-closed** (`governance_integration.py:365-395` — a DB write failure blocks the action); post-execution `OutcomeRecord` recording is **fail-open** (:487-513 — logged, never raised, since the action already ran).

## 12. Where authority is currently ASSUMED, not proven — the trust boundary

This is the crux for Heart wiring.

- `AuthorityContext` is **synthesized fresh on every call** in `governance_integration.py:247-252` — it grants exactly `frozenset({name})`, the one action being requested, with constraints copied from `OrgAuthorityCeiling` if one exists. This is not derived from a proof of legitimate authority; it is manufactured to always pass the grant check as long as the caller has a valid, authenticated `OrgContext`. **Authentication is being used as authorization.**
- `OrgAuthorityCeiling` (`governance/ceiling.py`) is trusted straight from a DB row, no provenance, no signature. Set by anyone with ADMIN role and API access.
- `DelegationRecord.grant()` (:79) enforces `validate_attenuation()` only when `from_identity_id` is set. A **root grant** (`from_identity_id=None`) — documented (:96-99) as skipping the check because "there's no parent to compare against" — is created by anyone able to call the grant endpoint with ADMIN role. **The entire root of the delegation graph is a DB insert by an authenticated admin, full stop.**
- `AuthorityPassport` exists but is explicitly **not wired into `evaluate()`** (docstring :37-46) and is itself not signed.
- `ExecutionAuthorization` is likewise not signed — trust is "same process, same async call stack" only.

**Summary**: the entire chain — authenticate → synthesize per-call `AuthorityContext` → optionally check a DB-row ceiling/delegation → evaluate → execute — never once asks "is this authority itself legitimate," "was consent given for this purpose," "is this the actual root of authority," or performs any cryptographic provenance check. Every "authority" object is either fabricated fresh from the caller's own identity, or read from a plain DB row an authenticated admin could have inserted directly. **This is exactly the gap the Heart closes.**

## 13. Execution paths that bypass governance entirely

- stdio MCP transport (§1) — total bypass by design.
- Hosted transport with `mcp_governance_enabled=False` (the default).
- Legacy/non-org-scoped API keys — `apply_governance()` requires `ctx.org_id is not None`; a scopeless key skips straight to `dispatch_tool()`.
- `mcp_http_allow_unauthenticated_demo` (`server.py:587-601`) — `org_id=None`, ungoverned regardless of the setting.
- Direct Python import of `mcp.tools.dispatch_tool()` — a code-level (not network) bypass, explicitly documented as still possible.

## 14. Existing DB repos/tables — reuse vs. new tables

Latest migration: **`0029_add_authority_passports.py`** — next would be `0030`.

| Repository | Table | Stores | Heart mapping |
|---|---|---|---|
| `delegation_repository.py` | `governance_delegations` | Grants, action types, constraints, purpose, expiry, revocation | **Closest analogue to Heart's delegation chain.** Root grants are the closest thing to a root-authority record today, but with zero cryptographic proof |
| `authority_passport_repository.py` | `governance_authority_passports` | Portable, revocable authority snapshot | **Closest analogue to `LegitimacyEnvelope`** — explicitly documented as not yet wired into `evaluate()`; the natural extension point |
| `principal_repository.py` | `verified_principals` | VC-authenticated principal claims | Closest analogue to a root-credential record, but authentication-only, not consent/legitimacy |
| `intent_repository.py` | `governance_intent_contracts` | Agent-declared goal/bounds | Closest analogue to `purpose_binding.py` — self-declared, unverified |
| `org_authority_ceiling_repository.py` | `org_authority_ceilings` | Org-level structural ceiling | Analogue to an org-level authority ceiling, not root-authority/consent |
| `evidence_repository.py` | `governance_evidence` | Hash-chained decision audit log | Could carry the Heart's evaluation trail |

**Nothing in the current schema is a `RootAuthorityRecord`, `ConsentProof`, or true `LegitimacyEnvelope`.** `governance_delegations` and `governance_authority_passports` are extension candidates; `ConsentProof` and `PurposeBinding` (beyond the self-declared intent contract) have no existing table — genuinely new tables, next migration `0030_...`.

## 15. The continuous re-authorization pattern — confirmed insertion point

Confirmed in `mcp/governance_integration.py:260-357`:

```python
delegation_denied_reason: str | None = None
if services.delegation_repo is not None:
    latest_delegation = await services.delegation_repo.get_latest_delegation(
        ctx.org_id, agent.agent_id
    )
    if latest_delegation is not None and not latest_delegation.is_active():
        code = (ReasonCode.AUTHORITY_REVOKED if latest_delegation.revoked_at is not None
                else ReasonCode.AUTHORITY_EXPIRED)
        delegation_denied_reason = format_reason(code, delegation_id=latest_delegation.delegation_id)
...
if delegation_denied_reason is not None:
    decision = DecisionResult(decision=GovernanceDecision.DENY, ...)
else:
    decision = services.gateway.evaluate(action, authority, policy=policy, ...)
```

This runs **before** `gateway.evaluate()`, on every dispatched governed call, using the always-fresh `get_latest_delegation()` specifically so staleness is never trusted from earlier in the same call. **This is the natural insertion point for Heart evaluation**: already positioned ahead of `gateway.evaluate()`; follows the identical "opt-in via optional repo, additive, skip entirely if unwired" posture every other v3 feature in this file already uses (ceiling, workflow rules, autonomy budget, intent contract); runs after identity/agent/authority construction but before risk/policy/content evaluation, so a Heart `DENY` is cheap; and evidence-recorded for free via the same downstream `build_evidence_record()`/`evidence_repo.record()` call.

**Second wiring point needed**: `apply_upstream_governance()` (`mcp/upstream_dispatch.py`) does **not** currently have this continuous re-check step at all — it will need the same treatment, not just `apply_governance()`.

## Call graphs

### Current (as of this audit)

```
Request (MCP tool call, hosted transport)
  ↓
_authenticate_or_error() — API key / OIDC / VC → OrgContext  [mcp/server.py:619]
  ↓
_call_tool()  [mcp/server.py:180]
  ↓ (only if mcp_governance_enabled AND ctx.org_id)
apply_governance()  [mcp/governance_integration.py:152]
  ├─ IdentityContext.from_org_context()  — identity, NOT authority
  ├─ AgentContext(...)                   — agent_id = the org credential's own key_id
  ├─ AuthorityContext(...)               — SYNTHESIZED FRESH, grants exactly {this action}
  ├─ continuous delegation re-check      — get_latest_delegation(), DENY if stale
  ↓
WhitePactRuntimeGateway.evaluate()  [gateway.py:169]
  ├─ risk → quarantine → workflow → attenuation → intent
  ├─ authority.permits() / constraint_violation()  ← trusts the synthesized AuthorityContext as-is
  ├─ policy → content scan → autonomy budget → PII → trust
  ↓
DecisionResult (ALLOW / DENY / REQUIRE_APPROVAL / QUARANTINE / ALLOW_WITH_REDACTION)
  ↓ (if ALLOW*)
authorize_execution() → ExecutionAuthorization (unsigned, 30s TTL, single-use)
  ↓
InternalToolExecutor.execute() → dispatch_tool()
  ↓
Evidence (fail-closed pre-execution, fail-open post-execution outcome)
```

**Nowhere in this graph is there a question: "is this authority itself legitimate?"** — root-of-authority, consent, purpose-binding, non-delegable-authority, and revocation-currency are entirely absent. `AuthorityContext` is manufactured from authentication alone.

### Intended future path (per the initiative's own target)

```
Request
    ↓
Principal Authentication          [existing: auth/oidc.py, auth/verifiable_credential.py, org_repository.py — REUSE]
    ↓
Authority Context Resolution      [NEW: an Authority Resolver service — Phase 5 of this initiative]
    ↓
HEART                             [existing: governance/sovereignty_kernel.py evaluate() — REUSE, unmodified]
    ├── root authority            [governance/root_authority.py]
    ├── consent                   [governance/consent_proof.py]
    ├── purpose                   [governance/purpose_binding.py]
    ├── delegation                [governance/delegation_kernel.py]
    ├── attenuation                [governance/models.py validate_attenuation() — ALREADY LIVE, reused]
    ├── expiry / revocation       [governance/authority_lifetime.py, revocation_kernel.py]
    └── constitutional constraints [governance/constitution.py, non_delegable_authority.py]
    ↓
LegitimacyEnvelope                [governance/legitimacy_envelope.py — REUSE, unmodified]
    ↓
WhitePact Governance / Risk       [gateway.py evaluate() — REUSE, unmodified, receives Heart-derived AuthorityContext instead of a synthesized one]
    ↓
Runtime Decision                  [DecisionResult — REUSE, unmodified]
    ↓
Execution Permit                  [execution.py ExecutionAuthorization — EXTEND: bind to LegitimacyEnvelope digest]
    ↓
Citadel / Enforcement Boundary    [InternalToolExecutor / UpstreamMCPExecutor — EXTEND: verify permit binding]
    ↓
Tool / MCP / API / external system
    ↓
Evidence                          [evidence_repository.py — EXTEND: record the LegitimacyEnvelope alongside the decision]
```

**Design principle preserved from the audit**: the Heart itself (`sovereignty_kernel.evaluate()`, and everything it composes) requires **zero changes** to become production-callable — it already accepts already-resolved domain objects and an abstract `RootResolver`. The work is entirely in what sits *around* it: an Authority Resolver that turns real identity + DB state into the objects `sovereignty_kernel.evaluate()` expects, and wiring its output (a `LegitimacyEnvelope`) into the exact insertion point §15 identified — the continuous re-authorization block in `apply_governance()` (and its currently-missing sibling in `apply_upstream_governance()`).
