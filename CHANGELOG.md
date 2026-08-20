# Changelog

All notable changes to this project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- Tool Trust Network (Authority Everywhere Phase 8) —
  `governance/tool_trust.py`: a deterministic 0-100 trust score per
  org-registered upstream MCP server, derived from the existing
  supply-chain scanner's findings plus incident history, with an
  audited admin-override path. A `BLOCKED` tier now denies a proxied
  call before governance is even consulted
  (`mcp/upstream_dispatch.py`), using the previously-reserved
  `ReasonCode.UNTRUSTED_MCP_SERVER`. New DB table `tool_trust_scores`
  (migration `0024`) and REST endpoints under
  `/api/governance/upstream/servers/{id}/trust` (`GET`, `POST .../scan`,
  `POST .../override`).
- Execution Permit v2 (Authority Everywhere Phase 9) —
  `ExecutionAuthorization` gained an optional `target_fingerprint`,
  closing a real gap where an upstream target string's *resolved*
  config (URL, enabled state, credential presence) could drift between
  a governance decision and its execution without the action digest
  changing. `AuthorizationTargetDriftError` now refuses execution on a
  mismatch (`governance/execution.py`, `governance/upstream_executor.py`).
- JIT Credential Broker (Authority Everywhere Phase 10) —
  `governance/jit_credential.py`: `UpstreamMCPExecutor` no longer reads
  `UpstreamServer.auth_token` directly; it must obtain a single-use,
  time-boxed `JITCredential` bound to the exact, already-validated
  `ExecutionAuthorization` for this call (expiry capped at the permit's
  own remaining TTL), with every issuance and consumption recorded to
  a new audit trail (`credential_issuances`, migration `0025`,
  `db/credential_issuance_repository.py`) that never stores the secret
  value itself. Stated honestly: this mediates and time-boxes access to
  an existing standing credential — it does not perform OAuth token
  exchange or mint a new, narrower upstream-side credential.
- Causal Influence Firewall (Authority Everywhere Phase 7) —
  `governance/causal_influence.py`: generalizes
  `governance/memory_firewall.py`'s persistent-memory-only
  injection-pattern scan to any upstream content a caller declares
  causally shaped an action (a prior tool's output, a sub-agent's
  result, external content) via a reserved `_provenance` argument key.
  `memory_firewall.py`'s public API is unchanged, absorbed rather than
  replaced (Phase 0's own classification) — its pattern table moved to
  the new module as the canonical location. A matched pattern is a hard
  `DENY` (`ReasonCode.CAUSAL_INFLUENCE_VIOLATION`); merely untrusted
  provenance with no match is a softer, non-blocking, evidence-visible
  marker (`ReasonCode.CAUSAL_INFLUENCE_UNTRUSTED_SOURCE`). New MCP tool
  `rai_causal_influence_check` (30th tool).
- Outcome Observation, Reconciliation, and Attestation (Authority
  Everywhere Phases 12-14) — `governance/outcome.py`: an
  `OutcomeRecord` (`SUCCEEDED`/`FAILED`/`ERRORED`) is now auto-recorded,
  fail-open, for every governed action's execution attempt, linked to
  its authorizing `EvidenceRecord` (new `governance_outcomes` table,
  migration `0026`). `governance/reconciliation.py` flags a decision
  that authorized execution but never got an outcome reported
  (`MISSING_OUTCOME`). `governance/attestation.py` packages
  decision + outcome + reconciliation into one exportable record —
  **not cryptographically signed**, stated in its own docstring:
  integrity is by linkage to the existing `EvidenceRecord` hash chain,
  not a new signature scheme. New endpoints
  `POST /api/governance/evidence/{id}/outcome` (manual reporting) and
  `GET /api/governance/evidence/{id}/attestation`.
- Verified Principal (Authority Everywhere Phase 3) —
  `auth/verifiable_credential.py`: `VerifiableCredentialProvider`
  verifies a Bearer JWT-VC presentation against an admin-configured
  trusted-issuer allowlist (`Settings.vc_trusted_issuers`), reusing
  `auth/oidc.py`'s JWKS-fetch and weak/private-key-rejection machinery.
  Lets a non-human principal — a service account, or another
  organization's attested agent — authenticate to the hosted MCP
  server (`mcp/server.py`'s `_authenticate`) alongside the existing
  static-API-key and OIDC paths. Verified principals resolve to a new
  `IdentityContext` kind (`"vc"`, `governance/models.py`) via a
  field-names-only `PrincipalClaim` (`governance/principal.py`) and are
  logged to a new append-only `verified_principals` audit table
  (migration `0027`). Not built: DID resolution, JSON-LD proofs,
  OpenID4VP presentation exchange, or revocation-list checking — see
  the module's own docstring for the full scoping.
- See `docs/architecture/AUTHORITY_EVERYWHERE.md` and
  `MIGRATION_WHITEPACT_V2.md` Sections 17-21 for the full design and
  structured phase verdicts. 24 + 17 + 26 + 20 + 21 new tests
  (`tests/test_tool_trust.py`, `tests/test_jit_credential.py`,
  `tests/test_causal_influence.py`,
  `tests/test_outcome_reconciliation_attestation.py`,
  `tests/test_verifiable_credential.py` +
  `tests/test_mcp_verified_principal.py`).

## [1.2.3] — 2026-08-19

### Added

- SAML 2.0 SSO support, independent of the existing OIDC integration —
  `src/responsibleai/auth/saml.py` (AuthnRequest generation, signed-
  response validation via `signxml`, XXE-safe XML parsing, WhitePact's
  own short-lived post-login session token since SAML has no bearer-
  token concept the way OIDC does). Supports both SP-initiated and
  IdP-initiated login flows. New routes: `GET /api/auth/login/saml`,
  `POST /api/auth/acs`, `GET /api/auth/saml/metadata`. Closes the
  "SAML is not supported" gap `ENTERPRISE_SECURITY.md` previously
  stated plainly. 31 new tests in `tests/test_saml.py`, including real
  signed-assertion round trips and the security-critical rejection
  paths (tampered assertion, wrong signing cert, unsigned assertion,
  expired/not-yet-valid assertion, wrong audience, replayed/mismatched
  request ID).
- Custom domain `whitepact.com` registered and wired to the hosted
  dashboard on Render (DNS verified, TLS certificate issued
  2026-08-17) — `https://responsibleai-dashboard.onrender.com` keeps
  resolving to the same service unchanged.
- Multi-approver quorum for `REQUIRE_APPROVAL` decisions on high-risk
  actions — configurable `required_approvals` (default 2 for HIGH
  risk tier), `governance_approval_votes` table, veto-on-any-DENY
  semantics, replay-guarded against a resolver voting twice.
- Delegation chains on `AuthorityContext.delegation_chain`, validated
  against the acting identity and a configurable `max_delegation_depth`,
  carried through to `EvidenceRecord` for audit.
- Upstream MCP tool discovery — `GET /api/governance/upstream/tools`
  queries every registered upstream server in parallel, per-server
  timeout-bounded, namespaced `server_id::tool_name` results; one dead
  server can't hang or hide the rest.
- Public, unauthenticated `/.well-known/mcp/server-card.json` on the
  hosted MCP HTTP transport, serving the same live `TOOL_DEFS`/
  `RESOURCE_DEFS` the server advertises over MCP itself — lets
  directories without an OAuth authorization server configured (this
  deployment only supports static Bearer API keys) complete a listing
  without a live authenticated scan.
- `.github/workflows/security-scan.yml` — weekly + on-push Bandit
  (SAST) + pip-audit (dependency vulnerability) scan, the free, honest
  interim signal ahead of a real, paid, independent penetration test.
- `compliance/NO_BUDGET_TRUST_PATH.md` — researched, real options for
  legal entity formation, penetration testing, and SOC 2 under a
  dev/scaling-only budget constraint.
- `scripts/caiq_answers.py` + `compliance/CAIQv4.0.3_WhitePact_completed.xlsx`
  — the full, honestly-answered 261-question CSA STAR CAIQ v4.0.3
  questionnaire (107 Yes / 122 No / 32 N/A), submitted to the CSA STAR
  Registry, Level 1 (currently pending CSA's own review).
- WhitePact is now listed on the official MCP Registry
  (`io.github.Guruprasath-Annadurai/whitepact`) and on Smithery
  (`guruprasathannadurai-official/whitepact`) — both verified live,
  not just submitted.
- `whitepact-mcp-http` — a second Render web service hosting the
  Streamable HTTP MCP transport publicly for the first time; the
  dashboard service alone never served `/mcp`.
- `SECURITY_ASSURANCE_CASE.md` — OpenSSF Best Practices Silver's
  `assurance_case` criterion: 12 defensible security claims, a
  24-entry threat model (asset/attacker/attack/trust boundary/control/
  test/residual risk), an explicit trust-boundary diagram, secure-
  design-principle citations, a common-implementation-weaknesses
  matrix, a supply-chain argument, and an evidence matrix — every
  control cross-checked against current source, not copied from prior
  docs.
- Signed Git release tags (`version_tags_signed`) — `verify-signed-tag`
  job in `.github/workflows/publish.yml` rejects lightweight tags,
  unsigned tags, invalid signatures, and unapproved signers before any
  build/publish step runs. `compliance/SIGNED_VERSION_TAGS.md` audits
  all prior release tags (none were signed) and documents the new
  policy; `security/release-signers.allowed` holds the approved public
  signing key; `VERIFY_RELEASE.md` documents both the tag-signature and
  the artifact-provenance verification paths for users.
- `ruff format --check` is now a hard CI gate alongside `ruff check`
  (`.github/workflows/ci.yml`) — the coding-standard check previously
  only covered linting, not formatting.

### Fixed

- Seven call sites across `dashboard/app.py`, `mcp/tools.py`, and
  `mcp/resources.py` (`/api/health`, `/api/version`,
  `/api/support/status`, the `X-API-Version` header, the
  `rai_audit_summary`/`rai_health` MCP tools, the `rai://health` MCP
  resource) had the package version hardcoded as a literal string,
  silently stale since the 1.2.1/1.2.2 releases. Now read
  `responsibleai.__version__` everywhere; tests assert against the
  real value instead of a literal so this can't drift stale again.
- A real ~17-day hosted-instance outage (2026-07-26 to 2026-08-12):
  the Supabase free-tier database auto-paused from inactivity, and
  every deploy since crashed at startup on an unreachable-tenant
  pooler error — including pure-documentation commits, which is what
  ruled out the application code as the cause. Resolved by freeing a
  Supabase free-tier project slot and resuming the paused database;
  no data lost.

---

## [1.2.2] — 2026-08-12

### Fixed

- `mcp-name` verification marker in `README.md` and `server.json`'s
  `name` field corrected to `io.github.Guruprasath-Annadurai/whitepact`
  (matching the exact casing of the authenticated GitHub account). The
  MCP Registry's publish validation is case-sensitive on both the
  namespace-ownership check (against the GitHub OAuth identity) and
  the PyPI-package-ownership check (against the literal `mcp-name:`
  line in the published README) — the 1.2.1 release used all-lowercase
  in both places and failed both checks in turn once actually tried.

---

## [1.2.1] — 2026-08-12

### Added

- `mcp-name: io.github.guruprasath-annadurai/whitepact` verification
  marker in `README.md` (rendered as an invisible HTML comment) —
  the ownership-proof the official MCP Registry's `mcp-publisher` CLI
  requires in a PyPI package's README before it will let the
  `io.github.guruprasath-annadurai/whitepact` namespace publish
  against the `rai-governance-platform` PyPI package. No behavior
  change; PATCH bump exists solely to get this marker onto a live
  PyPI release so registry publishing can proceed.

---

## [1.2.0] — 2026-08-12

Two development pushes, shipped together as one release since neither
had reached PyPI before now (the previous published version is
`1.1.0`): the pre-migration batch below (Leaderboard, Trust Index,
Incident Database, MFA, and a set of real security fixes) and the full
WhitePact Enterprise Foundation v2 migration on top of it. See `SPEC.md`
and `MIGRATION_WHITEPACT_V2.md` for full detail on every item below;
this entry summarizes, it isn't the source of truth.

### Added — WhitePact Enterprise Foundation v2 migration

Additive throughout: every `RAI_`/`responsibleai`/`rai://` name kept
working unchanged (see `MIGRATION_WHITEPACT_V2.md` Section 14's
timeline).

- **`whitepact` alias package** (`src/whitepact/`) re-exporting
  `responsibleai`'s public API by object identity, plus
  `WHITEPACT_*` env var precedence and `whitepact`/`whitepact-mcp`/
  `whitepact-mcp-http` console script names.
- **MCP server identity migration** — protocol name `whitepact`, dual
  `whitepact://`/`rai://` resource URI schemes.
- **Streamable HTTP MCP transport** (`/mcp`, spec 2025-03-26+) —
  additive alongside the existing HTTP+SSE transport (`/sse` +
  `/messages/`), which keeps running unmodified.
- **MCP transport security hardening** — DNS rebinding protection
  (opt-in) and a shared per-IP auth-failure rate limiter across both
  hosted transports.
- **MCP OAuth/OIDC resource server** — hosted transports now accept an
  OIDC-issued JWT (reusing the dashboard's existing SSO config) in
  addition to static API keys; RFC 9728 protected-resource metadata.
- **Structured tool-output contracts** (spec 2025-06-18) — all 27 MCP
  tools now return `structuredContent` alongside the legacy text blob.
- **Runtime governance core** (`src/responsibleai/governance/`) —
  `GovernanceDecision` (`ALLOW`/`ALLOW_WITH_REDACTION`/
  `REQUIRE_APPROVAL`/`DENY`/`QUARANTINE`), `WhitePactRuntimeGateway`,
  risk-tiered routing, a first policy engine, hash-chained evidence
  persistence (per-org chain, tamper-detectable), and a first
  approval workflow (`PENDING`→`APPROVED`/`DENIED`, race-safe
  resolution) — exposed via `/api/governance/*`.
- **MCP Trust/Supply-Chain Scanner** (`src/responsibleai/supplychain/`)
  — evaluates a third-party MCP server manifest (confusable-character/
  typosquat check, tool-description content scan, known-incident
  cross-reference), every finding classified `VERIFIED_FACT`/
  `INFERRED_SIGNAL`/`UNKNOWN`, never a single score.
  `POST /api/governance/supplychain/scan`.
- **HA Helm deployment for the hosted MCP transport** — a second
  Deployment (`mcp-*.yaml` templates) with the same replica/HPA/PDB/
  anti-affinity posture as the dashboard, previously undeployable via
  Helm at all.
- **Supply chain security** (CI) — CycloneDX SBOM generated on every
  build and attached to releases, Sigstore build provenance
  attestation on published artifacts, dependency-review gating on
  pull requests.
- **`THREAT_MODEL.md`**, **`DETERMINISTIC_VS_PROBABILISTIC.md`**,
  **`BENCHMARKS.md`** — new documents; `CONTRIBUTING.md`/`README.md`
  rewritten for the current architecture.
- **`GovernanceDecision.QUARANTINE` is now reachable** —
  `governance/quarantine.py` tracks a caller's recent `DENY` decisions
  (persisted evidence, rolling window) and the gateway returns
  `QUARANTINE` at or above a fixed threshold, before even checking
  authority.
- **`AgentContext.trust_state` is populated and consulted** —
  `governance/trust_integration.py` looks it up via the existing
  `TrustClient` when an action names a provider+model; a known,
  low-scoring model downgrades an otherwise-`ALLOW` decision to
  `REQUIRE_APPROVAL`.
- **Persisted governance policy rules** — new `governance_policies`
  table (migration `0012`), `PolicyRepository` (add/remove/reorder),
  and `GET/POST/DELETE /api/governance/policy*` endpoints. Policy rules
  no longer only exist as in-code objects.
- **MCP dispatch-path governance wiring** (opt-in,
  `Settings.mcp_governance_enabled`, default `False`) — every hosted
  Streamable HTTP/SSE tool call can now be evaluated by
  `WhitePactRuntimeGateway` before it executes: `DENY`/`QUARANTINE`
  block execution, `REQUIRE_APPROVAL` queues a real `ApprovalRequest`
  instead of running the tool, `ALLOW_WITH_REDACTION` substitutes
  redacted arguments. Off by default — a real behavior change for
  anyone who enables it, so existing hosted deployments are unaffected
  unless they opt in. A queued `REQUIRE_APPROVAL` now fires a real
  webhook (`WebhookEvent.APPROVAL_REQUESTED`) if the org has one
  registered, and an `EvidenceRepository.record()` failure now fails
  the call closed (blocked, clear error) instead of crashing.
- Branch protection on `main` — all four CI checks required, force-push
  and branch deletion disabled.
- **`compliance/SOC2_ALTERNATIVE_PATH.md`** + OpenSSF Scorecard
  (`.github/workflows/scorecard.yml`, README badge) — free,
  independently verifiable trust signals for when a paid SOC 2 audit
  isn't yet affordable, researched with real 2026 pricing.

### Fixed — WhitePact Enterprise Foundation v2 migration
- Stale `__version__ = "0.4.0"` in `responsibleai/__init__.py` (didn't
  match `pyproject.toml`'s `1.2.0`).
- Hardcoded-stale tool/resource counts in the MCP `health` resource
  payload.
- Unbounded `mcp>=1.0.0` dependency constraint that let a fresh CI
  install pick up the MCP SDK's breaking 2.0.0 release; pinned
  `<2.0.0` with the SDK-kwarg-rename migration tracked as separate,
  deliberate future work.
- Audit log entries were silently recorded with `org_id: null` for every
  request regardless of the real caller, because `AuditLogMiddleware`
  (a `BaseHTTPMiddleware`) read a `ContextVar` that Starlette's internal
  task-group boundary prevented the auth dependency from actually
  populating — making `GET /api/audit`'s per-org scoping vacuous. Fixed
  by moving org/key attribution onto `request.state`; see
  `THREAT_MODEL.md`'s Dashboard REST API section and
  `tests/test_tenant_isolation.py` for the regression test.

### Added — pre-migration batch (built 2026-07-23, shipped now)
- **Public Leaderboard** — cross-model trust leaderboard computed by
  actually calling each model's public inference API against a fixed
  prompt corpus (not self-reported): `leaderboard_models`/`leaderboard_runs`
  tables, `LeaderboardRunner`, `GET /api/leaderboard`, public UI page,
  `scripts/run_leaderboard_eval.py`, methodology doc
  (`compliance/LEADERBOARD_METHODOLOGY.md`).
- **Trust Index / Trust Passports** — the open, citable trust-scoring
  standard (`compliance/TRUST_INDEX_SPEC.md`, six weighted dimensions):
  `POST /api/trust-index/assess` (free self-assessment),
  `GET /api/trust-index/verify/{id}` (public verification),
  `POST /api/trust-index/certify/{id}` (human-reviewed certification,
  no automated path by design), `GET /api/trust-index/certified`
  directory, public `/verify/{id}` page, and an embeddable SVG badge
  (`GET /api/trust-index/badge/{id}.svg`) with copy-paste HTML/Markdown
  snippets distinguishing "Self-Assessed" from "Certified".
- **Public AI Incident Database** — crowd-reported, moderator-reviewed
  incident registry: `public_incident_reports` table, report/list/get/
  verify/admin-review endpoints, paid `check` endpoint, public list and
  detail pages.
- **TOTP MFA** (RFC 6238, `pyotp`) for the one interactive human login
  step (`POST /api/auth/login-key`), org-enforceable
  (`PUT /api/orgs/{id}/mfa`), single-use backup codes.
- **Field-level encryption expanded** from one column to four:
  `audit_log.ip_address`, `public_incident_reports.reporter_name`/
  `.reporter_contact`, `webhook_configs.secret`, `org_api_keys.mfa_secret`
  — opt-in via `RAI_FIELD_ENCRYPTION_KEY`, with real key-rotation support
  (`MultiFernet`, comma-separated key list) and a re-encryption sweep
  script (`scripts/rotate_field_encryption_key.py`).
- **Webhook configuration persisted to the database** (previously
  in-memory only) — survives restarts, and the retry worker claims
  pending deliveries atomically so running multiple replicas doesn't
  double-fire a delivery.
- **Multi-replica/HA readiness self-check** — `RAI_MULTI_REPLICA=true`
  self-declaration flags a `multi_replica_misconfigured` warning at
  startup if SQLite or in-memory rate limiting can't safely be shared
  across replicas.
- **Full dashboard UI rebuild** on a self-contained, CDN-free shared
  design system (`static/css/app.css`, `static/js/app.js`) — every page
  (overview, evaluate, guardrails, hallucination, cost, router,
  trust-scores, eval/compare/benchmark, red team, audit, incidents,
  webhooks, organizations, billing, settings) restyled and wired.
- **White-label branding support** — `RAI_BRAND_NAME`/`RAI_BRAND_LOGO_URL`
  config plus `GET /api/branding`, swapping the sidebar name/logo and tab
  title across every page with no frontend fork.
- **One-command self-hosted deploy** — `scripts/deploy.sh` automates
  secret generation, `.env.prod` creation, bringing
  `docker-compose.prod.yml` up, running migrations, and local health
  verification.
- **`/api/health` now returns HTTP 503** (not 200) when its database
  check fails, so load-balancer/orchestrator health probes can actually
  detect a degraded instance.
- **Legal, compliance, and go-to-market documentation**: `TERMS_OF_SERVICE.md`,
  `PRIVACY_POLICY.md` (drafts, attorney-review pending), a SOC 2
  readiness package mapped to the AICPA Trust Services Criteria
  (`compliance/SOC2_READINESS.md`), a real internal security review
  (`compliance/INTERNAL_SECURITY_REVIEW.md`), an OEM/white-label
  licensing one-pager, a compliance-methodology starter kit for other
  companies (`compliance/starter-kit/`, `scripts/generate_compliance_kit.py`),
  an insurance/underwriting partnership pitch, and the Trust Index
  methodology written up as an arXiv-ready paper
  (`compliance/TRUST_INDEX_PAPER.md`).
- **A genuinely live hosted instance** — `https://responsibleai-dashboard.onrender.com`,
  running on a card-free managed-services stack (Render for compute,
  Supabase for Postgres, Upstash for Redis) after both Oracle Cloud's and
  Google Cloud's signup flows hit real friction.

### Fixed — pre-migration batch
- **`nltk` PYSEC-2026-597** (path traversal) — moved out of the mandatory
  dependency set into an opt-in `[sentiment]` extra; the one call site
  passes a hardcoded, non-attacker-controlled resource name.
- **SQL injection pattern** in `CostTracker` (f-string query construction
  in `get_model_breakdown`/`get_team_breakdown`/`request_count`) —
  switched to parameterized queries.
- **SSRF in webhook delivery** — an admin could register a webhook
  pointing at cloud metadata endpoints or internal network addresses;
  added `validate_webhook_url()`, checked at registration and at every
  delivery (handles DNS rebinding), plus disabled redirect-following.
- **Stored XSS on the public `/verify/{id}` page** — `model_name`/
  `provider`/`certified_by` were concatenated into `innerHTML` unescaped
  on a public, unauthenticated page; now escaped via a shared `esc()`
  helper.
- **`Dockerfile` silently missing dependencies** (`pyotp`, `sqlalchemy`,
  `aiosqlite`, `websockets`, `prometheus-client`, `cryptography`) — a
  hand-maintained `pip install` package list had drifted out of sync with
  `pyproject.toml`'s `dashboard` extra since MFA/field-encryption
  shipped; now installs via the wheel's own extras instead.
- **Supabase transaction-pooler incompatibility** — PgBouncer/Supavisor
  transaction-mode pooling breaks asyncpg's prepared-statement cache;
  fixed with `statement_cache_size=0` in both `db/engine.py` and
  `migrations/env.py` (a separate engine-construction path Alembic uses).

### Tests
- Combined result as of this release: **1586 passed** (up from 919 in
  1.1.0 — 1271 after the pre-migration batch above, then the full
  WhitePact migration on top of that).

---

## [1.1.0] — 2026-06-27

### Added
- **MCP Server** (`responsibleai.mcp`) — the primary enterprise distribution channel
  - `responsibleai-mcp` CLI entry point; configure Claude Code by pointing `mcpServers.responsibleai` at it
  - **10 governance tools**: `rai_scan`, `rai_trust_score`, `rai_compliance`, `rai_hallucination`, `rai_cost_estimate`, `rai_redteam_payloads`, `rai_redteam_analyze`, `rai_compare_models`, `rai_audit_summary`, `rai_health`
  - **5 resources**: `rai://health`, `rai://models/catalog`, `rai://compliance/frameworks`, `rai://redteam/categories`, `rai://trust/dimensions`
  - Pure-computation tools run in-process (no REST server required for MCP usage)
  - `mcp>=1.0.0` added to core dependencies; `responsibleai-mcp` added to project scripts
- **Audit log API endpoints**
  - `GET /api/audit` — paginated governance audit log with optional `org_id`, `endpoint`, `days`, `limit`, `offset` filters
  - `GET /api/audit/export` — full CSV download of audit log
  - `GET /api/audit/summary` — top-N endpoints by request count and average latency
- **Red team API endpoints**
  - `GET /api/redteam/payloads` — all 10 adversarial attack payloads, filterable by category
  - `POST /api/redteam/analyze` — submit model responses and get a security report with vulnerability findings and security score
- **Billing / revenue metering**
  - `GET /api/billing/usage` — per-period cost summary, token totals, and per-model breakdown for billing integrations
- **Version bump to 1.1.0**
  - `X-API-Version: 1.1.0` on all responses
  - `api_versions` now reports `["1.0", "1.1"]`
  - Health endpoint modules list extended with `mcp_server` and `billing`

### Changed
- `pyproject.toml` version `1.0.0` → `1.1.0`
- Existing `/api/v1/*` prefix continues to work (no changes to routing middleware)

### Tests
- 919 tests passing (was 850), coverage 86%
- `tests/test_mcp_server.py` — 39 tests covering all MCP tools and resources
- `tests/test_redteam_audit_billing_api.py` — 30 tests covering the new REST endpoints

---

## [1.0.0] — 2026-06-26

### Added
- **Stable versioned API** — all breaking changes frozen after this release
  - `GET /api/version` — returns version, stability metadata, and changelog URL
  - `/api/v1/*` URL prefix supported via transparent rewrite middleware (no redirect overhead)
  - `X-API-Version: 1.0.0` and `X-API-Min-Version: 1.0.0` response headers on every call
  - Health endpoint reports `api_versions`, `stable_since` fields
- **Single Sign-On — OAuth2 / OIDC** (`responsibleai.auth`)
  - `OIDCProvider` — async JWKS caching, JWT validation (RS256/RS384/RS512/ES256/ES384/ES512)
  - `AsyncJWKSClient` — fetches and caches JSON Web Key Sets with 1-hour TTL
  - `JWTClaims` — frozen dataclass: `sub`, `email`, `name`, `roles`, `org_id`
  - Discovery document auto-fetch from `{issuer}/.well-known/openid-configuration`
  - New config fields: `oidc_issuer`, `oidc_client_id`, `oidc_client_secret`, `oidc_redirect_uri`, `oidc_scopes`, `oidc_jwks_uri`, `oidc_skip_verification`
  - `GET /api/auth/providers` — list configured auth providers
  - `GET /api/auth/login/{provider_id}` — initiate OAuth2 authorization code flow
  - `GET /api/auth/callback` — exchange code, validate token, return claims
  - `POST /api/auth/logout` — invalidate session
- **SLA-backed support tier**
  - `GET /api/support` — three-tier support table (Standard / Professional / Enterprise) with uptime SLAs and response times
  - `GET /api/support/status` — public platform status page (no auth required)
  - SLA.md updated with full support tier breakdown and direct contact info
- **Kubernetes Helm chart** (`helm/rai-governance/`)
  - `Deployment` with pod anti-affinity, non-root security context, read-only root filesystem
  - `HorizontalPodAutoscaler` — CPU + memory targets, 2–10 replicas
  - `PodDisruptionBudget` — minimum 1 available during rolling updates
  - `Ingress` with TLS and nginx annotations
  - `PersistentVolumeClaim` for SQLite data persistence
  - `ConfigMap` + `Secret` for all `RAI_*` env vars and OIDC secrets
  - `ServiceAccount` with `automountServiceAccountToken: false`
- **Multi-language SDKs**
  - **Python SDK** (`sdk/python/rai_client/`) — async `RAIClient` using `httpx`, full type hints, frozen response dataclasses for `TrustScore`, `GuardrailScan`, `HallucinationAnalysis`, `ComplianceReport`, `CostRecord`, `EvalCompareResult`
  - **TypeScript SDK** (`sdk/typescript/`) — `RAIClient` using Fetch API (Node 18+ / browser), full TypeScript types, zero runtime dependencies
  - **Go SDK** (`sdk/go/raiclient/`) — `Client` using `net/http`, context-aware, zero external dependencies
- New optional dependency group: `sso` (`PyJWT[crypto]>=2.8.0`)

### Changed
- Version bumped `0.9.0 → 1.0.0`
- `Development Status :: 4 - Beta` → `5 - Production/Stable` in PyPI classifiers
- App description updated to mention SSO, versioned stable API
- `modules` list in health endpoint updated with `sso_oidc`, `api_versioning`, `support`

**802 tests passing · 87% coverage**

---

## [0.9.0] — 2026-06-26

### Added
- **Model Evaluation Framework** (`responsibleai.eval`)
  - **`ModelComparator`** — side-by-side A/B comparison of two models on identical prompts
    - Per-prompt trust scoring via TrustScoreEngine; PII and hallucination penalties applied
    - `ComparisonResult` with per-prompt breakdown, aggregate winner, win/tie counts
    - `POST /api/eval/compare` — accepts prompt set + two response sets, persists result
  - **`BenchmarkRunner`** — runs three built-in benchmark suites against pre-collected responses
    - **TruthfulQA** (15 samples) — factual accuracy via keyword matching
    - **BBQ** (15 samples) — social bias detection across gender, race, age, religion, disability
    - **HellaSwag** (15 samples) — commonsense reasoning / sentence completion
    - `BenchmarkResult` with accuracy, bias_rate, overall_score, per-category breakdown
    - `POST /api/eval/benchmark` — runs suite, optionally sets result as baseline, checks regressions
    - `GET /api/eval/benchmark/prompts/{suite}` — returns prompt list for feeding to any model
  - **`RegressionDetector`** — tracks per-model baselines and flags score drops between runs
    - Three severity levels: `MINOR` (≥1%), `MODERATE` (≥5%), `SEVERE` (≥15%)
    - Monitors accuracy drop, bias_rate rise, and overall_score drop independently
    - `GET /api/eval/regression/{model}` — returns in-memory and DB-persisted baselines
  - **`DatasetBiasScanner`** — scans CSV/JSONL/text datasets for bias markers and PII
    - Six bias categories: gender, racial, age, religious, occupational, socioeconomic
    - PII detection via GuardrailsEngine; toxicity flagging included
    - `scan_csv()`, `scan_jsonl()`, `scan_texts()` interfaces
    - `DatasetScanResult` with flag_rate, per-category counts, flagged sample preview
    - `POST /api/eval/dataset-scan` — accepts text list, returns full scan summary
- **`EvalRepository`** (`responsibleai.db.EvalRepository`)
  - Persists comparison runs, benchmark runs, and dataset scans to `eval_runs` table
  - Persists model baselines to `eval_baselines` table with upsert semantics
  - `GET /api/eval/results` — list stored runs, filterable by type/model/org
- **Two new DB tables**: `eval_runs`, `eval_baselines`
- **50 new tests**: `tests/test_eval.py`

### Changed
- Version bumped `0.8.0 → 0.9.0`
- Dashboard description updated; `eval_compare`, `eval_benchmarks`, `eval_regression`, `dataset_scan` added to modules list

**802 tests passing · 87% coverage**

---

## [0.8.0] — 2026-06-25

### Added
- **Multi-tenant org management** (`responsibleai.rbac`, `responsibleai.db.OrgRepository`)
  - `Organization` model — id, name, slug, per-org monthly budget cap
  - `POST /api/orgs` (OWNER only), `GET /api/orgs`, `GET /api/orgs/{id}`, `DELETE /api/orgs/{id}`
  - DB table: `organizations`
- **DB-backed API keys with RBAC** (`responsibleai.db.OrgRepository`)
  - Keys stored as SHA-256 hashes — raw key shown once on creation, never stored
  - `POST /api/orgs/{id}/keys`, `GET /api/orgs/{id}/keys`, `DELETE /api/orgs/{id}/keys/{key_id}`
  - Revoked keys retained in DB for audit trail
  - `last_used_at` updated on every authenticated request
  - DB table: `org_api_keys`
- **Role-Based Access Control** (`responsibleai.rbac`)
  - Four roles: `OWNER > ADMIN > ANALYST > VIEWER`
  - `require_role(Role.X)` FastAPI dependency factory enforces minimum role on every endpoint
  - `has_permission()` hierarchical comparison helper
  - Backward compatible — flat `RAI_API_KEYS` entries treated as OWNER
- **`OrgContext`** — injected into every authenticated request via `Depends(get_org_context)`; carries `org_id`, `role`, `key_id`, `is_legacy`
- **Governance audit log** (`responsibleai.db.AuditRepository`)
  - Every API request recorded: endpoint, method, status, duration, IP, request_id, org_id, key_id
  - `GET /api/audit-log` (ADMIN+) — filterable by org, endpoint, date range; paginated
  - `endpoint_summary()` — top-N endpoints by request count with avg latency
  - `cleanup(retention_days)` — delete entries older than N days
  - DB table: `audit_log`
- **`AuditLogMiddleware`** — non-blocking async write via `asyncio.ensure_future`; skips `/static` and `/metrics`
- **ContextVar** (`_audit_ctx`) — passes org/key context from auth dependency to audit middleware without coupling
- **`/api/metrics`** now reports `audit_entries_30d`
- **`/api/health`** now reports `orgs` count
- **69 new tests**: `tests/test_rbac.py` (30) + `tests/test_org_api.py` (20) + `tests/test_audit_log.py` (19)

### Changed
- Version bumped `0.7.0 → 0.8.0`
- All endpoints use `require_role(Role.X)` instead of legacy `_require_auth`; backward-compatible
- CORS allows `PUT` and `DELETE` methods

**752 tests passing · 88% coverage**

---

## [0.7.0] — 2026-06-25

### Added
- **WebSocket live dashboard** (`/ws/dashboard`)
  - Real-time push of trust score updates, drift alerts, cost events, and guardrail blocks
  - Auth via `?token=<api-key>` query param; unauthenticated connections rejected with code 4001
  - Per-API-key tenant isolation — each client only receives its own events
  - Background heartbeat ping every 30 s with live connection count
  - Initial state snapshot sent on connect (monthly spend, registered models)
- **Streaming LLM scanner** (`responsibleai.streaming`)
  - `StreamingScanner` wraps any `AsyncIterator[str]` (OpenAI / Anthropic stream or custom generator)
  - Scans every N tokens (configurable `scan_window`, default 50) and on sentence boundaries
  - Hard-stop mode — terminates the stream immediately on PII detection
  - `StreamScanSummary` with token count, scan count, PII detections, elapsed ms
  - Async context-manager and plain async-generator interfaces
- **Enterprise webhook system** (`responsibleai.webhooks`)
  - `WebhookManager` — register, remove, list, test endpoints
  - Event types: `drift_alert`, `budget_exceeded`, `guardrail_triggered`, `trust_score_changed`
  - HMAC-SHA256 payload signing (`X-RAI-Signature-256` header)
  - Exponential backoff retry: 1 s / 5 s / 30 s (configurable `max_retries`)
  - Concurrent fan-out via `asyncio.gather`
  - Provider-specific payload formatters: Slack Block Kit, Teams Adaptive Card, PagerDuty Events API v2, generic JSON
  - In-memory delivery log (last 1 000 entries) with success/failure counters
- **Prometheus `/metrics` endpoint**
  - Metrics: `rai_trust_score`, `rai_requests_total`, `rai_cost_usd_total`, `rai_tokens_total`, `rai_guardrail_scans_total`, `rai_drift_alerts_total`, `rai_active_ws_connections`, `rai_webhook_deliveries_total`
  - Labeled by `model`, `provider`, `severity`, `result`, etc.
  - Compatible with Prometheus, Grafana, Datadog agent, VictoriaMetrics
- **Webhook CRUD API** — `POST/GET/DELETE /api/webhooks`, `GET /api/webhooks/deliveries`, `POST /api/webhooks/test/{id}`
- **`/api/health`** now reports `websocket_connections` and `webhooks_registered`
- **`/api/metrics`** now reports `websocket_connections`, `webhooks_registered`, `webhook_deliveries`, `webhook_failures`
- **46 new tests**: `tests/test_streaming.py` (17) + `tests/test_webhooks.py` (29)
- New optional deps: `websockets>=12.0`, `prometheus-client>=0.20.0`

### Changed
- Version bumped `0.6.0 → 0.7.0`
- `dashboard` dep group includes `websockets` and `prometheus-client`
- CORS allows `PUT` and `DELETE` methods (webhook management)

**683 tests passing · 88% coverage**

---

## [0.6.0] — 2026-06-20

### Added
- **Async database layer** (`responsibleai.db`)
  - `DatabaseEngine` — SQLAlchemy async engine factory; auto-selects `sqlite+aiosqlite` (default)
    or `postgresql+asyncpg` when `RAI_DATABASE_URL` is set
  - `CostRepository` — async replacement for CostTracker's DB operations; identical surface area,
    fully awaitable, connection-pooled (`pool_size=10`, `max_overflow=20`, `pool_pre_ping=True`)
  - `TrustRepository` — async replacement for TrustDriftMonitor's DB operations; drift detection,
    trend analysis, model listing
  - WAL mode + `synchronous=NORMAL` applied automatically for SQLite
- **Redis distributed rate limiting** — set `RAI_REDIS_URL=redis://host:6379/0` to switch slowapi
  from in-memory to Redis storage; falls back to in-memory when unset
- **OpenTelemetry APM** (`responsibleai.dashboard.telemetry`)
  - Traces and metrics exported via OTLP HTTP (`RAI_OTEL_ENDPOINT`)
  - FastAPI and HTTPX auto-instrumented via `opentelemetry-instrumentation-*`
  - Custom spans/metrics: `evaluate_model`, `ai.trust_score` histogram, `ai.guardrail.scans`
    counter, `ai.cost.usd` and `ai.tokens.total` counters
  - Compatible with Datadog, Grafana Tempo, Jaeger, and any OTLP collector
  - No-op fallback when `RAI_OTEL_ENDPOINT` is not set (zero overhead)
- **Dashboard upgraded to v0.6.0**
  - `/api/health` now reports `db_backend`, `rate_limit_backend`, `otel` status
  - `/api/metrics` now includes `monthly_spend_usd`, `db_backend`, `otel_enabled`
  - All DB operations in endpoints are now fully async
- **New environment variables**: `RAI_DATABASE_URL`, `RAI_REDIS_URL`, `RAI_OTEL_ENDPOINT`,
  `RAI_OTEL_SERVICE_NAME`, `RAI_OTEL_HEADERS`
- **New optional dep groups**: `postgres` (`asyncpg`), `redis` (`limits[redis]`),
  `telemetry` (full OTEL stack)
- **LLM integration tests** (`tests/test_llm_integration.py`) — 17 tests covering the full
  governance pipeline with mocked OpenAI and Anthropic API calls; no real keys required
- **Async DB tests** (`tests/test_async_db.py`) — 29 tests for `CostRepository` and
  `TrustRepository` using SQLite+aiosqlite; PostgreSQL path skipped when asyncpg absent

### Changed
- Version bumped `0.5.0 → 0.6.0`
- Dashboard endpoints fully migrated from sync CostTracker/TrustDriftMonitor to async repositories
- `pyproject.toml`: new optional groups, `all` updated to include `postgres`, `redis`, `telemetry`

### Fixed
- `app.py`: replaced deprecated `@app.on_event` with modern `asynccontextmanager` lifespan pattern

---

## [0.5.0] — 2025-06-20

### Added
- **Production-grade Governance Dashboard** (`responsibleai.dashboard`)
  - API key authentication (Bearer token, configurable via `RAI_API_KEYS`)
  - Per-endpoint rate limiting via `slowapi` (configurable per env var)
  - Structured JSON request logging with `structlog` and request IDs
  - Security response headers (`X-Content-Type-Options`, `X-Frame-Options`, etc.)
  - Global exception handlers — no raw stack traces leaked to clients
  - Pydantic-Settings config (`RAI_*` env vars, `.env` file support)
  - `/api/metrics` endpoint — uptime, request count, error rate, config status
  - Improved `/api/health` with database connectivity check
  - Input validation with strict size caps on all request fields
  - Graceful startup/shutdown lifecycle (closes SQLite connections cleanly)
- **Persistent storage by default** — DB path `~/.responsibleai/data.db`; `:memory:` for tests
- **CI/CD pipeline** (`.github/workflows/`)
  - `ci.yml` — lint (ruff), type-check (mypy), pytest with 80% coverage gate, build check
  - `publish.yml` — PyPI trusted publisher, triggers on `git tag v*`
- **Docker** — multi-stage `Dockerfile`, `docker-compose.yml` with persistent volume
- **`.env.example`** — full environment variable reference
- **`DEPLOYMENT.md`** — Docker, bare-metal, nginx reverse proxy, auth, backup instructions
- **`SLA.md`** — uptime tiers, response time targets, incident classification, data retention
- **`CHANGELOG.md`** — this file

### Changed
- Version bumped `0.4.0 → 0.5.0`
- `pyproject.toml`: added `dashboard` optional dep group, updated classifiers, added Changelog URL
- CI workflow updated to cover `src/responsibleai` with 80% minimum coverage gate
- Dashboard `app.py` fully rewritten with auth, middleware, rate limiting, validation, lifecycle hooks

### Fixed
- `drift/monitor.py`: removed stray `@dataclass_like = None` syntax error

---

## [0.4.0] — 2025-06-19

### Added
- **Cost Intelligence module** (`responsibleai.cost`)
  - `CostTracker` — SQLite-backed token usage, budget enforcement, team/model breakdown
  - `CostAnalyzer` — prompt bloat detection, model overkill detection, verbose response detection
  - `ModelRouter` — routes tasks to cheapest acceptable model by complexity tier
  - `MODEL_CATALOG` — 16 models with real 2025 pricing (OpenAI, Anthropic, Google, Mistral, Cohere, Ollama)
- **Trust Drift Monitor** (`responsibleai.drift`)
  - `TrustDriftMonitor` — SQLite-backed trust score history, drift alerts with severity levels
  - `trend()` — 7-day and 30-day moving averages, direction detection
- **Governance Dashboard** — FastAPI backend + dark-mode SPA (Chart.js + Tailwind)
- **Examples** — 7 self-contained scripts covering all platform modules, no API keys required
- 74 new tests; full suite 559 passing at 85% coverage

---

## [0.3.0] — 2025-06-18 (pre-open-source)

### Added
- **TrustScoreEngine** — 6-dimension composite score (0–100, A–F grade, risk level)
- **AIPassport** — SHA-256 verifiable trust certificate, JSON + HTML export
- **GuardrailsEngine** — PII detection (6 types), toxicity filtering, in-place redaction
- **HallucinationDetector** — TF-IDF self-consistency + hedging density
- **ComplianceEngine** — NIST AI RMF (14 controls), ISO 42001 (8 controls), EU AI Act tier classification
- **RedTeamSimulator** — 10 adversarial attack vectors, CWE IDs, safe-refusal detection
- 485 tests, 88% coverage on `responsibleai` package

---

## [0.2.0] — 2025-06-15 (pre-open-source)

### Added
- `PrivacyLabel` — federated data labeling with differential privacy
  - `FederatedClient` with `epsilon_per_round` / `total_epsilon` budget tracking
  - 4 DP mechanisms: Laplace, Gaussian, Exponential, DP-SGD
  - `FedAvgAggregator` with Weiszfeld geometric median
- `DeepfakeDetector` — MEAN/MAX/WEIGHTED/MAJORITY ensemble voting
- Cultural bias probe and intersectional co-failure analysis

---

## [0.1.0] — 2025-06-10 (pre-open-source)

### Added
- `BiasBuster` — 6 demographic bias probes (gender, racial, age, religious, occupational, cultural)
- TF-IDF cosine divergence + VADER sentiment scoring
- Bootstrap confidence intervals for divergence estimates
