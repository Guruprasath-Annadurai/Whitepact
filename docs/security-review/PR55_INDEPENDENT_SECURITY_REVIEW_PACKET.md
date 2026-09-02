# Independent Security Review Packet — PR #55

**Independent review status: NOT YET PERFORMED.**

This document is prepared *for* a human security reviewer. It does not
itself constitute review. It was assembled by an AI agent (Claude, via
Claude Code) at the direction of the repository owner, under an explicit
security-freeze directive that names the same rule as its predecessor
(`PR50_PR54_INDEPENDENT_REVIEW_PACKET.md`): do not "complete" independent
review yourself.

**Exact reviewed SHA:** `9c6fe838d7fe033c13be4dfd1e05268c67d2c1b1`
(branch `security/heart-production-closure`, PR
[#55](https://github.com/Guruprasath-Annadurai/Whitepact/pull/55)). See
[`FROZEN_REVIEW_BASELINE.md`](FROZEN_REVIEW_BASELINE.md) for full
identity/commit detail and
[`FROZEN_REVIEW_VERIFICATION.md`](FROZEN_REVIEW_VERIFICATION.md) for the
freshly reproduced test/lint/security-scan/migration evidence this packet
relies on rather than re-deriving.

**Primary sources this packet indexes rather than duplicates** — a
reviewer should read these directly, not just this summary:
- [`docs/heart-production-closure/ENFORCEMENT_PATH_MATRIX.md`](../heart-production-closure/ENFORCEMENT_PATH_MATRIX.md) — the complete, file:line-grounded execution-path audit (11 paths, 6 real bypasses found, current fix status per finding). This is the single most important document in this packet for topics 9, 26–28.
- [`docs/enterprise/TRUST_BOUNDARIES.md`](../enterprise/TRUST_BOUNDARIES.md) + `SECURITY_ASSURANCE_CASE.md` §3 — the trust-boundary diagrams and boundary-by-boundary validation.
- [`PR50_PR54_INDEPENDENT_REVIEW_PACKET.md`](PR50_PR54_INDEPENDENT_REVIEW_PACKET.md) — the prior packet covering Gaps A–D and the Heart primitives this branch builds on; still accurate for those primitives' design, corrected for test counts.
- `THREAT_MODEL.md`, `SECURITY_ASSURANCE_CASE.md`, `ENTERPRISE_SECURITY.md`, `ENFORCEMENT_BOUNDARY.md` (repo root) — pre-existing, broader security documentation not written for this review but relevant background.

---

## 1. Exact review SHA

`9c6fe838d7fe033c13be4dfd1e05268c67d2c1b1`. See `FROZEN_REVIEW_BASELINE.md` for merge-base, divergence from `origin/main`, and PR metadata — not repeated here to avoid the two documents drifting out of sync.

## 2. Architecture summary

WhitePact/`responsibleai` is an AI-governance control plane: it sits in front of tool/action execution (its own `InternalToolExecutor`, an upstream-MCP proxy, or a dashboard REST action) and decides ALLOW / ALLOW_WITH_REDACTION / DENY / QUARANTINE / REQUIRE_APPROVAL via a deterministic, DB-free `WhitePactRuntimeGateway.evaluate()` (policy/risk/workflow-rule engine), then — new in the Heart initiative — additionally requires a **legitimacy** verdict (`sovereignty_kernel.evaluate()`) proving the acting identity holds real, non-revoked, consent-backed authority before an ALLOW is honored under `enterprise_mode`. A decision becomes an `ExecutionAuthorization` (single-use, TTL-bound, digest-bound to the exact action) that the actual executor must present before running anything. Persistence is SQLite (dev) or PostgreSQL (production), reached only through SQLAlchemy async engines and Alembic migrations (37, currently at head `0037`).

## 3. Trust boundaries

See [`TRUST_BOUNDARIES.md`](../enterprise/TRUST_BOUNDARIES.md) (Mermaid diagrams) and `SECURITY_ASSURANCE_CASE.md` §3 (authoritative prose, boundary-by-boundary). Primary path: User/Agent → Internet → TLS (deployer-configured) → API/MCP transport → Auth → RBAC/tenant isolation → Governance runtime → Policy → Execution Permit → external target. Secondary boundaries (Postgres, Redis, OIDC, LLM provider, webhook targets, upstream MCP servers, CI/CD, secrets manager) are each given their own trust level and validation method in that document.

## 4. Auth flow

Three concrete mechanisms coexist, deliberately: (1) Bearer API key, org-scoped, DB-backed (`OrgRepository.authenticate()`); (2) OIDC JWT (JWKS-validated); (3) VC-JWT (verifiable credential). Hosted-MCP and dashboard-REST both funnel through the same style of dependency (`_authenticate_or_error()` in `mcp/server.py`, `get_org_context()` in `dashboard/app.py`), each with its own legacy/dev-mode fallback branches — see topic 26 (fail-open/fail-closed) and `ENFORCEMENT_PATH_MATRIX.md` Paths 4 and 7 for the specific bypass-adjacent conditions those fallbacks create. `AuthFailureLimiter` (new this session, `dashboard/middleware.py`) rate-limits failed REST auth attempts by remote address, mirroring the MCP server's pre-existing limiter.

## 5. Org/tenant boundary

`org_id` scoping is the tenant boundary throughout. This session's Phase 7 work (`_require_caller_owns_org()`, `dashboard/app.py`) closed a real cross-tenant IDOR across 15 `/api/orgs/{org_id}/...` handlers, found by a new adversarial test suite (`tests/test_cross_tenant_isolation_sweep.py`, 11 tests) — see that suite and `docs/enterprise-readiness/PHASE7_CROSS_TENANT_ISOLATION.md` for the finding and fix detail. `revoke_api_key()` was also fixed to verify the caller owns the key being revoked (same phase). **Not independently re-verified in this Stage-3 pass beyond re-running the existing test suite** (clean, see `FROZEN_REVIEW_VERIFICATION.md` §1) — a reviewer should treat the isolation sweep's 11 tests as the current adversarial coverage, not as proof no other cross-tenant path exists.

## 6. API-key lifecycle

Creation: `create_api_key()` (`dashboard/app.py:1909`). Revocation: `revoke_api_key()` (`dashboard/app.py:1938`), now ownership-checked (Phase 7). **No key-rotation endpoint or scheduled-rotation mechanism was found** in this pass (`grep -n "rotate" src/responsibleai/dashboard/app.py` returns no rotation-specific handler) — rotation today means revoke-then-create, manually. `docs/security/CREDENTIAL_SCOPING_AND_ROTATION.md` documents the intended operational posture; this is a documentation/process control, not an enforced technical one — worth attack-mapping (stale key never rotated because nothing forces it).

## 7. Session lifecycle

No traditional server-side session store was found — auth is per-request (Bearer token/API key/JWT), stateless. "Session lifecycle" in this codebase effectively means API-key/JWT lifetime and expiry, covered under topics 6/8, not a separate session-cookie mechanism. Flagged as a scope note for the reviewer rather than assumed away.

## 8. RBAC / authorization model

`Role` enum (`VIEWER`/`ANALYST`/`ADMIN`/`OWNER`, `dashboard/app.py`), enforced via FastAPI `Depends(require_role(...))` / `Depends(require_plan(...))` dependencies per-endpoint. Billing-plan gating (`Plan.PRO` etc.) is a separate axis from role, both checked as dependencies (e.g. `dashboard/app.py:2600`, `:2973`). **Not exhaustively re-audited endpoint-by-endpoint in this pass** — the Phase 7 IDOR sweep covered org-scoping specifically; a full role-matrix audit (does every ADMIN-only endpoint actually reject ANALYST tokens) is named here as an open attack-map item, not claimed complete.

## 9. `ExecutionAuthorization` lifecycle

Constructed only by `authorize_execution()` (`governance/execution.py:207`) from an ALLOW/ALLOW_WITH_REDACTION decision — DENY/QUARANTINE never produce one; REQUIRE_APPROVAL uses a separate, persisted binding (topic 14). Fields: `action_digest` (binds to the action's exact shape including `purpose`, via `compute_action_digest()`), `target_fingerprint` (optional, re-checked at execute time — `AuthorizationTargetDriftError` on drift), `nonce` (present for a future signed/cross-process future, unused today — see topic 27 caveat), `expires_at` (TTL-bound), `consumed` (single-use). `consent_reference`/`policy_version`/`heart_legitimacy_digest`/`revocation_epoch` are audit/provenance fields, deliberately not re-validated at execute time (documented reasoning inline in `execution.py`'s docstring — they describe the decision, not current external state, so there is nothing to "re-check" the way a target fingerprint has). See `ENFORCEMENT_PATH_MATRIX.md` for which of the 11 execution paths actually construct and check one of these versus bypassing the mechanism entirely.

## 10. Replay protection

`ExecutionAuthorization.consumed` (single-use) plus `governance_execution_nonces` table (migration `0036`) are the structural replay defenses for the synchronous-decision path. `ApprovalRepository.consume()` provides the equivalent single-use guarantee for the REQUIRE_APPROVAL/resume path (topic 14). **Not independently verified against a concurrent double-spend race in this pass** — the mechanism relies on a DB-level unique/consumed check; whether that check is itself race-free under concurrent resume attempts on the same approval is a real attack-map item (see attack map's TOCTOU section), not verified here.

## 11. Purpose binding

`purpose` flows: `ActionRequest.purpose` (raw, caller-supplied) → `resolve_authority_grant()` validates it against the matched `ConsentProof`'s `allowed_action_types`/scope (fail-closed-by-omission: unscoped/mismatched matches nothing) → the *validated* `grant.requested_purpose` (never the raw value) is what `authorize_execution(purpose=...)` receives and what `compute_action_digest()` binds into the authorization, per `execution.py`'s own docstring (topic 9). This closes purpose-substitution-after-authorization for the paths that reach it. **Per the headline finding in `ENFORCEMENT_PATH_MATRIX.md`, this entire mechanism currently has a live-call-site gap for its sibling `consent_repo` wiring status** — re-check that document's "Post-E0 status" table (marked FIXED for the headline finding as of the commits referenced there) rather than assuming purpose-binding is universal across all 11 paths; several paths (stdio, direct import, ungoverned hosted-HTTP) never reach `resolve_authority_grant()` at all, so purpose is not checked there — not a gap in the mechanism, a gap in the mechanism's *reach*.

## 12. Consent legitimacy

`RootAuthorityRecord` / `ConsentProof` / `sovereignty_kernel.evaluate()` — root-authority and consent-backed legitimacy checks, described fully in `PR50_PR54_INDEPENDENT_REVIEW_PACKET.md` (Gap A) and cross-referenced by reach in `ENFORCEMENT_PATH_MATRIX.md`. Per that matrix's headline finding, consent was *initially* found wired but with zero live call sites, then fixed (`consent_repo` threaded into both `governance_integration.py` and `upstream_dispatch.py`, with a regression test through the real HTTP dispatch path). A reviewer should confirm this fix is actually present at the reviewed SHA (it predates this branch's own commits per the matrix's own "Post-E0 status" section, i.e. it was fixed in a commit this branch's history already contains) rather than trust the narrative.

## 13. Approval flow

`ApprovalRequest` persisted with `action_digest`, multi-approver quorum support (`governance_approval_votes`, migration `0018`), workflow-rule-driven routing (`governance_workflow_rules`). REQUIRE_APPROVAL decisions do not produce an `ExecutionAuthorization` at decision time — see topic 14.

## 14. Approval resume flow

`resume_approval()` (`governance_integration.py:638`), reached via `/api/governance/approvals/{id}/execute` (`ENFORCEMENT_PATH_MATRIX.md` Path 6). Per that document: originally, Heart legitimacy was **not** re-checked at resume time — only at the original decision time, an arbitrary human-approval-latency window earlier. **Fixed this session's predecessor work**: `resume_approval()` now re-runs `resolve_authority_grant()` fresh at resume time when the repos are wired, raising `ApprovalRevokedSinceQueuedError` (HTTP 403) if legitimacy no longer holds — `ApprovalRepository.consume()` still runs first (the approval is spent either way, by design, to prevent an attacker from repeatedly probing revocation state via retries). A reviewer should verify this fix is present and test it directly against the "revoke between approval and resume" scenario named in the attack map.

## 15. Revocation

`RevocationEpoch` / `governance_revocation_epochs` (migration `0035`) — durable, multi-instance-safe revocation, with a real deadlock found and fixed during the original Heart Production Closure testing (per PR #55's own description). `ExecutionAuthorization.revocation_epoch` is deliberately left unpopulated — `resolve_authority_grant()` does not query the revocation-epoch repository at grant time (named as an open item in `00_MASTER_READINESS_AUDIT.md`'s "Purpose binding" row, not fixed in this pass). This is a real, honestly-disclosed gap: a grant could in principle be issued referencing a revocation state that isn't itself captured on the resulting authorization object, though the resume-time re-check (topic 14) and the grant-time root/consent lookups (topic 12) each independently consult current state at their own point in time.

## 16. MCP hosted transport (Streamable HTTP / SSE)

Both converge on the same `_call_tool()` chokepoint (`ENFORCEMENT_PATH_MATRIX.md` Paths 2/3) — same auth, same governance branch condition (`ctx.org_id` truthy AND `mcp_governance_enabled=true` AND `enterprise_mode=true`), same bypass conditions when any of those three is unmet.

## 17. MCP stdio behavior

Path 1 in the matrix: no authentication concept at all (no `org_id`/ContextVar), by design ("full unrestricted tool access" per the module's own docstring) — `enterprise_mode=true` narrows it to a static MINIMAL/LOW risk-tier allowlist (not a Heart/legitimacy check), closed further this session (Phase E2: `enterprise_mode=true` now blocks stdio entirely). This is the platform's declared, intentional self-hosted/local-dev capability, not a defect — but it is a real bypass relative to "governed action" and must be represented that way to a reviewer, not hidden behind the word "self-hosted."

## 18. Upstream MCP execution

`UpstreamMCPExecutor` (`upstream_executor.py`) shares `_validate_authorization()` with `InternalToolExecutor`. Reached via Path 5 (dashboard REST) — per the matrix, this is "the MOST consistently governed path found in this audit": unconditional policy/evidence (no separate opt-in flag), explicit legacy/orgless-key rejection. SSRF-guarded at both registration and every delivery (`webhooks/manager.py`'s `validate_webhook_url()` pattern is shared conceptually; upstream-server URLs get equivalent treatment — not independently re-verified line-by-line in this pass, flagged for the attack map).

## 19. SSRF protections

`validate_webhook_url()` (`webhooks/manager.py`). This session found and fixed two real unhandled-exception crash bugs via property-based fuzzing (`tests/test_public_api_fuzz.py`, 12 tests): a malformed IPv6 URL raising `ValueError` from `urlsplit()`, and a pathologically long hostname raising `UnicodeError` from IDNA encoding inside `socket.getaddrinfo()` — both now caught and converted to `UnsafeWebhookURLError` rather than crashing the request handler. This is a genuine, fuzz-discovered improvement, not a theoretical one. **Scope note:** the fuzz suite targets the webhook-URL validator specifically; whether the same validator (or an equivalent) actually gates every upstream-MCP-server URL registration path was not re-verified line-by-line in this pass — attack-map item.

## 20. Evidence/audit integrity

`governance_evidence` table with hash-chain integrity added to `audit_log` (migration `0004`), policy versioning (migration `0015`), delegation-chain binding (migration `0019`). `docs/operations/DR_RESTORE_DRILL.md` documents a real (not simulated) `pg_dump`/drop/recreate/restore cycle performed this session against local PostgreSQL 17. **Chain-tampering/fork-prevention was added via a uniqueness constraint** (migration `0032`, "Add uniqueness constraints preventing forked evidence hash chains") but this pass did not independently attempt to fork or tamper with a chain to confirm the constraint actually blocks it end-to-end — attack-map item.

## 21. Database security

Async SQLAlchemy, parameterized queries only (per `TRUST_BOUNDARIES.md`'s own claim — not independently re-audited for raw-SQL/string-interpolation exceptions in this pass beyond what `bandit` would catch, which came back clean, `FROZEN_REVIEW_VERIFICATION.md` §5). PostgreSQL migration round-trip (all 37, both directions) freshly verified against a real server this stage (§12 of that same document). SQLite (`aiosqlite`) is the dev/test default; the earlier `test_v1_api.py` hang finding (this session's predecessor work) demonstrated that an unpatched `Settings` singleton silently defaults to a real on-disk SQLite file (`~/.responsibleai/data.db`) rather than `:memory:` — fixed for tests, but the same silent-fallback behavior exists in `migrations/env.py`'s `_resolve_url()` for production too (confirmed directly in this Stage-1 pass: setting the wrong env-var name silently produced a SQLite migration instead of erroring) — **this is a real, newly-surfaced configuration-hygiene finding**: a misconfigured `RAI_DB_URL`/`RAI_DATABASE_URL` variable name produces silent fallback to SQLite with no warning, which in a real deployment could mean "production" quietly runs against an ephemeral or wrong database. Not fixed in this pass (out of Stage-1/2/3 scope); flagged here and in the attack map.

## 22. Secrets/crypto configuration

`docs/security/PRODUCTION_CONFIGURATION_STANDARD.md` and `CREDENTIAL_SCOPING_AND_ROTATION.md` (this session's predecessor work) document the intended posture. This session's Phase 9 fix (`logging_config.py`) caps `aiosqlite`/`asyncpg` logger levels at INFO regardless of configured app level, closing a real secret-leak-via-DEBUG-logging path found by a new adversarial suite (`tests/test_secrets_never_logged_sweep.py`, 3 tests). `gitleaks` clean across 68 commits (`FROZEN_REVIEW_VERIFICATION.md` §8). Crypto key material: `governance_crypto_keys` table (migration `0029`) — key generation/storage internals not independently re-audited in this pass.

## 23. Webhook security

Covered under topic 19 (SSRF) plus signature verification (`wiki/Webhooks.md` documents HMAC-SHA256 signing — `verify_signature()`). Replay protection for inbound webhook *deliveries* specifically (as opposed to outbound SSRF validation) was not independently re-verified in this pass — attack-map item.

## 24. Billing/entitlement boundaries

`Plan` enum + `require_plan()` dependency (`dashboard/app.py:919`), Stripe fields on `organizations` (migration `0003`). Not independently re-audited for plan-downgrade/entitlement-bypass scenarios in this pass — attack-map item (a cancelled/downgraded org retaining PRO-gated access via a cached or stale token, for example).

## 25. Enterprise mode

`enterprise_mode` is the master flag gating Heart legitimacy enforcement across every path in `ENFORCEMENT_PATH_MATRIX.md`. `heart_production_gate.py`'s `verify_heart_production_enforcement()` (Gap C, prior initiative) is a fail-closed startup invariant — refuses to start under invalid combinations (e.g. `enterprise_mode=true` + `mcp_http_allow_unauthenticated_demo=true`, closed Phase E4). This session's E0 audit found and fixed a real wiring gap: this startup gate was only ever called from the dashboard process, not the MCP server process — now wired into both. **Named-but-not-yet-closed configuration gap** (topic 26): nothing currently requires `auth_enabled=true` when `enterprise_mode=true` — a deployment can satisfy every existing startup check while leaving REST auth disabled.

## 26. Fail-open/fail-closed decisions

The project's stated design principle throughout (`resolve_authority_grant()`, consent matching, purpose validation) is fail-closed-by-omission: an unscoped or mismatched field matches nothing, never everything. The **known exceptions** to this posture, all honestly documented rather than hidden:
- stdio transport: fails open by design (declared capability) when `enterprise_mode=false` (the default), and even under `enterprise_mode=true` prior to Phase E2 allowed MINIMAL/LOW tools with zero Heart check (now blocked entirely).
- `mcp_governance_enabled=false` (default on hosted transports): governance entirely skipped, not a partial fail-open — a full bypass to bare `dispatch_tool()`.
- `enterprise_mode=false` (the dev/self-hosted default): Heart root-check skipped even when other governance runs.
- `auth_enabled=false` (dev mode, dashboard REST): zero credential required, `Role.OWNER` granted — not itself an execution bypass (org-scoped execution endpoints explicitly reject `org_id=None`) but a real read/config-mutation exposure under a nonsensical-but-currently-unblocked combination with `enterprise_mode=true`.
- `migrations/env.py`'s DB-URL resolution (topic 21): silently falls back rather than erroring on a misconfigured env var name.

## 27. Network-reachable execution paths

Every path in `ENFORCEMENT_PATH_MATRIX.md` except Path 8 (direct Python import) and Path 9 (unrelated CLI) is reachable over the network in some deployment configuration. The matrix's summary table is the authoritative per-path breakdown of which network paths are governed under which flag combinations and which are not — reproduced in the attack map (`PR55_ATTACK_MAP.md`) rather than duplicated a third time here.

## 28. In-process-only execution paths

**Path 8 — direct Python import of `dispatch_tool()`** (renamed `_dispatch_tool_unchecked()`, Phase E5). This is the one structural, honestly-unclosed gap this entire security-freeze process exists to surface plainly rather than paper over. See Stage 4 (`docs/architecture/EXECUTION_PROCESS_BOUNDARY_STATEMENT.md`, to be produced in this same pass) for the required precise framing: **network-reachable execution is expected to pass governance under enterprise-mode guarantees where verified above; in-process trusted-code execution can bypass application-level controls, because Python offers no in-process privilege boundary a renamed private function can enforce.** A drift-guard test (`tests/test_dispatch_tool_unchecked_call_sites.py`) fails the suite if a new call site, re-export, or public alias ever appears — this bounds *accidental* drift, not a deliberate in-process bypass by someone with repo/deploy access.

## 29. Known structural bypasses

Enumerated fully in topics 17, 25–28 and the matrix's "Six real bypasses found, not four" section: (1) stdio by design, (2) `mcp_governance_enabled=false`, (3) `enterprise_mode=false`, (4) legacy/demo hosted-MCP auth (mostly closed, see matrix Path 4's correction), (5) consent-not-consulted-live (fixed), (6) approval-resume-doesn't-recheck (fixed). Plus this packet's own newly-surfaced items: the `auth_enabled` configuration gap (topic 26) and the silent DB-URL-fallback gap (topic 21). **None of these are claimed fully closed except where the matrix's "Post-E0 status" table explicitly says FIXED** — a reviewer should treat every "FIXED" claim in that table as itself requiring independent confirmation, not just this packet's citation of it.

## 30. Known infrastructure gaps

- ~~No CI/CodeQL has ever run on this branch or PR #55~~ — **CLOSED (2026-09-02).** Root cause was a base-branch trigger-filter mismatch (`FROZEN_REVIEW_VERIFICATION.md` §11), fixed and verified: at SHA `860c806c510d049ad53c94f8e3e449c0acf7265c`, real GitHub Actions CI now runs against PR #55 and all 12 checks pass. See [`CI_GAP_ROOT_CAUSE_AND_FIX.md`](CI_GAP_ROOT_CAUSE_AND_FIX.md). Every check in this packet's evidentiary base up to `54e9cb8` was run manually/locally only; from `860c806` onward, GitHub-attested CI evidence also exists.
- Live AWS S3 Object Lock verification: BLOCKED, no credentials/infrastructure in this environment (Gap D, prior initiative) — implementation exists, live behavior unverified. See Stage 9 of the governing directive for the required future verification protocol; not attempted in this pass.
- Docker/production-container verification: hardening flags added (`read_only`, `cap_drop: [ALL]`, `no-new-privileges`, image digest pinning) but **not smoke-tested against a live container** — no Docker daemon in this environment, stated honestly rather than claimed verified.
- No key-rotation mechanism (topic 6), no independent chain-tamper attempt (topic 20), no plan-downgrade/entitlement-bypass test (topic 24), no webhook-delivery-replay test (topic 23) — each named as a real, currently-unfilled gap in this pass's own coverage, not asserted as safe by omission.

---

## Honest coverage statement

This packet indexes and extends the existing `ENFORCEMENT_PATH_MATRIX.md`/`TRUST_BOUNDARIES.md`/`PR50_PR54` body of work rather than re-deriving all 30 topics from a blank slate in this single pass. Topics 2–4, 9–10, 14–20, 25–29 rest on prior, file:line-grounded audit work this packet cites specifically enough to be checked. Topics 6, 7, 21 (DB-URL fallback), 22, 23, 24 include genuinely new findings surfaced during this Stage 1–3 pass. Topics 6, 8, 18, 20, 23, 24 explicitly name gaps in *this packet's own* coverage depth, not just the system's — a reviewer should treat those as open review-scope items, not as "checked and clean."
