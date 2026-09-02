# Reviewer Attack Map — PR #55

Companion to [`PR55_INDEPENDENT_SECURITY_REVIEW_PACKET.md`](PR55_INDEPENDENT_SECURITY_REVIEW_PACKET.md).
For each critical subsystem: FILES / ENTRY POINTS / TRUST ASSUMPTIONS /
SECURITY INVARIANTS / TESTS / KNOWN LIMITATIONS / ATTACK IDEAS. Built for
a human reviewer to attack the system's assumptions directly, not to be
taken as proof those assumptions hold.

**Reviewed SHA:** `9c6fe838d7fe033c13be4dfd1e05268c67d2c1b1`

---

## A. Authentication & tenant boundary

**FILES:** `dashboard/app.py` (`get_org_context`, `create_api_key`, `revoke_api_key`, `_require_caller_owns_org`), `mcp/server.py` (`_authenticate_or_error`), `db/org_repository.py` (`OrgRepository.authenticate`), `dashboard/middleware.py` (`AuthFailureLimiter`).

**ENTRY POINTS:** every `/api/*` REST endpoint; both MCP hosted transports.

**TRUST ASSUMPTIONS:** a validated Bearer token/API key/JWT uniquely and correctly identifies one `org_id`; `is_legacy`/`org_id=None` keys are lower-trust and rejected by execution-capable endpoints.

**SECURITY INVARIANTS:** no request reaches an org-scoped resource without its own `org_id` matching the resource's `org_id` (Phase 7 fix); failed-auth attempts are rate-limited per remote address.

**TESTS:** `tests/test_cross_tenant_isolation_sweep.py` (11), `tests/test_rest_auth_failure_limiter.py` (5).

**KNOWN LIMITATIONS:** no key-rotation endpoint; `auth_enabled=false` dev-mode grants `Role.OWNER` with zero credential, blocked from action-execution endpoints but not from read/config endpoints; `AuthFailureLimiter` is IP-keyed (spoofable behind a shared NAT/proxy without correct `X-Forwarded-For` handling — not independently re-verified in this pass).

**ATTACK IDEAS:**
- Cross-tenant access: request org B's resource with org A's key against an endpoint *not* in the 15 covered by the Phase 7 sweep — is there a 16th handler?
- Tenant-ID substitution in a nested/child resource (e.g. an object whose own `org_id` is set indirectly through a parent lookup rather than the URL path).
- API-key enumeration via timing or error-message differences between "key doesn't exist" and "key exists, wrong org."
- Stale credential use: revoke a key, then race a concurrent in-flight request that already passed the auth dependency but hasn't yet hit a DB-consuming operation.
- `AuthFailureLimiter` bypass via IP rotation or a missing/misconfigured trusted-proxy header check.

## B. Heart legitimacy / authority resolution

**FILES:** `governance/authority_resolver.py` (`resolve_authority_grant`, `_resolve_applicable_consent`), `governance/sovereignty_kernel.py` (`evaluate`), `db/root_authority_repository.py`, `db/consent_proof_repository.py`.

**ENTRY POINTS:** `mcp/governance_integration.py:229`, `mcp/upstream_dispatch.py:128` — the only two production call sites (per `ENFORCEMENT_PATH_MATRIX.md`'s own grep).

**TRUST ASSUMPTIONS:** a `RootAuthorityRecord`/`ConsentProof` returned by the repository layer is exactly what the acting identity currently holds; fail-closed-by-omission means an unscoped/mismatched field matches nothing.

**SECURITY INVARIANTS:** `enterprise_mode=true` implies every reaching path checks root authority at minimum; consent, once wired, is integrity-verified and scope-matched before granting.

**TESTS:** `test_heart_wiring_phase6.py::TestConsentBackedLegitimacyReachableThroughLiveDispatch` and the broader Heart/authority test files (not enumerated exhaustively here — see `tests/` for `test_authority_resolver*`, `test_sovereignty_kernel*`).

**KNOWN LIMITATIONS:** `sovereignty_kernel.evaluate()` only runs the checks whose *all* prerequisite inputs are supplied (per `00_CLOSURE_AUDIT.md`'s reading of `sovereignty_kernel.py:126-168`) — a caller that omits an input skips that check entirely rather than failing it. `ExecutionAuthorization.revocation_epoch` is never populated at grant time (topic 15 of the review packet).

**ATTACK IDEAS:**
- Omit exactly the inputs needed to make `evaluate()` skip a check, if any caller-controlled path can influence which kwargs get passed.
- Purpose confusion: request with `purpose=A`, get authorized, attempt to execute with an argument set that implies `purpose=B` — should be caught by `compute_action_digest()` binding, but verify the digest actually covers every field an attacker could vary.
- Cross-org substitution: present a valid `ConsentProof` scoped to org A while authenticated as org B.
- Confused deputy: an upstream-MCP-proxied action where the *proxy's* identity, not the original caller's, ends up being what's authority-checked.
- Policy bypass via a policy-version race — the decision is made against version N, but the digest doesn't re-validate that version N is still current at execution time (per `execution.py`'s own docstring, this is explicitly *not* re-checked, by design — is that design actually safe, or does it just move the risk?).

## C. Execution authorization / replay / TOCTOU

**FILES:** `governance/execution.py` (`ExecutionAuthorization`, `authorize_execution`, `AuthorizationTargetDriftError`), `governance/approval.py` (`compute_action_digest`), migration `0036` (`governance_execution_nonces`).

**ENTRY POINTS:** `InternalToolExecutor.execute()`, `UpstreamMCPExecutor.execute()`.

**TRUST ASSUMPTIONS:** `action_digest` fully captures everything that must not change between authorization and execution; `consumed`/nonce tracking is atomic against concurrent use.

**SECURITY INVARIANTS:** an `ExecutionAuthorization` can be consumed exactly once; expired authorizations are rejected; a target-fingerprint mismatch (where applicable) raises `AuthorizationTargetDriftError`.

**TESTS:** execution/authorization unit tests in `tests/` (not enumerated exhaustively — grep `test_execution` / `test_authorize`).

**KNOWN LIMITATIONS:** `nonce` is populated but nothing currently transmits or verifies it cryptographically — it exists for a not-yet-built signed/cross-process future (stated directly in the class docstring). Concurrent-consume race safety was not independently verified in this pass (topic 10 of the review packet).

**ATTACK IDEAS:**
- Double-spend race: fire two concurrent execute requests with the same authorization the instant it's issued — does `consumed` actually serialize correctly under real DB concurrency (SQLite vs. PostgreSQL may differ here)?
- Replay after TTL expiry with clock skew between issuing and executing processes, if they ever run on different hosts.
- Authorization/action mismatch: construct an action that hashes to the same digest via a crafted argument collision (low probability with SHA-256, but confirm the digest actually includes every field that matters, not just the obvious ones).
- Nonce-table growth/exhaustion as a DoS angle against the execution path itself (defensive concern, not just correctness).

## D. Approval / resume / revocation

**FILES:** `governance_integration.py` (`resume_approval`, `build_resume_action`), `db/approval_repository.py` (`ApprovalRepository.consume`), migration `0035` (`governance_revocation_epochs`).

**ENTRY POINTS:** `/api/governance/approvals/{id}/execute` (`ENFORCEMENT_PATH_MATRIX.md` Path 6).

**TRUST ASSUMPTIONS:** a `REQUIRE_APPROVAL` decision that's since been approved by a human is safe to execute as long as authority hasn't been revoked in the interim.

**SECURITY INVARIANTS:** resume re-checks Heart legitimacy fresh (this session's predecessor fix) and raises `ApprovalRevokedSinceQueuedError` on a stale grant; `consume()` is single-use regardless.

**TESTS:** referenced in `ENFORCEMENT_PATH_MATRIX.md`'s Path 6 entry; specific test file not independently re-located in this pass — **verify it exists at the reviewed SHA** rather than trusting the citation.

**KNOWN LIMITATIONS:** `consume()` runs *before* the revocation re-check (by design, to avoid leaking revocation state via retry probing) — the approval is spent either way. Revocation-epoch is not bound into the original `ExecutionAuthorization` object at all (see topic 15).

**ATTACK IDEAS:**
- Revoke authority in the exact window between `consume()`'s DB write and the subsequent `resolve_authority_grant()` re-check inside the same request — is there a real gap there, or is it inside one transaction?
- Approval resurrection: attempt to resume an approval a second time after `consume()` already spent it — confirm this fails, not just for the happy path but for a resume attempt racing the first.
- Quorum bypass: if `required_approvals > 1`, attempt to resume after only a partial vote count.

## E. MCP transports (stdio / Streamable HTTP / SSE) & the in-process bypass

**FILES:** `mcp/server.py` (`main`, `_call_tool`, `_StreamableHttpEndpoint`, `handle_sse`), `mcp/tools.py` (`_dispatch_tool_unchecked`, formerly `dispatch_tool`), `tests/test_dispatch_tool_unchecked_call_sites.py`.

**ENTRY POINTS:** all of `ENFORCEMENT_PATH_MATRIX.md`'s Paths 1–4 and 8.

**TRUST ASSUMPTIONS:** stdio is a declared, local/self-hosted capability, not a network-exposed one in a correctly configured deployment; `enterprise_mode=true` is the deployer's signal that governance must be unavoidable on every *network-reachable* path.

**SECURITY INVARIANTS (network-reachable only):** under `enterprise_mode=true` + `mcp_governance_enabled=true`, every hosted-MCP call passes through `_call_tool()`'s governance branch. Stdio is fully blocked under `enterprise_mode=true` (Phase E2).

**SECURITY INVARIANTS (explicitly NOT claimed):** no in-process privilege boundary — `_dispatch_tool_unchecked()` is directly importable by any Python code in the same process. The drift-guard test only bounds *accidental* new call sites/re-exports, not a deliberate import by someone with repo/deploy access.

**TESTS:** `test_dispatch_tool_unchecked_call_sites.py`.

**KNOWN LIMITATIONS:** see review packet topics 17, 25, 28. This is the one structural gap this entire freeze process exists to surface, not close.

**ATTACK IDEAS:**
- If stdio is ever exposed over a network transport by a misconfigured deployment (e.g. proxied), does *anything* stop it, or does the `enterprise_mode` block only apply to the process's own stdio entry point?
- Confirm the drift-guard test actually fails the suite on a newly added call site — try adding one locally and see if CI (once it exists — see topic 30) or local `pytest` catches it.
- Supply-chain angle: could a dependency, loaded into the same process, reach `_dispatch_tool_unchecked()` via `sys.modules` introspection even without a normal import statement? (Python offers no real boundary here — the point isn't whether this is possible, which it structurally is, but whether the docs correctly refuse to claim otherwise.)

## F. SSRF / webhook / upstream-MCP targets

**FILES:** `webhooks/manager.py` (`validate_webhook_url`), `tests/test_public_api_fuzz.py`, `tests/test_ssrf_guard_fuzz.py`.

**ENTRY POINTS:** webhook registration, webhook delivery, upstream-MCP-server registration/call.

**TRUST ASSUMPTIONS:** `validate_webhook_url()` correctly rejects internal/link-local/metadata-endpoint targets and malformed input without crashing.

**SECURITY INVARIANTS:** SSRF-guarded at registration *and* every delivery (not just once at setup) — per `TRUST_BOUNDARIES.md`.

**TESTS:** `test_public_api_fuzz.py` (12, found 2 real crash bugs this session — malformed IPv6, oversized-hostname IDNA failure, both fixed), `test_ssrf_guard_fuzz.py` (96 lines, newer addition per the diff stat — not read in full during this pass).

**KNOWN LIMITATIONS:** whether upstream-MCP-server URLs get the *same* validator or an independent one was not confirmed line-by-line in this pass (topic 18/19 of the review packet).

**ATTACK IDEAS:**
- DNS rebinding: register a webhook URL that resolves to a safe IP at validation time and an internal IP at delivery time.
- Redirect retargeting: a webhook target that 30x-redirects to an internal address — confirm the HTTP client used for delivery doesn't follow redirects past validation, or re-validates the redirect target.
- IPv6-specific bypass variants beyond the one the fuzzer already found (e.g. IPv4-mapped IPv6 addresses, zone-ID suffixes).
- Upstream-MCP-server registration with a target that only becomes internal after a DNS TTL expires post-registration.

## G. Evidence/audit chain integrity

**FILES:** `governance_evidence`/`audit_log` schema (migrations `0004`, `0015`, `0019`, `0032`), evidence-writing code paths in `governance/*.py`.

**ENTRY POINTS:** every governed decision writes an evidence record.

**TRUST ASSUMPTIONS:** the hash chain cannot be forked or silently rewritten without detection.

**SECURITY INVARIANTS:** migration `0032` adds uniqueness constraints "preventing forked evidence hash chains."

**TESTS:** not independently re-located/re-run against a deliberate fork attempt in this pass.

**KNOWN LIMITATIONS:** the fork-prevention constraint's actual end-to-end effectiveness against a deliberate tamper attempt is unverified here (topic 20).

**ATTACK IDEAS:**
- Attempt to insert two evidence records with the same parent-hash pointer (a fork) and confirm the DB constraint actually rejects it, not just that the application-layer code happens not to construct one.
- Evidence deletion: is there any path (admin tooling, direct DB access assumed out of scope, but any *application* endpoint) that can delete or truncate an evidence/audit record?
- Evidence-chain regeneration: if a chain is ever rebuilt from a backup/restore (see `DR_RESTORE_DRILL.md`), does the restored chain's integrity verification actually re-validate against the pre-restore chain, or just "look" internally consistent?

## H. Rate limiting, request size, logging hygiene

**FILES:** `dashboard/middleware.py` (`AuthFailureLimiter`, `MaxBodySizeMiddleware`), `mcp/server.py` (`_AuthFailureLimiter`), `dashboard/logging_config.py`.

**ENTRY POINTS:** every REST/MCP request.

**TRUST ASSUMPTIONS:** IP-keyed limiting is a meaningful control; a 10MB cap is sufficient against oversized-request DoS.

**SECURITY INVARIANTS:** `aiosqlite`/`asyncpg` loggers are capped at INFO regardless of app-configured level (Phase 9 fix — closes a real secret-leak-via-DEBUG-logging path, confirmed by `test_secrets_never_logged_sweep.py`).

**TESTS:** `test_rest_auth_failure_limiter.py`, `test_secrets_never_logged_sweep.py`.

**KNOWN LIMITATIONS:** IP-based limiting is bypassable by any attacker with multiple source IPs; no distributed/shared-state rate limiting was confirmed (i.e., does this hold across multiple app instances, or is it per-process in-memory state?) — not verified in this pass.

**ATTACK IDEAS:**
- Confirm whether `AuthFailureLimiter`'s state is per-process (in-memory) or shared (Redis/DB) — if per-process, a load-balanced deployment gives each instance its own quota, multiplying the effective limit.
- Malformed JSON / malformed MCP payloads at exactly the body-size boundary (off-by-one at `MAX_REQUEST_BODY_BYTES`).
- Exception-leakage: trigger every error path this session's fuzz/crash fixes touched and confirm the *fixed* error responses don't leak stack traces or internal paths.

---

## Coverage note

This attack map covers the subsystems most directly touched by PR #55's own diff (Heart legitimacy, execution authorization, approval/resume, MCP transports, SSRF, evidence integrity, rate-limiting/logging) plus the tenant-isolation and secret-hygiene sweeps this session's predecessor work specifically added tests for. It does **not** independently attack subsystems outside this PR's diff (billing internals, OIDC provider trust beyond JWKS validation, LLM-provider integration, deepfake/redteam detection internals) — those are out of scope for this packet, not asserted safe.
