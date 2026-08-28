# Threat Model

Last reviewed: 2026-08-11 · Platform version: 1.2.0

This document uses STRIDE (Spoofing, Tampering, Repudiation, Information
disclosure, Denial of service, Elevation of privilege) against the current,
real attack surface — not a hypothetical future one. Every mitigation cited
here points at real code or a real test; every open gap is stated as a gap,
not implied to be handled. If you find a mitigation claimed here that no
longer matches the code, treat the code as ground truth and report the
discrepancy per [SECURITY.md](SECURITY.md).

## Scope

In scope:
- MCP transports (stdio, Streamable HTTP `/mcp`, legacy HTTP+SSE `/sse`+`/messages/`)
- OAuth/OIDC resource-server authentication for the hosted MCP transport
- The governance decision pipeline (`WhitePactRuntimeGateway`, risk tiering, policy engine)
- The evidence hash chain and approval workflow
- The dashboard REST API (`src/responsibleai/dashboard/`)
- The database layer (SQLite/PostgreSQL via SQLAlchemy)
- Helm/Kubernetes deployment (`helm/rai-governance/`)

Out of scope (see [ENTERPRISE_SECURITY.md](ENTERPRISE_SECURITY.md) for why):
- Physical security of self-hosted infrastructure — the deployer's responsibility.
- Third-party LLM provider security (OpenAI/Anthropic/Google APIs) — covered by each provider's own terms.
- Social engineering — see [SECURITY.md](SECURITY.md)'s scope section.

---

## 1. MCP transports

**Assets**: tool-call arguments (which may contain PII the caller is
scanning), governance decisions, evidence records.

**Threats and mitigations**:

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| DNS rebinding against the Streamable HTTP/SSE listener, tricking a browser-based MCP client into talking to a malicious "localhost" origin | Spoofing | `TransportSecuritySettings` (`enable_dns_rebinding_protection`, `allowed_hosts`, `allowed_origins`) — see `src/responsibleai/mcp/server.py`. Enabled automatically once `RAI_MCP_HTTP_ALLOWED_HOSTS`/`RAI_MCP_HTTP_ALLOWED_ORIGINS` are set. | Mitigated when configured. **Gap**: off by default if those env vars are unset — a deployer who skips configuration is unprotected. Documented, not silently defaulted to "safe" because a wrong default host allowlist can break legitimate clients. |
| A malicious MCP client claiming a fabricated identity to call governed tools | Spoofing | OAuth/OIDC resource-server auth (RFC 9728 protected-resource metadata) reuses the dashboard's SSO configuration; Bearer tokens are validated per request. | Mitigated for the hosted HTTP transport. stdio transport has no network identity to spoof — trust boundary is the local process invoking it. |
| Tampering with tool-call arguments in transit | Tampering | TLS termination is the deployer's responsibility (same posture as the REST API — see `ENTERPRISE_SECURITY.md`); the MCP SDK itself speaks plain HTTP/SSE. | **Gap, stated honestly**: no application-layer message signing. Relies entirely on TLS at the reverse proxy. |
| A tool call that silently succeeds against a governance policy but claims a different tool was called (repudiation) | Repudiation | Every tool call that reaches `WhitePactRuntimeGateway.evaluate()` produces a hash-chained `EvidenceRecord` — see Section 3. | Mitigated for governed tools. Un-governed diagnostic tools (`rai_health`) are not evidence-logged by design — nothing sensitive to repudiate. |
| A legacy SSE client held open indefinitely, exhausting server connections | Denial of service | No per-connection timeout enforced today beyond the ASGI server's own defaults (uvicorn). | **Gap**. Not yet load-tested; see Phase 25 benchmarking for what has and hasn't been measured. |

---

## 2. OAuth/OIDC resource-server authentication

**Assets**: the ability to call any MCP tool as an authenticated org.

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| A stolen or leaked Bearer token used after an employee departs | Elevation of privilege | `PUT /api/orgs/{id}/sso {"sso_required": true}` invalidates static API keys org-wide once SSO is enforced — see `ENTERPRISE_SECURITY.md` SSO section. | Mitigated only when the org opts in. **Gap**: orgs that never enable `sso_required` keep static keys valid indefinitely (by design — see `RELEASING.md`'s backward-compatibility stance, but it is a real standing risk for those orgs). |
| Token replay across the two transports (SSE and Streamable HTTP) | Spoofing | Both transports validate the same Bearer token against the same auth backend; no transport-specific bypass exists. | Mitigated — verified by `tests/test_mcp_oauth.py` (transport-parity assertions). |
| A malicious OIDC provider (customer-controlled) returning forged claims | Spoofing | Out of scope — the customer's own IdP choice is trusted per `ENTERPRISE_SECURITY.md`'s SSO section; WhitePact validates the OIDC token signature against the configured issuer's published JWKS, standard OAuth2 flow. | Standard OIDC trust boundary, not something this platform can additionally defend against. |

---

## 3. Governance decision pipeline

**Assets**: the integrity of every ALLOW/ALLOW_WITH_REDACTION/REQUIRE_APPROVAL/DENY/QUARANTINE decision and its evidence trail.

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| A crafted tool-call argument set designed to make the risk classifier under-tier a dangerous action | Elevation of privilege | `governance/risk.py`'s `TOOL_RISK_TIERS` is a hardcoded table keyed by tool name, not inferred from argument content — argument-based evasion cannot change a tool's tier. Drift-tested against live `TOOL_DEFS` (`tests/test_governance_risk.py`) so a new tool can't ship without a risk classification. | Mitigated by design (static, not content-inferred). |
| A policy rule ordering bug that lets a `DENY` rule get shadowed by an earlier, broader `ALLOW` rule | Tampering (of the decision itself) | `Policy` is explicitly first-match-wins — documented and tested (`tests/test_governance_policy.py`) so rule order is a known, testable property rather than implementation-defined behavior. | Mitigated for the engine; **gap**: a poorly-authored policy (broad `ALLOW` before a narrow `DENY`) is a real misconfiguration risk the engine cannot prevent — this is a policy-authoring responsibility, called out here so it isn't assumed away. |
| Directly editing `governance_evidence` rows in the database to hide a DENY/QUARANTINE decision after the fact | Tampering, Repudiation | Hash chain: `entry_hash = sha256(prev_hash + fields)`. `verify_chain()` recomputes and reports the first broken link. | Detects tampering (Section "Audit trail integrity" pattern, same limitation as `ENTERPRISE_SECURITY.md`'s audit-log chain: does not detect an attacker with full DB write access who recomputes the entire chain from scratch — no external anchoring exists yet). |
| Argument values (potentially containing PII) leaking through the evidence trail itself | Information disclosure | `EvidenceRecord` never stores raw argument values — only field-name keys, by design (see `governance/evidence.py`). | Mitigated by design. |
| A race between two concurrent resolvers both approving the same `REQUIRE_APPROVAL` request | Tampering | `ApprovalRepository` resolution uses a `WHERE status='PENDING'` SQL guard plus an in-Python pre-check; the loser gets `ApprovalAlreadyResolvedError`. | Mitigated — tested under concurrent resolution in `tests/test_governance_approval.py`. |
| A caller invoking `WhitePactRuntimeGateway.evaluate()` bypassing the MCP layer entirely, going straight to the underlying engine (e.g. `GuardrailsEngine`) | Elevation of privilege | Not prevented at the library level — anything importing `responsibleai` as a Python library has direct access to the underlying engines. This is intentional (the SDK is meant to be embeddable) but means the governance gateway is a chosen integration point, not an unbypassable boundary, for a caller with code-level access. | **Gap, stated honestly**: the governance layer secures MCP-mediated access; direct library use is the caller's own trust boundary. |
| Within the governed MCP dispatch path itself, a bug that calls `mcp.tools.dispatch_tool()` directly instead of through `governance/execution.py`'s `InternalToolExecutor`, skipping the decision check entirely | Elevation of privilege | `mcp/server.py`'s `_call_tool()` no longer calls `dispatch_tool()` itself for a governed (org-scoped, `mcp_governance_enabled=True`) request — `apply_governance()` constructs an `ExecutionAuthorization` and calls `InternalToolExecutor.execute()`, which validates the authorization (digest match, org match, not expired, not already consumed) before invoking `dispatch_tool()`. There is exactly one call site left that can reach `dispatch_tool()` on the governed path. | Mitigated and tested — `tests/test_executor_bypass_invariant.py` proves the executor refuses a mismatched action, wrong org, expired authorization, and replay (same authorization used twice) in isolation; `tests/test_mcp_governance_dispatch.py` proves the live end-to-end path routes through it. `governance/upstream_executor.py`'s `UpstreamMCPExecutor` (calls proxied to third-party upstream MCP servers) has the identical property, independently tested (`tests/test_citadel_execution_containment.py`, `tests/test_upstream_gateway.py`, `tests/test_tool_trust.py`) and additionally binds to a target-config fingerprint at authorization time (`AuthorizationTargetDriftError`), refusing execution if the resolved server's URL/enabled-state/credential drifted between decision and execution. |
| A hosted-MCP tool call bypassing governance because `Settings.mcp_governance_enabled` defaults to `False` | Elevation of privilege | Deliberate, documented default (see the field's own docstring in `dashboard/config.py`) — turning governance-gating on for an existing hosted deployment is a real behavior change, so it's opt-in rather than silently applied. When enabled, every org-scoped Streamable HTTP/SSE tool call is evaluated (`mcp/governance_integration.py`); when it isn't, none are. | **Gap, stated honestly**: an operator who never sets the flag gets zero dispatch-path enforcement, same as before this wiring existed. The self-hosted stdio transport is never covered either way — no organizational identity exists there to evaluate against. |
| Evidence-write or Trust Index HTTP-call failure during `apply_governance()` blocking or silently skipping a tool call | Denial of service / Elevation of privilege | `EvidenceRepository.record()` failures are caught explicitly and fail *closed*: the call is blocked with `governance_evidence_unavailable` rather than proceeding with no audit record, or crashing with an unhandled exception. A Trust Index lookup failure fails *open* via `TrustCheckResult.error` (an unscored model never triggers the low-trust downgrade) — consistent with the fail-open reasoning `TrustCheckResult.passes()` documents; the two failure modes are deliberately asymmetric (an unreachable trust-check shouldn't block routine calls, but an unrecorded decision should always block, since evidence is this platform's entire audit-trail guarantee). | Mitigated for both — the trust lookup (tested, `test_governance_trust_state.py`'s network-error case) and the evidence-write failure (tested, `test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed`, which monkeypatches `EvidenceRepository.record` to raise and confirms the underlying tool never runs). |

---

## 4. Dashboard REST API

Covered in detail by `ENTERPRISE_SECURITY.md` (RBAC, multi-tenancy, encryption) and `SECURITY.md` (disclosure process). Threat-model-specific additions:

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| Cross-org data leakage via a missing `org_id` filter in a new repository method | Information disclosure | Every repository method filters by `org_id`; treated as a `SECURITY.md`-scope defect if found, not a feature gap. | Mitigated by convention + code review; **gap**: no automated static check enforces this — relies on reviewer discipline today. Flagged as a real gap rather than claiming automated coverage that doesn't exist. |
| Audit log entries silently attributed to no organization at all (`org_id: null` regardless of the real caller), making `GET /api/audit`'s org-scoping vacuous and undermining the audit trail's tenant attribution | Repudiation, Information disclosure (by omission) | **Found and fixed during Phase 23's tenant-isolation test work** (2026-08-11), not previously known: `AuditLogMiddleware` is a `BaseHTTPMiddleware`, and Starlette runs the downstream app (including the `get_org_context` auth dependency) in a separate task via its internal task group — a `ContextVar` set inside that inner task does not propagate back to the middleware's own scope after `call_next()` returns. The middleware was reading a `ContextVar` that was never actually populated from the caller's perspective, so every audit entry recorded `org_id: null` no matter who made the request. Fixed by moving org/key attribution onto `request.state` (`app.py`'s `get_org_context`/`AuditLogMiddleware`), which is the same `Request` object instance across that task boundary. | Fixed and regression-tested — `tests/test_tenant_isolation.py` proves audit entries are now correctly attributed and org-scoped `GET /api/audit` queries return only the caller's own entries. |
| Rate-limit bypass by rotating API keys | Denial of service | Per-org (not per-key) rate limiting would close this; current implementation is per-Bearer-token (SHA-256 keyed). | **Gap**: an org with multiple keys gets a rate-limit bucket per key, not per org — a caller with several keys can exceed the intended per-org ceiling. |
| Webhook SSRF — a registered webhook URL pointed at internal infrastructure | Elevation of privilege | `validate_webhook_url()` (`webhooks/manager.py`) resolves the hostname and rejects private/loopback/link-local/reserved/multicast/unspecified addresses (including cloud-metadata-style hosts), re-checked at registration (`POST /api/webhooks`) and again at every delivery, since DNS can resolve differently between the two. | Mitigated — tested in `tests/test_webhooks.py` (scheme rejection, no-host rejection, localhost/internal-hostname/metadata-address rejection, resolution-failure handling). |

---

## 5. Database layer

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| SQL injection | Tampering | SQLAlchemy Core/ORM parameterized queries throughout; no raw string-interpolated SQL in the governance, evidence, or approval repositories. | Mitigated — verified by code review each phase; no dedicated injection fuzz-test suite exists yet (see Phase 23 test-suite expansion). |
| A compromised `RAI_DATABASE_URL` credential granting broad database access | Elevation of privilege | Credential management is the deployer's responsibility (env var / secret manager) — same posture as any 12-factor app. | Out of application scope; documented so it isn't silently assumed handled. |

---

## 6. Helm/Kubernetes deployment

| Threat | STRIDE | Mitigation | Status |
|---|---|---|---|
| A pod compromise pivoting into the same-namespace dashboard Secret used by both the dashboard and MCP HTTP Deployments | Elevation of privilege | Standard Kubernetes Secret sharing (same pattern as most Helm charts); no per-Deployment secret splitting today. | **Gap**: both Deployments (dashboard, hosted MCP transport) mount the same Secret. A compromise of either pod exposes credentials usable by the other's identity. Not yet split — would need separate service accounts/Secrets per Deployment. |
| Prometheus scraping the wrong port on the MCP Deployment (a real bug caught during Phase 14 before it shipped) | Information disclosure (of metrics, low severity) | Fixed at implementation time — the MCP Deployment does not reuse the dashboard's `podAnnotations` verbatim, since the MCP process has no `/metrics` endpoint. | Mitigated (caught pre-ship, documented in `MIGRATION_WHITEPACT_V2.md` Phase 14). |

---

## What this threat model does not cover

- No formal STRIDE workshop with a second reviewer has been run — this is a
  solo-founder pass, same limitation `GOVERNANCE.md` states about the
  quarterly risk-review cadence. Treat it as a structured self-assessment,
  not independent red-team output.
- No fuzz-testing or dedicated penetration test has been performed against
  any of the surfaces above — see `SLA.md`/`ENTERPRISE_SECURITY.md` for the
  explicit, honest statement that a pentest report does not exist yet.
- Supply-chain risk of WhitePact's own dependencies (as opposed to
  third-party MCP servers WhitePact's scanner evaluates) is covered
  separately by SBOM generation and `dependency-review.yml` — see
  `RELEASING.md` and `MIGRATION_WHITEPACT_V2.md` Section 10.1, not
  duplicated here.

## Revisiting this document

Update this threat model whenever a new transport, auth mechanism, or
governance primitive ships — the same day, not "eventually," per the
standard this project holds `GOVERNANCE.md` to. A stale threat model that
implies coverage it doesn't have is worse than an honestly incomplete one.
