# WhitePact Security Assurance Case

Last reviewed: 2026-08-19 · Platform version: 1.2.2 · Author: solo maintainer (self-review, not independent — see "How to read this document")

This document exists to satisfy the OpenSSF Best Practices Silver
`assurance_case` criterion, which requires four things: a threat model,
clear trust boundaries, an argument that secure-design principles are
applied, and an argument that common implementation-level security
weaknesses are countered. It is written for an enterprise security
engineer evaluating WhitePact, not for the OpenSSF BadgeApp checkbox —
every claim below points at a real file, a real test, or a real CI
check, and every limitation is stated as a limitation, not smoothed
over.

## How to read this document

This is a synthesis and a structured re-index of evidence that already
exists across several other documents in this repository, cross-checked
against the current source as of the commit this file was written
against — it does not replace them, and where it summarizes, the
underlying document is the more detailed source:

- [`THREAT_MODEL.md`](THREAT_MODEL.md) — STRIDE analysis of the real
  attack surface, organized by subsystem (MCP transports, OIDC,
  governance pipeline, dashboard API, database, Kubernetes). Section 2
  below restructures a subset of that same material into the specific
  ASSET/ATTACKER/ATTACK/TRUST BOUNDARY/CONTROL/TEST/RESIDUAL RISK shape
  OpenSSF's criterion asks for, and adds threats `THREAT_MODEL.md`
  doesn't separately break out (Execution Permit mutation/replay,
  delegation escalation, weak cryptographic keys, release-artifact
  substitution).
- [`ENTERPRISE_SECURITY.md`](ENTERPRISE_SECURITY.md) — the
  procurement-facing answer to "what can I expect / what can't I
  assume": encryption at rest, data residency, audit-trail integrity,
  SSO, RBAC, multi-tenancy.
- [`compliance/INTERNAL_SECURITY_REVIEW.md`](compliance/INTERNAL_SECURITY_REVIEW.md)
  — the most recent Bandit/pip-audit/manual-review pass, including two
  real vulnerabilities found and fixed (a SQL-injection-shaped pattern
  in `CostTracker`, and an SSRF hole in webhook delivery) with
  regression tests.
- [`compliance/KEY_MANAGEMENT.md`](compliance/KEY_MANAGEMENT.md) —
  custody and rotation procedure for the one application-managed
  encryption key.
- [`SECURITY.md`](SECURITY.md) — vulnerability disclosure process and
  scope.

**This is a self-review, explicitly not independent oversight.** The
same person who wrote the code wrote this document and the internal
security review it draws on. Where that matters for a specific claim,
it's called out in that claim's own row. See "Known Limitations"
(Section 8) for the full, unhidden list — no independent penetration
test, no SOC 2, no ISO 27001.

---

## 1. Security Claims

Every claim below is defended somewhere in Sections 2–7 with a pointer
to real source and, where one exists, a real test. Nothing here is
claimed on the strength of documentation alone.

| # | Claim | Primary evidence |
|---|---|---|
| C1 | Authenticated dashboard/API operations require a valid identity (static API key, OIDC bearer token, or SAML session token) — no endpoint that mutates state is reachable unauthenticated when `auth_enabled` is true. | `dashboard/middleware.py::build_api_key_dependency`, `dashboard/app.py::get_org_context`, `auth/oidc.py`, `auth/saml.py` |
| C2 | RBAC restricts operations by role (`OWNER > ADMIN > ANALYST > VIEWER`), enforced per-endpoint via `require_role(...)`, not left to caller discretion. | `ENTERPRISE_SECURITY.md` "RBAC"; `dashboard/app.py::require_role` |
| C3 | Tenant-scoped data is isolated by organization — every governance-data repository method filters by `org_id`. | `ENTERPRISE_SECURITY.md` "Multi-tenancy isolation"; `tests/test_tenant_isolation.py` |
| C4 | Agent actions dispatched through this platform's own MCP tool set are subjected to runtime authority enforcement before execution, not after. | `governance/gateway.py::WhitePactRuntimeGateway.evaluate()`, `governance/execution.py::InternalToolExecutor` |
| C5 | Authority cannot legitimately expand through delegation — a delegated grant can never exceed what the delegating identity currently, actively holds. | `governance/models.py::validate_attenuation`, `db/delegation_repository.py::DelegationRepository.grant` (raises `DelegationEscalationError`) |
| C6 | Execution Permit (`ExecutionAuthorization`) and approval mechanisms bind an authorization to one specific, byte-identical action, single-use, where currently implemented. | `governance/execution.py`, `governance/approval.py::compute_action_digest`/`matches_action` |
| C7 | Untrusted external destinations (webhook targets, upstream MCP servers) are validated against private/internal address ranges before WhitePact makes an outbound call to them. | `webhooks/manager.py::validate_webhook_url`, `governance/upstream_executor.py` |
| C8 | API credentials are not stored in recoverable plaintext. | `ENTERPRISE_SECURITY.md` "Encryption at rest"; `db/org_repository.py` (SHA-256 hash only) |
| C9 | Weak cryptographic keys/secrets are rejected where WhitePact validates them (JWKS RSA keys, webhook HMAC secrets). | `auth/crypto_policy.py`; `tests/test_crypto_policy.py` |
| C10 | Release artifacts (wheel + sdist) carry cryptographic build provenance. | `.github/workflows/publish.yml::actions/attest-build-provenance` |
| C11 | The audit-log and governance-evidence hash chains provide their documented tamper-evidence — detection of a partial edit/delete, not defense against a full-chain-recompute attacker with DB write access. | `ENTERPRISE_SECURITY.md` "Audit trail integrity"; `db/evidence_repository.py` |
| C12 | Security-sensitive ambiguity fails safely (closed) where currently implemented — an evidence-write failure blocks the action rather than letting it proceed unlogged. | `THREAT_MODEL.md` §3 ("Evidence-write ... failure ... fail closed"); `tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed` |

Claims **not** made, because source/tests don't support them: WhitePact
does not claim independent third-party review of any of the above (see
Section 8), does not claim its evidence hash chain resists an attacker
with full database write access recomputing the chain from scratch,
does not claim governance enforcement is unbypassable for a caller with
direct Python library access, and does not claim signed Git release
tags exist yet (tracked separately — see
`compliance/SIGNED_VERSION_TAGS.md`).

---

## 2. Threat Model

Each threat below follows OpenSSF's requested shape. "Residual risk" is
never omitted — a threat with no residual risk stated is a threat this
document hasn't thought hard enough about, not one that's fully solved.

### 2.1 Stolen API credentials

- **Asset**: any org-scoped API key holder's access (governance data,
  billing, org management up to the key's role).
- **Attacker**: anyone who obtains a valid raw key (phishing, leaked
  `.env`, departed employee).
- **Attack**: presents the stolen key as `Authorization: Bearer <key>`.
- **Trust boundary**: Internet → WhitePact API (authentication).
- **Control**: keys are opaque, high-entropy (`secrets.token_urlsafe(32)`,
  256 bits) and stored only as a SHA-256 hash — a database compromise
  alone does not yield usable keys. An org can force SSO and
  simultaneously invalidate all its static keys (`PUT
  /api/orgs/{id}/sso {"sso_required": true}`).
- **Test/evidence**: `db/org_repository.py::_generate_raw_key`;
  `ENTERPRISE_SECURITY.md` "SSO / authentication".
- **Residual risk**: a key is valid indefinitely until revoked or SSO
  is enforced — there is no automatic expiry, and an org that never
  enables `sso_required` keeps static keys valid forever by design
  (`THREAT_MODEL.md` §2).

### 2.2 Malicious authenticated user

- **Asset**: any operation gated by role.
- **Attacker**: a legitimately authenticated but lower-privileged or
  malicious org member.
- **Attack**: calls an endpoint above their role (e.g. a VIEWER trying
  to create an API key).
- **Trust boundary**: authentication → RBAC.
- **Control**: `require_role(min_role)` on every endpoint; strict
  hierarchy `OWNER > ADMIN > ANALYST > VIEWER`.
- **Test/evidence**: `ENTERPRISE_SECURITY.md` "RBAC"; endpoint-level
  role assertions across `tests/test_dashboard_api.py`.
- **Residual risk**: no automated static check enforces that every new
  endpoint actually declares a `require_role` — relies on reviewer
  discipline (same gap `THREAT_MODEL.md` §4 states for `org_id`
  filtering).

### 2.3 Privilege escalation

- **Asset**: authority beyond what an identity should hold.
- **Attacker**: an authenticated identity (human or agent) attempting
  to acquire authority its role/delegation doesn't grant.
- **Attack**: (a) role-hierarchy bypass — covered by 2.2; (b)
  authority-model bypass via delegation — covered by 2.10; (c)
  authority-ceiling bypass.
- **Trust boundary**: RBAC / Machine Authority.
- **Control**: `OrgAuthorityCeiling` is a structural envelope every
  per-call `AuthorityContext` is checked against via
  `validate_attenuation()` — an admin sets "no key under this org may
  ever authorize a payment above $X" once, not per-key.
- **Test/evidence**: `governance/ceiling.py`; `tests/test_authority_constraints.py`.
- **Residual risk**: the ceiling is opt-in per org (default:
  unrestricted, matching pre-feature behavior) — an org that never
  configures one gets no ceiling enforcement.

### 2.4 Cross-tenant access

- **Asset**: another organization's governance/cost/audit/webhook data.
- **Attacker**: an authenticated user of org A attempting to read/write
  org B's data.
- **Attack**: a request that omits or forges an `org_id`, or a
  repository method missing an `org_id` filter.
- **Trust boundary**: RBAC → tenant isolation.
- **Control**: every governance-data table carries `org_id`; every
  repository method filters by it; org-scoped keys can only act within
  their own org (only legacy flat super-admin keys cross orgs, and that
  crossing is itself audit-logged).
- **Test/evidence**: `tests/test_tenant_isolation.py`;
  `ENTERPRISE_SECURITY.md` "Multi-tenancy isolation".
- **Residual risk**: enforced by convention across every repository
  method, not by a single choke point or automated static check — a
  new repository method that forgets the filter is a real class of bug
  this architecture doesn't structurally prevent, only makes easy to
  spot in review (`THREAT_MODEL.md` §4). **Found-and-fixed instance**:
  Phase 23 discovered `AuditLogMiddleware` was recording `org_id: null`
  on every entry due to a Starlette `ContextVar`/task-boundary bug —
  fixed and regression-tested, cited here as evidence this class of bug
  is real, not hypothetical.

### 2.5 SQL injection

- **Asset**: database integrity/confidentiality.
- **Attacker**: any caller who can influence a value that reaches a SQL
  query.
- **Attack**: string-interpolated attacker-controlled input in query
  text.
- **Trust boundary**: application → PostgreSQL/SQLite.
- **Control**: SQLAlchemy Core/ORM parameterized queries throughout;
  no raw string-interpolated SQL in the governance, evidence, or
  approval repositories.
- **Test/evidence**: `compliance/INTERNAL_SECURITY_REVIEW.md` §2.1 —
  a real f-string-interpolation pattern was found in
  `cost/tracker.py` (library-only surface, not the API path) and fixed
  with regression tests; `bandit -r src/` (B608) as an ongoing check.
- **Residual risk**: no dedicated SQL-injection fuzz-test suite exists
  — coverage today is code review plus Bandit's static pattern
  matching, not adversarial fuzzing (`THREAT_MODEL.md` §5).

### 2.6 SSRF

- **Asset**: internal network reachability from WhitePact's own
  server-side HTTP client.
- **Attacker**: an ADMIN-role user registering a malicious webhook URL,
  or the MCP upstream-registry feature pointed at an internal host.
- **Attack**: register a target resolving to `169.254.169.254`
  (cloud metadata), an RFC 1918 address, or `localhost`.
- **Trust boundary**: WhitePact ↔ webhook target / WhitePact ↔ upstream
  MCP server.
- **Control**: `validate_webhook_url()` resolves the hostname and
  rejects private/loopback/link-local/reserved/multicast/unspecified
  addresses, checked both at registration and at every delivery (DNS
  can resolve differently between the two — DNS-rebinding-aware);
  `follow_redirects=False` blocks redirect-based bypass. The upstream
  MCP proxy executor applies the equivalent guard before calling out to
  a registered upstream server.
- **Test/evidence**: `compliance/INTERNAL_SECURITY_REVIEW.md` §2.2
  (found and fixed as a real vulnerability, not designed-in from the
  start); `tests/test_webhooks.py::TestSSRFGuard` (7 tests: scheme
  rejection, no-host, loopback, RFC 1918, cloud-metadata address,
  allowed public IP, unresolvable host); `governance/upstream_executor.py`.
- **Residual risk**: does not prevent an admin from pointing a webhook
  at a public internet service they don't control — inherent to the
  feature (webhooks exist to call external URLs), not a vulnerability.

### 2.7 Malicious webhook target

- Same asset/attacker/attack/trust-boundary/control/test as 2.6 —
  covered by the same `validate_webhook_url()` guard, plus HMAC-SHA256
  payload signing (`X-RAI-Signature-256`) so a receiving endpoint can
  verify the payload actually came from WhitePact.
- **Residual risk**: signing secret is optional (empty secret = no
  signature, an explicit deployer choice) — `crypto_policy.py` rejects
  a *present-but-weak* secret, not the absence of one.

### 2.8 Malicious or compromised MCP server

- **Asset**: integrity of tool calls proxied to an external, registered
  upstream MCP server.
- **Attacker**: an upstream MCP server operator, or an attacker who has
  compromised one.
- **Attack**: a registered upstream server returns malicious tool
  results, or the registration itself points at an SSRF target.
- **Trust boundary**: WhitePact ↔ upstream MCP server.
- **Control**: SSRF-guarded proxy executor (registration + call-time
  target validation, same pattern as 2.6); a supply-chain trust/scanner
  exists to evaluate a candidate MCP server before it's trusted
  (`mcp/resources.py`/scanner tooling from the supply-chain security
  work).
- **Test/evidence**: `governance/upstream_executor.py`,
  `governance/upstream_discovery.py`.
- **Residual risk**: WhitePact validates the *destination* (not an
  internal target) and structurally binds *this platform's own* tool
  dispatch to a decision (Execution Permit), but cannot validate the
  *correctness* of an upstream server's tool results — an upstream
  server that is malicious but not pointed at a private address is a
  content-trust problem this layer doesn't solve.

### 2.9 Prompt-manipulated autonomous agent

- **Asset**: the integrity of a governance decision.
- **Attacker**: a prompt-injection payload embedded in tool-call
  arguments or (specifically) in content later replayed into an agent's
  persistent memory.
- **Attack**: crafted argument content designed to make the risk
  classifier or policy engine misclassify a dangerous action as safe,
  or a poisoned memory write later "instructing" a future session.
- **Trust boundary**: model reasoning ↔ deterministic governance layer.
- **Control**: risk tiering (`governance/risk.py::TOOL_RISK_TIERS`) is
  a hardcoded table keyed by tool *name*, never inferred from argument
  content — content-based evasion cannot change a tool's risk tier.
  `Policy` evaluation is explicit first-match-wins, not model-inferred.
  Memory Firewall (`governance/memory_firewall.py`) is a deterministic
  regex scan for injection-shaped patterns (fake role markers,
  instruction overrides) specifically aimed at content before it's
  persisted to or read back from agent memory.
- **Test/evidence**: `tests/test_governance_risk.py` (drift-tests the
  static tier table against live tool definitions, so a new tool can't
  ship unclassified); `governance/memory_firewall.py` module docstring
  for exact scope.
- **Residual risk**: Memory Firewall is pattern-matching, not a general
  jailbreak/prompt-injection detector — deliberately narrow to
  memory-persistence patterns, stated as a scope limit, not a general
  claim of injection immunity. No LLM call is made to "understand"
  intent anywhere in the security-critical path — this is deliberate
  (deterministic controls preferred), but it also means a sufficiently
  novel injection pattern that doesn't match the fixed regex set is not
  caught.

### 2.10 Delegation escalation

- **Asset**: authority integrity across a delegation chain.
- **Attacker**: an identity holding delegated authority attempting to
  grant a *broader* authority than it holds to another identity.
- **Attack**: `grant()` called with `granted_action_types`/`constraints`
  that exceed the parent delegation.
- **Trust boundary**: Machine Authority / Governance Runtime.
- **Control**: `validate_attenuation()` is checked at grant time against
  the delegator's currently *active* delegation (re-checked fresh, not
  just at the parent's own grant time) — `DelegationRepository.grant()`
  raises `DelegationEscalationError` rather than silently creating an
  invalid grant.
- **Test/evidence**: `governance/delegation.py`,
  `db/delegation_repository.py`; `tests/test_delegation_chains.py`,
  `tests/test_delegation_graph.py`.
- **Residual risk**: root grants (`from_identity_id=None`, i.e. from a
  human/org owner) skip the attenuation check by design — there is no
  parent to compare against, so an org's authority ceiling (2.3) is the
  actual root-level constraint, not the delegation graph itself.

### 2.11 Workflow/sequence abuse

- **Asset**: authority-composition integrity — a sequence of
  individually-permitted actions that's dangerous only in combination.
- **Attacker**: an agent chaining permitted actions (e.g.
  `beneficiary.create` → `payment.limit.raise` → `payment.execute`)
  each individually authorized.
- **Attack**: executes the sequence within a short window to achieve an
  outcome no single step would have been allowed to reach directly.
- **Trust boundary**: Machine Authority / Governance Runtime.
- **Control**: `WorkflowSequenceRule` — a fixed, ordered `action_types`
  sequence per rule, matched as a subsequence within a time window,
  deterministic (no LLM inference).
- **Test/evidence**: `governance/workflow.py`.
- **Residual risk**: rules are hand-authored per known-dangerous
  sequences, not learned or exhaustively enumerated — a novel dangerous
  combination not yet encoded as a rule is not caught.

### 2.12 Approval replay

- **Asset**: an already-consumed `REQUIRE_APPROVAL` decision.
- **Attacker**: a caller attempting to execute an approved action twice
  from a single approval.
- **Attack**: presents the same resolved `ApprovalRequest` for
  execution more than once.
- **Trust boundary**: approval workflow → execution.
- **Control**: `ApprovalStatus.CONSUMED` is a one-way transition entered
  only via `ApprovalRepository.consume()`; a `WHERE status='PENDING'`
  (resolution) / consumed-state SQL guard prevents a second consumption.
- **Test/evidence**: `governance/approval.py`;
  `tests/test_approval_execution_binding.py`.
- **Residual risk**: none identified beyond standard DB-transaction
  race coverage, already tested under concurrent resolution
  (`tests/test_governance_approval.py`, cited in `THREAT_MODEL.md` §3).

### 2.13 Approval mutation

- **Asset**: the binding between what a human reviewed and what
  actually executes.
- **Attacker**: a caller attempting to execute a *different* action
  (e.g. a larger payment amount) than the one a human approved, using a
  since-approved `ApprovalRequest`.
- **Attack**: modify `target`/`arguments` between approval and
  execution, then present the approval ID.
- **Trust boundary**: approval workflow → execution.
- **Control**: `compute_action_digest()` — a SHA-256 digest over
  `action_type` + `target` + `arguments` — is computed at approval-
  request build time and compared byte-for-byte at consumption via
  `matches_action()`. A legacy approval with no digest
  (`action_digest == ""`) matches nothing, fail-closed rather than
  skipping the check.
- **Test/evidence**: `governance/approval.py::compute_action_digest`;
  `tests/test_approval_execution_binding.py`.
- **Residual risk**: none identified for the digest mechanism itself;
  the digest is not a secrecy boundary (only the digest, never the
  canonical JSON, is persisted) — stated explicitly in the module's own
  docstring so it isn't mistaken for one.

### 2.14 Execution Permit mutation

- **Asset**: the binding between a governance *decision* and the
  action that actually executes.
- **Attacker**: a caller attempting to execute an action different from
  the one `WhitePactRuntimeGateway.evaluate()` actually authorized.
- **Attack**: present an `ExecutionAuthorization` alongside a mutated
  `ActionRequest`.
- **Trust boundary**: governance decision → `InternalToolExecutor`.
- **Control**: `ExecutionAuthorization.matches_action()` compares the
  authorization's `action_digest` (via the same `compute_action_digest`
  used for approvals) against the action presented at execution time;
  mismatch raises `AuthorizationActionMismatchError`.
- **Test/evidence**: `governance/execution.py::_validate_authorization`;
  `tests/test_executor_bypass_invariant.py` (proves the executor
  refuses a mismatched action, wrong org, expired authorization, and
  replay in isolation).
- **Residual risk**: `ExecutionAuthorization` is a structural binding
  (digest + org + expiry + single-use flag), *not* cryptographically
  signed — an explicit, documented design decision, correct as long as
  the object never crosses a process/trust boundary (it's constructed
  and consumed within the same async call stack today). If a future
  out-of-process executor (`MCPExecutor`/`HTTPExecutor`, not built yet)
  is added, this becomes load-bearing and the module's own docstring
  says so.

### 2.15 Execution Permit replay

- **Asset**: single-use guarantee of an execution authorization.
- **Attacker**: a caller attempting to consume the same
  `ExecutionAuthorization` twice.
- **Attack**: call `InternalToolExecutor.execute()` a second time with
  the same authorization.
- **Trust boundary**: governance decision → `InternalToolExecutor`.
- **Control**: `authorization.consumed` is set `True` after the first
  successful validation; a second call hits
  `AuthorizationAlreadyConsumedError`.
- **Test/evidence**: `governance/execution.py`;
  `tests/test_executor_bypass_invariant.py`.
- **Residual risk**: `DEFAULT_AUTHORIZATION_TTL_SECONDS = 30` bounds the
  replay window even before consumption is checked — short by design;
  no residual gap identified for the single-process case this covers.

### 2.16 Revoked authority reuse

- **Asset**: the guarantee that a revoked/expired delegation cannot
  still authorize an action.
- **Attacker**: an identity whose delegation was revoked or has expired,
  attempting to act on authority it no longer holds.
- **Attack**: present a request as an identity with a since-revoked
  delegation.
- **Trust boundary**: Machine Authority / Governance Runtime.
- **Control**: **continuous re-authorization** — every dispatched call
  fetches the *latest* delegation state fresh (`get_latest_delegation()`,
  not a cached/session-scoped grant) and `DelegationRecord.is_active()`
  checks both `revoked_at` and `expires_at` against the current time on
  every call, not just at grant time.
- **Test/evidence**: `governance/delegation.py::DelegationRecord.is_active`;
  `db/delegation_repository.py` module docstring ("Continuous
  re-authorization's real source"); `tests/test_delegation_graph.py`.
- **Residual risk**: revocation is not push-propagated to any
  in-flight, already-authorized `ExecutionAuthorization` (2.14/2.15) —
  those are short-lived (30s TTL) and single-use by construction, which
  is why this isn't treated as a separate gap, but it's worth stating
  explicitly rather than assuming revocation is instantaneous at every
  layer.

### 2.17 Weak cryptographic keys

- **Asset**: the integrity of any signature/verification WhitePact
  relies on.
- **Attacker**: a misconfigured or compromised counterparty serving a
  deliberately weak key (e.g. a 512-bit RSA key from a compromised JWKS
  endpoint, or a human typing `"secret123"` as a webhook signing
  secret).
- **Attack**: rely on WhitePact accepting a weak key to make subsequent
  forgery/brute-force tractable.
- **Trust boundary**: WhitePact ↔ OIDC provider (JWKS) / webhook
  configuration.
- **Control**: `crypto_policy.py` enforces a 2048-bit floor for any RSA
  key fetched from a configured OIDC provider's JWKS endpoint (NIST SP
  800-57 Part 1) and a 32-character floor for a *present* webhook HMAC
  secret (an *absent* secret is a legitimate "unsigned" choice, not
  covered by this floor). WhitePact's own generated secrets (API keys,
  TOTP seeds, Fernet keys) are correct by construction (CSPRNG at fixed
  adequate length) and don't need runtime policy checks.
- **Test/evidence**: `auth/crypto_policy.py`;
  `tests/test_crypto_policy.py`.
- **Residual risk**: this is a floor on what WhitePact *trusts*, not a
  claim about every key in the system — it doesn't (and can't) enforce
  key strength on a customer's own OIDC provider's internal signing
  practices beyond the public key it publishes.

### 2.18 OIDC/JWKS manipulation

- **Asset**: the integrity of bearer-token authentication.
- **Attacker**: a party able to influence what a configured OIDC
  provider's JWKS endpoint serves (compromise, misconfiguration, or a
  malicious provider).
- **Attack**: (a) serve a private key where a public key is expected
  (classic JWK-confusion attack shape); (b) serve a weak key (2.17);
  (c) sign with `alg: none` or an unexpected algorithm; (d) a token with
  the wrong audience/issuer.
- **Trust boundary**: WhitePact ↔ OIDC provider.
- **Control**: `pyjwt.algorithms.RSAAlgorithm.from_jwk(jwk)`'s result is
  explicitly type-checked as `RSAPublicKey` before use — a JWKS
  endpoint serving a private key is rejected, not silently accepted.
  `pyjwt.decode()` is called with an explicit `algorithms=[...]`
  allowlist (`RS256/RS384/RS512/ES256/ES384/ES512` — never `none` or
  HMAC-family, which would let a holder of the *public* key forge a
  token), and explicit `audience=`/`issuer=` checks.
- **Test/evidence**: `auth/oidc.py::OIDCProvider.validate_token`;
  `tests/test_oidc.py`.
- **Residual risk**: a malicious *customer-configured* OIDC provider
  returning forged-but-correctly-signed claims is out of scope by
  design — the customer's own IdP choice is a trust boundary WhitePact
  cannot additionally defend against (`THREAT_MODEL.md` §2).

### 2.19 Secret disclosure

- **Asset**: `RAI_FIELD_ENCRYPTION_KEY`, OIDC/webhook/Stripe secrets,
  raw API keys.
- **Attacker**: anyone with access to logs, error output, git history,
  or the repository.
- **Attack**: secret leaked via a log line, an error message, a commit,
  or a Docker image layer.
- **Trust boundary**: Deployment ↔ secrets manager/environment;
  Developer ↔ GitHub.
- **Control**: raw API keys are never stored (2.8, hash-only); the
  encryption key's error path deliberately never echoes the key value;
  `compliance/KEY_MANAGEMENT.md` documents explicit anti-patterns (never
  in git, never in a `Dockerfile ENV`, never logged) and a custody
  preference order (secrets manager > VPS secret feature >
  `chmod 600` file). Gitleaks scans every PR diff plus a weekly
  full-history scan.
- **Test/evidence**: `.github/workflows/gitleaks.yml`;
  `db/encryption.py` error-path behavior; `compliance/KEY_MANAGEMENT.md`.
- **Residual risk**: Gitleaks scanning is pattern-based — a secret that
  doesn't match a known pattern (a bespoke internal token format, for
  instance) could slip past it; this is a general limitation of
  automated secret scanning, not specific to this project's
  configuration.

### 2.20 Dependency compromise

- **Asset**: the integrity of the dependency closure shipped in every
  release.
- **Attacker**: a compromised upstream package (typosquatting, account
  takeover of a maintainer, a malicious transitive dependency).
- **Attack**: a vulnerable or malicious package version is pulled in by
  a routine dependency bump.
- **Trust boundary**: WhitePact ↔ PyPI (dependencies).
- **Control**: `pip-audit` runs in CI on every push (`ci.yml`) and
  weekly (`security-scan.yml`) against the installed environment;
  `dependency-review.yml` reviews what a *pull request proposes to
  change* (new deps, version bumps, licenses) before merge, not just
  after; an SBOM (CycloneDX) is generated from the actual built
  artifact's installed dependency closure on every release.
- **Test/evidence**: `.github/workflows/{ci,security-scan,dependency-review}.yml`;
  `compliance/INTERNAL_SECURITY_REVIEW.md` §2.4 (documents the one
  currently-flagged package, `nltk`, and why it's correctly scoped as
  an opt-in extra rather than a mandatory dependency).
- **Residual risk**: `pip-audit`/dependency-review catch *known*
  vulnerabilities against public advisory databases — a zero-day or an
  advisory-database gap is not caught by either. No reproducible-build
  verification exists to detect a compromised PyPI upload that doesn't
  match the reviewed source (see 2.21).

### 2.21 Release artifact substitution

- **Asset**: the integrity of the wheel/sdist a user actually installs.
- **Attacker**: anyone able to intercept or substitute the published
  artifact between build and consumption.
- **Attack**: publish a tampered wheel under the same version number,
  or intercept the PyPI upload.
- **Trust boundary**: GitHub Actions ↔ PyPI; Deployment ↔ PyPI.
- **Control**: `actions/attest-build-provenance` produces a
  Sigstore-backed, GitHub-attested provenance statement for the built
  wheel + sdist, verifiable with `gh attestation verify <file> --owner
  Guruprasath-Annadurai` — a consumer can confirm the artifact was
  built by this repository's own workflow, from this exact commit, not
  substituted in between. Publishing uses PyPI Trusted Publishing (OIDC),
  so no long-lived API token exists to be stolen and used to publish a
  substitute release independently of the workflow.
- **Test/evidence**: `.github/workflows/publish.yml`.
- **Residual risk**: as of v1.2.3 (2026-08-19), the Git version tag
  itself **is** cryptographically signed and CI-verified before
  build/publish — see `compliance/SIGNED_VERSION_TAGS.md`. The residual
  gap is narrower now: every release *before* v1.2.3 (9 tags) predates
  this control and was never signed, and is not retroactively signed
  (rewriting a published tag would break reproducibility for anyone who
  already fetched it). Artifact attestation and tag signing remain two
  separate controls — proving "this artifact came from this workflow
  run against this commit" is not the same claim as "a trusted human
  authorized cutting this release" — both are now real for every
  release from v1.2.3 onward.

### 2.22 Direct governance bypass

- **Asset**: the guarantee that a tool call was actually evaluated by
  the governance pipeline.
- **Attacker**: a caller with direct code-level access to this
  package's internals.
- **Attack**: import `responsibleai` as a library and call an
  underlying engine (e.g. `GuardrailsEngine`, or `mcp.tools.dispatch_tool`
  directly) without going through `WhitePactRuntimeGateway.evaluate()`
  or `InternalToolExecutor`.
- **Trust boundary**: MCP transport / governed dispatch path.
- **Control**: for the one path this platform *itself* controls — its
  own 27 MCP tools dispatched via the hosted MCP transport —
  `mcp/server.py::_call_tool()` no longer calls `dispatch_tool()`
  directly for a governed request; it goes through
  `InternalToolExecutor.execute()`, which structurally cannot run
  without a matching `ExecutionAuthorization` (2.14/2.15).
- **Test/evidence**: `tests/test_executor_bypass_invariant.py`,
  `tests/test_mcp_governance_dispatch.py` (proves the live end-to-end
  dispatch path routes through the executor, not around it).
- **Residual risk**: **stated honestly, not hidden**: this closes the
  bypass for the one dispatch path this platform owns. A caller with
  direct Python code-level access to the library (embedding it as an
  SDK) can still call underlying engines directly — the governance
  gateway is a *chosen* integration point for such a caller, not an
  unbypassable one. `THREAT_MODEL.md` §3 states this identically. Also:
  `mcp_governance_enabled` defaults to `False` for the hosted transport
  — an operator who never enables it gets zero dispatch-path
  enforcement, same as before this wiring existed.

### 2.23 Database tampering

- **Asset**: the integrity of governance decisions and audit records
  once written.
- **Attacker**: anyone with direct database write access (compromised
  credentials, insider, or an attacker who has otherwise breached the
  DB layer).
- **Attack**: directly edit or delete a `governance_evidence` or
  `audit_log` row to hide a DENY/QUARANTINE decision or falsify
  history.
- **Trust boundary**: WhitePact ↔ PostgreSQL.
- **Control**: hash chain — `entry_hash = sha256(prev_hash + fields)` —
  on both `audit_log` and `governance_evidence`. `GET
  /api/audit/verify` (super-admin only) and `verify_chain()` recompute
  the chain and report the first broken link.
- **Test/evidence**: `ENTERPRISE_SECURITY.md` "Audit trail integrity";
  `db/evidence_repository.py`.
- **Residual risk**: **stated identically in `ENTERPRISE_SECURITY.md`
  and repeated here because it matters**: this does not detect an
  attacker with full database write access who recomputes the entire
  chain from scratch — no hash chain without external anchoring (e.g.
  periodic publication to write-once storage) can defend against that,
  and no such anchoring exists yet. The chain is also process-local,
  not a single global chain across a multi-replica deployment.

### 2.24 Denial-of-service / resource exhaustion

- **Asset**: service availability.
- **Attacker**: any caller, authenticated or not (depending on
  endpoint), sending high request volume or holding connections open.
- **Attack**: (a) API request flooding; (b) rotating API keys to evade
  a per-key rate limit; (c) holding a legacy SSE connection open
  indefinitely.
- **Trust boundary**: Internet → WhitePact API / MCP transport.
- **Control**: per-Bearer-token (SHA-256-keyed) rate limiting via
  `slowapi` on rate-sensitive endpoints (MFA login attempts capped at
  10/minute, bounding brute-force of a 6-digit TOTP within its 30s
  validity window).
- **Test/evidence**: `dashboard/app.py` (`@limiter.limit(...)`
  decorators); `THREAT_MODEL.md` §1, §4.
- **Residual risk**: **stated honestly**: rate limiting is per-key, not
  per-org — an org with multiple keys can exceed the intended per-org
  ceiling by rotating between them. No per-connection timeout is
  enforced on the legacy SSE transport beyond uvicorn's own defaults —
  not yet load-tested for this specific exhaustion scenario (Phase 25
  benchmarking covered throughput, not adversarial connection-holding).

---

## 3. Trust Boundaries

```
User / Agent
      │
      ▼
Internet                                    UNTRUSTED
      │
      ▼
TLS termination / reverse proxy             CONDITIONALLY TRUSTED
      │   (deployer-configured; app speaks plain HTTP behind it)
      ▼
WhitePact API / MCP transport               BOUNDARY — validates request shape
      │   (Pydantic models, CSP/HSTS/security headers, DNS-rebinding
      │    protection when configured)
      ▼
Authentication                              BOUNDARY — Bearer token / OIDC / SAML validated
      │   (auth/oidc.py, auth/saml.py, static-key hash comparison)
      ▼
RBAC / tenant isolation                     BOUNDARY — role + org_id enforced
      │   (require_role, org_id filtering on every repository method)
      ▼
Machine Authority / Governance Runtime      TRUSTED (internal, still validated)
      │   (WhitePactRuntimeGateway — deterministic, DB-free evaluation)
      ▼
Policy / Risk / Workflow / Approval         TRUSTED (internal, deterministic)
      │   (Policy, TOOL_RISK_TIERS, WorkflowSequenceRule, ApprovalRequest)
      ▼
Execution Permit / execution control        BOUNDARY — structural binding checked
      │   (ExecutionAuthorization: digest + org + expiry + single-use)
      ▼
MCP / API / external target                 UNTRUSTED beyond this point
      (InternalToolExecutor → dispatch_tool, or upstream MCP proxy —
       SSRF-guarded before any outbound call)
```

Additional boundaries not on the primary request path:

| Boundary | Status | Validation at the boundary |
|---|---|---|
| WhitePact ↔ PostgreSQL | TRUSTED (credentialed) | Parameterized queries only (2.5); credential itself is the deployer's responsibility (env var / secret manager) — not application-mediated. |
| WhitePact ↔ Redis | CONDITIONALLY TRUSTED | Rate-limit counters only — never governance data, PII, or credentials; a Redis compromise cannot leak sensitive data because none is stored there. |
| WhitePact ↔ OIDC provider | CONDITIONALLY TRUSTED | JWKS key type/size validated (2.17, 2.18); token signature, audience, issuer, expiry all verified — but the provider's own claim content is trusted once signature-verified (customer's IdP choice, out of WhitePact's control). |
| WhitePact ↔ LLM provider | UNTRUSTED (opt-in, customer-configured) | WhitePact does not alter or audit what the provider does with a request once sent — the customer's own API key/account/provider terms apply (`ENTERPRISE_SECURITY.md` "Data residency"). |
| WhitePact ↔ webhook target | UNTRUSTED, SSRF-validated | `validate_webhook_url()` at registration and at every delivery (2.6). |
| WhitePact ↔ upstream MCP server | UNTRUSTED, SSRF-validated | Registry + SSRF-guarded proxy executor (2.6, 2.8) — destination validated; result *content* is not independently verified. |
| Developer ↔ GitHub CI | TRUSTED (branch-protected) | Required status checks (Lint × 2, Build, Helm lint, dco-check, gitleaks, Accessibility, i18n) gate every merge to `main`; `dependency-review` reviews every PR's dependency diff. |
| GitHub Actions ↔ PyPI | TRUSTED (OIDC, no static secret) | PyPI Trusted Publishing — no long-lived API token to steal; build provenance attested (2.21). |
| Deployment ↔ secrets manager/environment | TRUSTED (deployer-managed) | `compliance/KEY_MANAGEMENT.md` custody rules; the application never logs or echoes the values it reads. |

---

## 4. Secure Design Principles

Each principle below points at a concrete, current implementation —
not a general claim about intent.

- **Least privilege** — `require_role(min_role)` per endpoint
  (`dashboard/app.py`); org-scoped API keys cannot act outside their
  own org; `OrgAuthorityCeiling` (2.3) lets an org bound what *any* key
  under it can ever authorize, independent of per-key configuration.
- **Complete mediation** — every dispatched call through this
  platform's own MCP tools re-checks authorization at execution time
  via `InternalToolExecutor` (2.22), not once at session start; every
  delegation is re-validated fresh per call (2.16, "continuous
  re-authorization"), not cached from grant time.
- **Fail-safe defaults / fail closed** — an evidence-write failure
  blocks the underlying action rather than proceeding unlogged (2.24
  claim C12, tested in `tests/test_mcp_governance_dispatch.py`); a
  legacy approval/authorization with no digest matches nothing
  (fail-closed on missing data, not fail-open); a JWKS endpoint serving
  a private key or a weak key is rejected before it's trusted (2.17,
  2.18).
- **Defense in depth** — SSRF validation runs at both registration
  *and* delivery time for webhooks, specifically because DNS can
  resolve differently between the two (2.6); the audit-log chain
  detects tampering *in addition to* — not instead of — RBAC and
  tenant-isolation controls that prevent unauthorized access in the
  first place.
- **Explicit trust boundaries** — Section 3 above is not aspirational;
  every boundary crossing named there maps to a real validation step in
  source, cited alongside it.
- **Input validation** — Pydantic models validate every FastAPI request
  body/query parameter before a handler runs; `crypto_policy.py`
  validates externally-supplied keys/secrets before they're trusted
  (2.17).
- **Secure defaults** — `mcp_governance_enabled` and
  `RAI_MCP_HTTP_ALLOWED_HOSTS`/`ALLOWED_ORIGINS` (DNS-rebinding
  protection) default to *off*, stated honestly as a gap rather than a
  false sense of "secure by default" — see the residual-risk notes on
  2.22 and `THREAT_MODEL.md` §1 for why this is a real, documented
  trade-off (avoiding a breaking-change default), not an oversight.
  Where a default *is* safety-first: `OrgAuthorityCeiling` fields
  default to unrestricted (matches pre-feature behavior, not a
  regression) but new capabilities like SSRF validation and JWKS
  key-strength checks are unconditional, not opt-in.
- **Tenant isolation** — Section 2.4.
- **Minimization of sensitive data** — `EvidenceRecord` stores argument
  *field names*, never values (`governance/evidence.py` module
  docstring); webhook/audit payloads never include request/response
  bodies.
- **Cryptographically secure randomness** — every WhitePact-generated
  secret (API keys, TOTP seeds, Fernet keys) uses `secrets`/`os.urandom`-backed
  CSPRNGs, never `random` — `crypto_policy.py` module docstring states
  this explicitly as why those particular secrets need no runtime
  policy check (correct by construction).
- **Deterministic authorization** — risk tiering, policy evaluation,
  and workflow-sequence matching are all table-driven/rule-based, not
  LLM-inferred (2.9, 2.11) — a deliberate, stated preference for
  auditable, reproducible decisions over probabilistic ones.
- **Revocation** — SSO enforcement invalidates an org's static keys
  immediately (2.1); delegation revocation is checked fresh on every
  call, not cached (2.16).
- **Auditability** — every governed decision produces a hash-chained
  `EvidenceRecord`; every API request is logged to `audit_log`
  (endpoint, method, org, key, status, timing).
- **Separation of security-critical logic from model reasoning** — the
  entire governance decision pipeline (risk tiering, policy, workflow,
  approval, execution binding) runs with zero LLM calls in the
  decision path — `governance/gateway.py`'s own docstring states
  `WhitePactRuntimeGateway` is synchronous and DB-free by design, a
  pure function of its inputs.
- **Bounded trust of external systems** — webhook targets and upstream
  MCP servers are SSRF-validated before any outbound call (2.6, 2.8); a
  customer's own OIDC provider and LLM provider are explicitly named
  trust boundaries this platform validates the *mechanics* of (token
  signature, key strength) but not the *content* of (2.18's residual
  risk, `ENTERPRISE_SECURITY.md` "Data residency").

---

## 5. Common Implementation Weaknesses — How They're Countered

| Weakness | Status | Detail |
|---|---|---|
| SQL injection | **Countered** | Section 2.5. |
| Command injection | **Not applicable / countered** | No `eval`, `exec`, `os.system`, or `subprocess(shell=True)` anywhere in `src/responsibleai/` — confirmed by manual review (`compliance/INTERNAL_SECURITY_REVIEW.md` §2.5). The one `subprocess` call (`db/migrate.py`, invoking `alembic`) uses `create_subprocess_exec` with an argument list, not a shell string. |
| SSRF | **Countered** | Section 2.6. |
| XSS | **Partially countered, stated honestly** | `Content-Security-Policy` restricts script/style sources, `X-Content-Type-Options: nosniff`, `X-XSS-Protection` set (`dashboard/middleware.py`). **Residual**: the dashboard's static pages use inline `<script>`/`<style>` and `onclick=` handlers, requiring `'unsafe-inline'` in the CSP — documented in the middleware's own comment as a known relaxation pending a refactor to `addEventListener` + nonces, not hidden. |
| CSRF | **Mitigated by design, not a dedicated token** | The API is Bearer-token authenticated, not cookie/session-based for API calls — CSRF requires an ambient credential (cookies) a browser attaches automatically; a Bearer token in an `Authorization` header is not ambient. The one cookie-adjacent flow (SAML session token) is delivered via URL fragment, never a cookie, and consumed once client-side (`auth/saml.py` module docstring). |
| Broken authentication | **Countered** | Section 2.1, 2.18; MFA (TOTP) available and rate-limited (`compliance/INTERNAL_SECURITY_REVIEW.md` §2.5). |
| Broken authorization | **Countered** | Section 2.2, 2.3, 2.4. |
| Cross-tenant leakage | **Countered, with a stated review-discipline gap** | Section 2.4. |
| Unsafe redirects | **Not applicable** | The application does not implement an open-redirect-shaped feature (no user-supplied `next`/`redirect_uri` echoed without validation) — OIDC's `redirect_uri` is a deployer-configured value, not user input. |
| Weak randomness | **Countered** | Section 4, "Cryptographically secure randomness". |
| Weak cryptographic algorithms | **Countered** | JWT verification allowlists only RS256/RS384/RS512/ES256/ES384/ES512 (2.18) — never `none` or symmetric HMAC-family algorithms (which would let a public-key holder forge a token). Webhook signing uses HMAC-SHA256. |
| Weak cryptographic keys | **Countered** | Section 2.17. |
| Timing-sensitive secret comparison | **Partially addressed, residual risk stated** | Org-scoped API key auth compares against a SHA-256 *hash* looked up by an index, not a raw secret compared character-by-character against a list. **Residual**: the legacy flat super-admin path (`dashboard/middleware.py::build_api_key_dependency`) uses Python's `in` against a list of keys, which is not constant-time. Given this path is for a small, operator-configured set of legacy keys (not per-tenant, not the primary auth path — `ENTERPRISE_SECURITY.md` describes org-scoped keys as the primary mechanism) and any practical timing signal is dominated by network jitter over HTTP, this is accepted as low-risk rather than fixed — stated here rather than silently left unmentioned. |
| Secret logging | **Countered** | `db/encryption.py`'s error path never echoes the key value (only a generic "not a valid Fernet key" message); `compliance/KEY_MANAGEMENT.md` states this as a design requirement, not just an accident of current behavior. |
| Unsafe deserialization | **Not applicable** | No `pickle.load`, no unsafe `yaml.load` anywhere in `src/responsibleai/` (confirmed manual review, `compliance/INTERNAL_SECURITY_REVIEW.md` §2.5). API request bodies are parsed via Pydantic (JSON schema validation), not arbitrary deserialization. |
| Path traversal | **Addressed for the one identified surface** | `nltk.data.load()`'s PYSEC-2026-597 advisory concerns attacker-controlled percent-encoded paths; WhitePact's only call site (`nltk.download("vader_lexicon", quiet=True)`) uses a hardcoded literal, never attacker input — triaged in `compliance/INTERNAL_SECURITY_REVIEW.md` §2.4 and `pip-audit`'s ignore list with the reasoning inline in `ci.yml`. |
| Malicious file/input handling | **Bounded** | No file-upload endpoint exists in the current API surface that accepts arbitrary binary content for server-side processing; SAML/XML parsing uses an explicitly XXE-hardened `lxml` parser (`resolve_entities=False, no_network=True, load_dtd=False`, `auth/saml.py::_safe_xml_parser`). |
| Insecure TLS | **Deployer responsibility, verified for the reference deployment** | `ENTERPRISE_SECURITY.md` "Encryption at rest" — the live reference deployment was independently checked and negotiates TLS 1.3 with PFS-by-construction; self-hosted deployments are the deployer's own TLS configuration (documented nginx config in `DEPLOYMENT.md` requires TLS 1.2+, PFS-only ciphers). |
| Certificate-validation bypass | **Not applicable** | No TLS verification is disabled anywhere in the codebase (no `verify=False` on any `httpx`/`requests` call) — outbound calls (JWKS fetch, webhook delivery) use Python's default `ssl` context. |
| Dependency vulnerabilities | **Countered** | Section 2.20. |
| Supply-chain tampering | **Countered for build/publish; tag-signing is an open gap** | Section 2.21; see `compliance/SIGNED_VERSION_TAGS.md`. |
| Race conditions in approvals/permits | **Countered** | Section 2.12; `WHERE status='PENDING'` SQL guard plus in-Python pre-check tested under concurrent resolution. |
| Replay attacks | **Countered** | Sections 2.12, 2.15 (approval and Execution Permit replay); OAuth2 `state` parameter and SAML `InResponseTo` single-use tracking prevent authentication-flow replay (`auth/oidc.py`, `auth/saml.py`). |

---

## 6. Supply-Chain Argument

Current, verified CI/release reality (not aspirational):

| Control | Where | What it does |
|---|---|---|
| Branch protection on `main` | GitHub repo settings, verified via `GET .../branches/main/protection` re-fetch (`compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`) | Requires PRs, blocks direct pushes; no repository ruleset exists to conflict with or override it. |
| Required CI status checks | `.github/workflows/ci.yml` | Lint (Ruff `check` + `format --check`), type-check (mypy, `src/responsibleai`), test suite with coverage (`--cov-fail-under=80` blended + a separate pure-branch-coverage gate for OpenSSF `dynamic_analysis`), Build distribution, Helm chart lint, dco-check, gitleaks, Accessibility (WCAG2AA), i18n unit tests. |
| Ruff | `ci.yml` | Static lint + formatting, both hard-gated as of this review — see the corresponding CI-hardening work (`ruff check` and `ruff format --check`, both `src/` and `tests/`). |
| mypy | `ci.yml` | Static type-check, `src/responsibleai` — currently clean (0 errors across 116 source files as of this review). |
| pytest | `ci.yml` | Full suite, coverage-gated. |
| Bandit | `security-scan.yml` (weekly + push-to-main), and run ad hoc during `compliance/INTERNAL_SECURITY_REVIEW.md` | SAST — found and drove the fix of the SQLi-shaped pattern in `CostTracker` (2.5). |
| pip-audit | `ci.yml` (every push) + `security-scan.yml` (weekly) | Known-CVE dependency scanning against the installed environment. |
| Gitleaks | `.github/workflows/gitleaks.yml` | Every PR diff + weekly full-history scan. |
| SBOM | `.github/workflows/publish.yml` | CycloneDX SBOM generated from the *actual built artifact's* installed dependency closure (installs the built wheel into a clean venv, then scans that), not a static `pyproject.toml` read. |
| GitHub Artifact Attestations | `.github/workflows/publish.yml::actions/attest-build-provenance` | Sigstore-backed build provenance for every released wheel/sdist. |
| PyPI Trusted Publishing | `.github/workflows/publish.yml::pypa/gh-action-pypi-publish` | OIDC-based publishing — no long-lived PyPI API token stored as a repository secret. |
| Dependency Review | `.github/workflows/dependency-review.yml` | Reviews new dependencies/version bumps/licenses on every PR before merge. |
| OpenSSF Scorecard | `.github/workflows/scorecard.yml` | Weekly, independently reproducible third-party-run posture scan, published to the public Scorecard API. |

**Not yet true, stated plainly**: signed Git version tags. See
`compliance/SIGNED_VERSION_TAGS.md` for the current audit and status —
this is tracked as a separate, explicit gap, not implied to be covered
by the artifact attestation above (they verify different properties;
see that document's own explanation).

---

## 7. Evidence Matrix

| Security Claim | Threat (§2 ref) | Control | Implementation | Test | CI/Scanner | Residual Limitation |
|---|---|---|---|---|---|---|
| C1 Authenticated ops require valid identity | 2.1, 2.2 | Bearer/OIDC/SAML auth | `dashboard/app.py::get_org_context`, `auth/oidc.py`, `auth/saml.py` | `tests/test_dashboard_api.py`, `tests/test_oidc.py`, `tests/test_saml*.py` | ci.yml pytest | Static keys valid indefinitely absent SSO enforcement |
| C2 RBAC restricts by role | 2.2 | `require_role` | `dashboard/app.py` | `tests/test_dashboard_api.py` | ci.yml pytest | No automated static check that every endpoint declares a role |
| C3 Tenant isolation | 2.4 | `org_id` filtering | every repository in `db/` | `tests/test_tenant_isolation.py` | ci.yml pytest | Convention-enforced, not structurally unbypassable; one real instance found-and-fixed (audit `org_id: null` bug) |
| C4 Runtime authority enforcement | 2.22 | `WhitePactRuntimeGateway` + `InternalToolExecutor` | `governance/gateway.py`, `governance/execution.py` | `tests/test_mcp_governance_dispatch.py`, `tests/test_executor_bypass_invariant.py` | ci.yml pytest | Only covers this platform's own MCP dispatch path, not direct library use; opt-in (`mcp_governance_enabled`) |
| C5 No authority expansion via delegation | 2.10 | `validate_attenuation` | `governance/models.py`, `db/delegation_repository.py` | `tests/test_delegation_chains.py`, `tests/test_delegation_graph.py` | ci.yml pytest | Root grants skip the check by design (ceiling is the root constraint) |
| C6 Execution Permit/approval binding | 2.12–2.15 | `compute_action_digest`, consumed-flag | `governance/approval.py`, `governance/execution.py` | `tests/test_approval_execution_binding.py`, `tests/test_executor_bypass_invariant.py` | ci.yml pytest | `ExecutionAuthorization` not cryptographically signed (correct only while in-process) |
| C7 Untrusted destinations validated | 2.6, 2.8 | `validate_webhook_url`, upstream SSRF guard | `webhooks/manager.py`, `governance/upstream_executor.py` | `tests/test_webhooks.py::TestSSRFGuard` | ci.yml pytest | Public-but-attacker-chosen targets not restricted (inherent to the feature); upstream server *content* not verified |
| C8 No plaintext credential storage | 2.1, 2.19 | SHA-256 hash-only | `db/org_repository.py` | — | gitleaks | Whole-DB encryption at rest is a deployer responsibility |
| C9 Weak keys rejected | 2.17, 2.18 | `crypto_policy.py` | `auth/crypto_policy.py`, `auth/oidc.py` | `tests/test_crypto_policy.py`, `tests/test_oidc.py` | ci.yml pytest | Floor on what WhitePact trusts, not a claim about a provider's internal practices |
| C10 Release artifacts have build provenance | 2.21 | Sigstore attestation | `.github/workflows/publish.yml` | — (workflow-level, not unit-tested) | publish.yml | Git tag itself not yet signed — see `compliance/SIGNED_VERSION_TAGS.md` |
| C11 Hash-chain tamper-evidence | 2.23 | `entry_hash = sha256(prev_hash + fields)` | `db/evidence_repository.py` | (chain-verify covered by governance persistence tests) | ci.yml pytest | Does not detect full-chain recompute by an attacker with DB write access; process-local, not cross-replica |
| C12 Fail-closed on evidence-write failure | 2.24 (C12) | explicit catch + block | `mcp/governance_integration.py` | `tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed` | ci.yml pytest | Trust-check (as opposed to evidence-write) failures fail *open* by asymmetric, documented design |

---

## 8. Known Limitations

Preserved from `ENTERPRISE_SECURITY.md` and `compliance/INTERNAL_SECURITY_REVIEW.md`,
not softened for this document:

- **No independent penetration test has been performed, and none is
  claimed.** `compliance/INTERNAL_SECURITY_REVIEW.md` is a self-review
  by the same person who maintains the code. A genuine third-party
  pentest is a real, open, cost-gated item
  (`compliance/SOC2_READINESS.md` §4).
- **No SOC 2 or ISO 27001 certification exists.** See `SLA.md` for the
  honest alternative-evidence path (`compliance/SOC2_ALTERNATIVE_PATH.md`).
  Self-attested OpenSSF badges (Passing, Baseline, and — if this
  document achieves it — Silver's `assurance_case`) are not equivalent
  to independent certification and are never represented as such.
- **Encryption at rest is not guaranteed by the application for every
  deployment mode.** SQLite (self-hosted default) is plaintext-on-disk
  unless the host volume is encrypted. Only the live reference
  deployment's managed Postgres (Supabase) and one opt-in PII column
  (`audit_log.ip_address`) have encryption-at-rest guarantees this
  document stands behind.
- **The audit/evidence hash chains cannot detect an attacker with full
  database write access who recomputes the entire chain from scratch.**
  No external anchoring (e.g. periodic publication to write-once
  storage) exists yet. Each chain is process-local, not a single global
  chain across a multi-replica deployment.
- **Any configured LLM provider (OpenAI, Anthropic, Google, etc.) is a
  third-party dependency outside WhitePact's control.** The customer's
  own API key, account, and provider terms apply to whatever is sent —
  WhitePact cannot audit or alter what a provider does with a request
  once sent.
- **Git version tags are signed as of v1.2.3 (2026-08-19); every tag
  before it is not.** See `compliance/SIGNED_VERSION_TAGS.md` for the
  full audit — 9 historical tags remain unsigned by design (not
  rewritten), and every release from v1.2.3 onward is gated by
  `.github/workflows/publish.yml`'s `verify-signed-tag` job, which
  rejects a lightweight, unsigned, or unapproved-signer tag before any
  build/publish step runs.
- **Rate limiting is per-API-key, not per-organization** — an org with
  multiple keys can exceed an intended per-org ceiling by rotating
  between them (§2.24).
- **Several controls in this document are optional rather than
  mandatory**, stated explicitly rather than implied to be default-on:
  `mcp_governance_enabled` (defaults `False`), `OrgAuthorityCeiling`
  (defaults unrestricted), DNS-rebinding protection env vars (unset by
  default), webhook HMAC signing (empty secret = unsigned, a legitimate
  explicit choice), and `RAI_FIELD_ENCRYPTION_KEY` (unset by default,
  so existing installs aren't broken by a newly-required key).
- **No fuzz-testing or dedicated penetration test has been performed
  against any surface named in this document** — Bandit/pip-audit/manual
  review are the current coverage, not adversarial fuzzing.
- **This document itself has not been reviewed by a second person.**
  Same solo-founder limitation `GOVERNANCE.md` already states about the
  quarterly risk-review cadence — treat this as a structured
  self-assessment, not independent red-team output.

---

## Revisiting this document

Update this assurance case whenever a new transport, auth mechanism,
governance primitive, or supply-chain control ships — the same day, not
"eventually," matching the standard `THREAT_MODEL.md` and `GOVERNANCE.md`
already hold themselves to. A stale assurance case that implies
coverage it doesn't have is worse than an honestly incomplete one. If
you find a claim here that no longer matches the code, treat the code
as ground truth and report the discrepancy per `SECURITY.md`.
