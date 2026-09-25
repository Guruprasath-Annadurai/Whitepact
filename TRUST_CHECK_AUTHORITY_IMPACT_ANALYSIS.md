# Trust check authority impact analysis (WP-V1-FIND-002)

## Components

| Surface | Uses `TrustCheckResult` / `rai_check_trust` | Authorization impact |
| --- | --- | --- |
| `rai_check_trust` MCP tool | Direct HTTP advisory read | **Advisory** — informs agents; must not imply execution permission |
| `TrustClient.passes()` | LangGraph gate, A2A adapter, integrations | **Admission hint** when `require_known=True` or threshold checks used |
| `enrich_agent_trust_state()` | Populates `AgentContext.trust_state` before gateway | **Context only** — gateway `_trust_reason()` escalates stale/low scores; does not auto-allow on outage |
| `WhitePactRuntimeGateway._trust_reason()` | Human-visible escalation reasons | **Non-blocking** for unknown models; **blocking narrative** for stale assessments and low known scores |

## Finding

Prior behavior: HTTP **503** → `error` set → `passes() == True` (fail-open).

That allowed agents and tests to treat **provider outage as pass**, while still returning an `error` field — ambiguous for security reviewers and unsafe where `passes` is interpreted as admission.

## Remediation (v1.3.1)

- `TrustCheckResult.trust_status()` → `TRUSTED` | `UNTRUSTED` | `UNKNOWN`
- Default `passes()` is **fail-closed**: `UNKNOWN` and `UNTRUSTED` → `passes is False`
- Provider errors and unknown models → `UNKNOWN` (not `TRUSTED`)
- `WHITEPACT_TRUST_FAILURE_MODE` (`closed` default, `advisory` optional) — **advisory does not restore pass on outage**; it only documents non-authorizing degraded display paths
- `rai_check_trust` response includes `trust_status`, `stale`, explicit `passes`

## Fail-closed guarantee

No execution authorization is created solely because the trust provider is unreachable. Governed execution still requires WhitePact authority chain (identity, policy, approvals, evidence) independent of trust index availability.

## Offline / static safe-list

**Rejected** — no hardcoded vendor safe table. Secure local cache deferred; expired evidence must not silently trust.

## Configuration

| Variable | Purpose |
| --- | --- |
| `WHITEPACT_TRUST_API_BASE` | Trust Index HTTP base URL |
| `RAI_TRUST_API_BASE` | Legacy alias |
| `WHITEPACT_TRUST_FAILURE_MODE` | `closed` (default) or `advisory` |
