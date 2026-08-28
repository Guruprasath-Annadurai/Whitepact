# WhitePact Enterprise Neural — Codex Independent Security Review Handoff

**Assume this implementation is insecure until executable evidence proves otherwise.**

This document is the frozen, authoritative handoff for the independent
Codex security review. It supersedes any looser phrasing in earlier
summaries (e.g. `CHATGPT_HANDOFF_SUMMARY.md`, PR #50's description) —
where those documents conflict with this one, this one is correct.

---

## 0. Exact review commit

| Field | Value |
|---|---|
| Repository | `Guruprasath-Annadurai/Whitepact` |
| Branch | `security/enterprise-neural-phase-0-1` |
| PR | [#50](https://github.com/Guruprasath-Annadurai/Whitepact/pull/50) — **OPEN, UNMERGED** |
| Head commit SHA | `4136dc9beab422f22846fa90b5fa3365f75129fb` |
| Base branch | `main` |
| Base SHA (merge-base) | `9dcdc1bebe0ad856bd399dc627d17c35a2cc5828` |
| Verification timestamp (UTC) | 2026-08-28T18:05:31Z |

Note: §3's fresh-verification numbers below (test suite, ruff, mypy,
Bandit, pip-audit) were captured against commit `2913b0f` — the
commit immediately prior to this one, which added only this document
and `CODEX_ATTACK_MAP.md` (documentation, zero source/test files
touched). PR #50's 12/12 CI check re-confirmation and the CodeQL
alert count were re-verified a second time, specifically against
`4136dc9` (this exact head), after that commit's own CI run
completed — see the timestamp above.

**If any commit is added to this branch after the timestamp above, this
section is stale — re-verify `git rev-parse HEAD` before trusting the
rest of this document.**

---

## 1. Corrected project-status language

Do not describe this initiative as "all 18 phases fully complete"
without qualification. The accurate statement:

> All **in-scope** Enterprise Neural phases (0-2, 4-8, 10-18) are
> complete on this branch. **Phase 3** (Zero-Trust Identity + Tenant
> Isolation) and **Phase 9** (Heart Production Authority Integration)
> are handled/deferred into the separate, already-in-progress
> `docs/heart-production/` initiative and are **not completed by this
> Enterprise Neural branch.**

This dependency is not hidden — see §7 below for exactly what remains
incomplete there and what it means for code on this branch.

---

## 2. Neural product reality — exactly what exists

**CONTRACT EXISTS ≠ REAL DEVICE CAPABILITY EXISTS.**

WhitePact Neural currently contains typed security/governance
contracts and property tests. It does:

- Classify neural data (N0-N5) with a fail-closed consent policy
- Persist a neural vault index (metadata only, never raw payload)
- Define a device capability/trust contract (`NeuralCapabilityManifest`)
- Define a typed `NeuralDecision` with misuse-rejection logic
- Bind a decision to a proposed action via `NeuralIntentAttestation`
  (mutation of any security-relevant field invalidates the attestation)
- Require actual on-file scientific evidence before a capability may
  be labeled `VALIDATED`
- Carry property/security tests for every one of the above

It does **not** contain, and no document in this repository should
imply otherwise:

- A production BrainFlow integration
- A production LSL integration
- A concrete BCI vendor adapter
- A real EEG signal-processing pipeline
- A trained neural decoder
- A production semantic or inner-speech thought decoder
- Real user calibration data
- Real neurological accuracy measurements
- Clinical validation
- Medical-device approval

Verified by direct source inspection: `governance/neural/device.py`'s
`BCIDeviceAdapter` is a `Protocol` with zero concrete implementations
in `src/`; `governance/neural/decision.py` defines `NeuralDecision`'s
shape and validation logic but no code path produces one from a real
signal; `mint_neural_intent_attestation()` has zero call sites outside
its own module and its own test file (structurally proven, Phase 8's
regression guard, `tests/test_llm_agent_security_boundary.py`) — **no
neural governance code is wired into any live execution path today.**

---

## 3. Fresh verification against current HEAD (not carried forward)

All of the following were re-run against `2913b0f` specifically, not
assumed from an earlier phase's report:

| Check | Result | Evidence |
|---|---|---|
| Full regression suite | **3147 passed, 1 skipped, 0 failed** | `uv run pytest -q`, 130.36s |
| ruff check | **All checks passed** | `ruff check src/ tests/` |
| ruff format | **370 files already formatted** | `ruff format --check src/ tests/` |
| mypy | **0 errors, 163 source files** | `mypy src/responsibleai` |
| Bandit (`-ll`, matching CI) | **No issues identified** (0 at reported threshold; 19 low-severity/low-confidence findings exist below the CI threshold, unchanged from historical baseline) | `bandit -r src/responsibleai -ll` |
| pip-audit (`--skip-editable --ignore-vuln PYSEC-2026-597`, matching CI) | **No known vulnerabilities found** | `pip-audit ...` |
| PR #50 CI (via GitHub API, scoped to head SHA `2913b0f`) | **12/12 completed/success** | `gh api .../commits/2913b0f/check-runs` |
| CodeQL open alerts (filtered by `tool.name == "CodeQL"`) | **0** | `gh api .../code-scanning/alerts` |
| Dependency review | **success** (part of the 12/12 above) | same API call |
| Gitleaks | **success** (part of the 12/12 above) | same API call |

No check above is reported as PASS without the underlying command
output backing it. Nothing was in a PENDING state at verification
time — all 12 required checks were `completed`.

---

## 4. Crypto foundation activation status — priority attack surface

**Claim under test**: is the Phase 2 `governance/crypto/` envelope-
encryption foundation actually protecting anything in production
today? **Answer, from source inspection: no — it is fully built and
tested, but not activated anywhere.**

- `configure_field_encryption_key()` (`db/encryption.py`) and
  `configure_session_signing_key()` (`auth/saml.py`) — the only two
  functions that populate the module-level "active key" state the new
  scheme reads — **have zero call sites in `src/responsibleai/` outside
  their own definitions.** Verified: `grep -rn
  "configure_field_encryption_key(\|configure_session_signing_key("
  src/responsibleai --include="*.py"` returns only docstring mentions
  and the `def` lines themselves. They are called only from test files
  (`tests/test_field_encryption.py`, `tests/test_saml.py`,
  `tests/test_rotate_field_encryption_key.py`).
- No application-startup path (`dashboard/app.py`'s lifespan,
  `mcp/server.py`'s `_build_http_app()`) constructs a
  `LocalEnvelopeKeyProvider` or a `CryptoKeyRepository`, or calls
  either `configure_*` function. Verified by grep: zero instantiation
  sites of either class outside `governance/crypto/`'s own module and
  test files.
- **What is actually active today**: the *legacy* scheme only —
  `RAI_FIELD_ENCRYPTION_KEY`-based Fernet for column encryption
  (`db/encryption.py::_load_fernet()`), and `SAMLConfig.session_secret`-
  based HMAC for session tokens. Both predate Phase 2 and are
  unrelated to the new `KeyProvider` architecture.
- **Plaintext fallback exists and is real, by design**:
  `EncryptedString.process_bind_param()` — if neither the new scheme
  is configured *nor* `RAI_FIELD_ENCRYPTION_KEY` is set, the value is
  written and read back as **plain text**, with no error. This is
  documented in the class's own docstring as intentional ("safe to
  apply to a column in an existing deployment without forcing
  encryption on immediately"), not a bug — but it means a deployment
  that never sets `RAI_FIELD_ENCRYPTION_KEY` stores `audit_log.ip_address`,
  `public_incident_reports.reporter_name`/`.reporter_contact`,
  `org_api_keys.mfa_secret`, and `webhook_configs.secret` in **plain
  text** today.
- **Old ciphertext readability**: unaffected. Since nothing ever
  writes the new scheme's prefix (`_NEW_SCHEME_PREFIX`), every existing
  encrypted value on disk is either legacy Fernet or plaintext; reads
  correctly fall through to the legacy path. No migration hazard from
  this dormancy.
- **Fail-closed behavior that *does* exist**: if a stored value ever
  *did* carry the new-scheme prefix (it currently cannot, since
  nothing writes it) but no key were configured at read time,
  `process_result_value()` raises `DecryptionError` rather than
  returning garbage or plaintext — this path is real and tested, just
  currently unreachable in production.
- **What a deployment must configure to actually activate Phase 2**:
  wire a real `KeyProvider` (e.g. `LocalEnvelopeKeyProvider` backed by
  `CryptoKeyRepository`) at application startup and call
  `configure_field_encryption_key()`/`configure_session_signing_key()`
  before the first request is served. **No code path does this today.**

This is the single largest, most concrete gap on this branch. It is
not a new finding — Phase 2's own reports named it as the phase's
largest residual risk — but it is restated here with precise,
re-verified evidence for Codex, since it is exactly the kind of
"looks encrypted in the source, isn't encrypted in production" gap an
attacker (or a careless deployment) would exploit.

---

## 5. Phase 3 / Phase 9 dependency risk

`docs/heart-production/` currently contains three files:
`00_CURRENT_RUNTIME_MAP.md` (audit), `01_AUTHORITY_CONTRACT.md`
(`AuthorityGrant`, the boundary object), `02_IDENTITY_RESOLUTION.md`
(`identity_authority_adapter.py`, the fail-safe `IdentityContext.kind`
→ `RootType` mapping). **No Phase 3 file exists.**
`02_IDENTITY_RESOLUTION.md`'s own "What this phase does not do"
section states explicitly:

> - Does not resolve a real `authority_source` chain (Phase 5).
> - **Does not persist anything (Phase 3).**
> - **Does not wire this adapter into `apply_governance()`/
>   `apply_upstream_governance()` (Phase 6).**

So: Heart-production's root-authority/consent/persistence work is
real but **not wired into the live governed dispatch path at all**.
`mcp/governance_integration.py::apply_governance()` — the actual,
live decision path every governed MCP call goes through — does not
call `identity_authority_adapter.py`, `root_authority.py`, or any
other Heart-production module. It builds `AuthorityContext` directly
from `ceiling_repo`/`policy_repo`/`delegation_repo`, entirely
independent of Heart's root-of-authority concept.

**Does any code on this branch assume a Heart-production guarantee
that doesn't yet exist?** No live code does, because no live code
calls into Heart-production at all yet — there is nothing to assume
incorrectly. The risk is the inverse: `apply_governance()` still
synthesizes authority from authentication alone (the exact gap
`docs/heart-production/00_CURRENT_RUNTIME_MAP.md`'s own audit
identified as the reason this initiative exists), and none of Phases
4-8/10-17 on this branch changed that — none of them touch
`apply_governance()`'s authority-construction logic. Neural
governance code (`NeuralIntentAttestation` etc.) is even further
removed: it has zero call sites anywhere, so it cannot currently rely
on — or be undermined by — anything Heart-production has or hasn't
built yet.

**Not fixed here, per instruction**: this is documented as an external
dependency risk for Codex, not silently patched.

---

## 6. Neural trust boundary — canonical diagram

```
HUMAN
  ↓
BCI DEVICE                          — NOT IMPLEMENTED (no vendor decision made)
  ↓
DEVICE ADAPTER                      — CONTRACT ONLY (BCIDeviceAdapter Protocol, zero implementations)
  ↓
SIGNAL PROCESSING                   — NOT IMPLEMENTED
  ↓
PERSONAL NEURAL MODEL               — NOT IMPLEMENTED
  ↓
NEURAL DECODER                      — NOT IMPLEMENTED
  ↓
NEURAL DECISION                     — CONTRACT ONLY (NeuralDecision type + misuse-rejection logic; no decoder produces one)
  ↓
NEURAL INTENT ATTESTATION           — CONTRACT ONLY, tested, zero live call sites
  ↓
WHITEPACT HEART                     — PARTIALLY IMPLEMENTED (constitution, root-authority types, identity adapter exist; NOT wired into any live dispatch path; Phase 3 persistence NOT STARTED)
  ↓
WHITEPACT BRAIN (risk/policy engine)— IMPLEMENTED and live (governance/gateway.py, risk.py, policy.py — real, tested, unconditionally wired into both governed MCP dispatch paths)
  ↓
WHITEPACT CITADEL (execution containment) — IMPLEMENTED and live (ExecutionAuthorization, InternalToolExecutor, UpstreamMCPExecutor — real, tested, digest-bound, single-use)
  ↓
EXECUTION PERMIT                    — IMPLEMENTED (= ExecutionAuthorization; unsigned, in-process only — see §9)
  ↓
LLM / TOOL / SOFTWARE               — IMPLEMENTED (dispatch_tool(), 27 internal tools + upstream MCP proxy)
```

**The critical fact this diagram makes visible**: everything from
`WHITEPACT BRAIN` downward is real, live, and tested. Everything from
`NEURAL DECISION` upward through `WHITEPACT HEART` exists only as
typed contracts with no live wiring — there is currently **no path**
by which a real neural signal could reach the Brain/Citadel/Execution
layers even if a device existed, because `NeuralIntentAttestation`
has no call site that would hand it to `apply_governance()`. This is
a real gap between the neural governance layer and the general
governance pipeline, not yet closed by any phase on this branch.

---

## 7. Neural data flow (N0-N5)

| Class | Source | Storage | Encryption | Retention | Logging | Telemetry | External transmission | LLM visibility | Enterprise-admin visibility | Deletion | Consent required |
|---|---|---|---|---|---|---|---|---|---|---|---|
| N0 (raw neural) | DESIGNED ONLY (`NeuralDataClass.N0_RAW_NEURAL`) | NOT IMPLEMENTED — `NeuralVaultEntry` structurally has no payload field | N/A, nothing to encrypt yet | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY — `LOCAL_ONLY_BY_DEFAULT` forbids by default | NOT IMPLEMENTED | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY — `ConsentCategory` exists, `evaluate_neural_data_flow()` fail-closed-denies with no record |
| N1 | Same as N0 | Same as N0 | Same as N0 | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY, local-only by default | NOT IMPLEMENTED | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY, same evaluator |
| N2 | Same as N0 | Same as N0 | Same as N0 | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY, local-only by default | NOT IMPLEMENTED | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY, same evaluator |
| N3 | DESIGNED ONLY | `NeuralVaultRepository` — PARTIALLY IMPLEMENTED (index/metadata table real, migration `0031`, no payload ever stored) | N/A at this layer | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY, not local-only-by-default | NOT IMPLEMENTED | NOT IMPLEMENTED | PARTIALLY IMPLEMENTED — `soft_delete()` exists on the repository | DESIGNED ONLY, same evaluator |
| N4 | DESIGNED ONLY | Same as N3 | N/A | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | PARTIALLY IMPLEMENTED (same soft-delete) | DESIGNED ONLY |
| N5 (operational metadata) | DESIGNED ONLY | Same as N3 | N/A | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | DESIGNED ONLY | NOT IMPLEMENTED | NOT IMPLEMENTED | PARTIALLY IMPLEMENTED | DESIGNED ONLY |

**Read this table literally**: no runtime code path currently writes,
reads, transmits, or displays any actual neural data of any
classification, because no device/decoder exists to produce it. Every
"DESIGNED ONLY" cell describes typed vocabulary and a fail-closed
policy function that has never been exercised against real data. The
one exception is `NeuralVaultRepository`'s CRUD operations
themselves, which are real, tested, DB-backed code — "PARTIALLY
IMPLEMENTED" there means the storage layer exists and is correct by
construction (no payload field to leak), not that any real data has
ever flowed through it.

---

## 8. Fail-closed matrix

| Scenario | Expected | Actual implementation | Evidence |
|---|---|---|---|
| Database unavailable | DENY/ERROR | Repository calls raise; `apply_governance()` has no try/except around most repository reads, so the exception propagates and the tool never executes (fail-closed by propagation) | `tests/test_resilience_fail_closed_matrix.py` (6 of the 9 pre-`evaluate()` dependencies proven directly) |
| Authority repository (ceiling/policy/delegation) unavailable | DENY/ERROR | Same propagation mechanism as above | `tests/test_resilience_fail_closed_matrix.py` |
| Neural vault unavailable | UNTESTED | No live code path calls the neural vault today (§6) — this scenario cannot currently occur in production | None — not reachable, not fabricated |
| Evidence repository unavailable | DENY/ERROR (explicit) | `EvidenceRepository.record()` failure is caught explicitly; the call is blocked with `governance_evidence_unavailable` | `tests/test_mcp_governance_dispatch.py::TestEvidenceWriteFailsClosed` |
| KMS unavailable | N/A — no KMS integration exists | The `KeyProvider` Protocol exists but no concrete KMS-backed implementation exists to fail; `LocalEnvelopeKeyProvider` has no external dependency to be "unavailable" | None — not applicable to current architecture |
| Neural decoder unavailable | N/A — no decoder exists | N/A | N/A |
| Device disconnected | N/A — no device exists | N/A | N/A |
| Brain/policy unavailable | DENY/ERROR | `policy_repo.get_policy()` failure propagates the same way as other pre-`evaluate()` dependencies | `tests/test_resilience_fail_closed_matrix.py` (`PolicyRepository.get_policy`) |
| Citadel/execution unavailable | DENY/ERROR (structural) | `authorize_execution()` refuses to produce an authorization for any non-ALLOW decision; `InternalToolExecutor`/`UpstreamMCPExecutor` both validate before any side effect | `tests/test_executor_bypass_invariant.py`, `tests/test_citadel_execution_containment.py` |
| LLM unavailable | Out of scope of this layer | The governance decision pipeline runs with zero LLM calls in the decision path by design (`gateway.py`'s own docstring: synchronous, DB-free) — an unavailable LLM affects the caller's own use of a model, not this platform's governance decision | `SECURITY_ASSURANCE_CASE.md` §4, "Separation of security-critical logic from model reasoning" |
| Tool unavailable | ERROR surfaces to caller | `dispatch_tool()` raising propagates as an MCP error response; evidence is already recorded before dispatch (Phase 12/`InternalToolExecutor` ordering) so the decision itself is never lost even if the tool call fails after being authorized | Existing `dispatch_tool()` error handling; not independently regression-tested for every one of the 27 tools this phase |
| Cache unavailable | Degrades to direct lookup | `TrustClient`'s cache miss/failure falls through to a direct call, fails *open* (does not block routine calls on a trust-check failure) — deliberate, documented asymmetry, distinct from evidence-write | `test_governance_trust_state.py`, `THREAT_MODEL.md` §3 |
| Clock invalid | UNTESTED | `ExecutionAuthorization.is_expired`/`NeuralDecision` expiry checks trust `datetime.now(UTC)` — no defense against a manipulated system clock is implemented or tested | None — real, undocumented-until-now gap; low practical severity (requires host-level compromise to manipulate) |
| Signature invalid | DENY | Webhook HMAC verification, JWT signature verification (RS/ES-family only, `none`/HMAC-family algorithms rejected) both fail closed | `tests/test_crypto_policy.py`, `tests/test_oidc.py` |
| Attestation expired | DENY | `NeuralIntentAttestation`/`ExecutionAuthorization` both have `is_expired`/expiry checks that deny; for `NeuralIntentAttestation` specifically, this is tested but the attestation itself has zero live call sites (§6) | `tests/test_governance_neural_attestation.py`, `tests/test_executor_bypass_invariant.py` |

Cells marked **UNTESTED** are real gaps, not silently assumed safe —
named here for Codex to prioritize, not smoothed over.

---

## 9. `ExecutionAuthorization` trust-boundary review

**Claim under test**: `ExecutionAuthorization` is deliberately
unsigned because it never crosses a process boundary. **Verified by
exhaustive search, not assumed.**

- No serialization method exists on the class at all: `grep -n
  "to_dict\|asdict\|__reduce__\|json.dumps\|pickle"
  src/responsibleai/governance/execution.py` returns nothing. A
  dataclass with no such method is not JSON-serializable by Python's
  standard `json` module without custom code, which does not exist
  here.
- Exactly three real call sites of `authorize_execution()` exist in
  `src/responsibleai/` (`grep -rn "authorize_execution("`):
  `mcp/upstream_dispatch.py`, and two in
  `mcp/governance_integration.py` (`apply_governance()`'s main path
  and `resume_after_approval()`). All three construct the
  `ExecutionAuthorization` and pass it directly to
  `executor.execute(authorization, action)` **within the same
  `async def`, same call stack, no `await queue.put()`, no Redis, no
  Celery/background-worker dispatch, no HTTP request carrying it.**
- No grep hit for `ExecutionAuthorization` appears in
  `webhooks/manager.py` (the one module in this codebase that does
  make outbound HTTP calls with a payload) or anywhere resembling a
  queue/message-broker integration — this codebase has no such
  integration at all today.

**Conclusion**: the "never crosses a process boundary" assumption
holds by executable evidence — there is no code path that could
serialize or transmit an `ExecutionAuthorization` today, not merely an
absence of an observed instance. This is a structural fact of the
current codebase, not a promise about the future; the module's own
docstring already states signing becomes load-bearing the moment a
future executor lives in a separate process (a not-yet-built
`MCPExecutor`/`HTTPExecutor`).

---

## 10. Self-hosted stdio MCP gap — explicit

- **What stdio can execute**: any of this platform's tools, without
  restriction. `_call_tool()` (the single handler both transports
  share) checks `_current_org`/`_current_governance` ContextVars,
  which are populated only by the hosted-HTTP transport's auth
  middleware. On stdio, both are `None`, so every conditional gate
  (plan/quota check, `apply_governance()` call) is skipped entirely,
  and execution falls straight through to `dispatch_tool(name,
  call_arguments)` with no authority, risk, or policy check of any
  kind. Verified by reading `mcp/server.py`'s `_call_tool()` in full.
- **Which authority checks it bypasses**: all of them — risk tiering,
  policy evaluation, delegation/ceiling checks, evidence recording,
  plan/quota gating. None of these run on stdio.
- **Is it intended only for a single trusted local operator?** Yes,
  per the existing, consistent framing across `execution.py`'s and
  `THREAT_MODEL.md`'s own docstrings: "the self-hosted stdio transport
  has no network identity to spoof — trust boundary is the local
  process invoking it." This is a stated design assumption, not an
  oversight, but it means the trust boundary is entirely outside this
  codebase (the OS process/user running it).
- **Can it access sensitive tools?** Yes — all 27 tools, with no
  per-tool restriction on stdio specifically.
- **Should enterprise mode disable it by default?** No such setting
  exists today. `grep -n "stdio" src/responsibleai/dashboard/config.py`
  returns only docstring mentions; there is no `Settings` field or
  environment variable that disables the stdio entry point. It is a
  separate CLI binary (`whitepact-mcp`/`responsibleai-mcp`,
  `main()` in `mcp/server.py`), not a code path the hosted deployment
  exposes — an operator who never runs that binary is unaffected, but
  no code-level control prevents someone from running it.

This is named explicitly, not hidden under "self-hosted" — Codex
should review whether the stated trust-boundary assumption (local
process = trust boundary) is acceptable for every deployment mode
this platform claims to support.

---

## 11. OpenSSF Scorecard findings — triaged, not just counted

58 open findings on `main` (not this branch specifically — Scorecard
scans the default branch), discovered during Phase 18 while precisely
verifying the CodeQL alert count. Grouped by rule, with a triage
category:

| Rule | Count | Severity (Scorecard) | Triage |
|---|---|---|---|
| `PinnedDependenciesID` | 50 | medium | **Configuration hygiene.** 25 GitHub-owned Actions + 6 third-party Actions not pinned by commit hash (version tags only) across `ci.yml`/`publish.yml`/`scorecard.yml`/`security-scan.yml`; 15 pip installs not hash-pinned. Real, low-blast-radius (GitHub-owned actions are lower risk than third-party; pip installs run in ephemeral CI runners, not production). Not fixed in this phase — bulk-editing every workflow file is exactly the "mechanical change to increase a score" this directive says not to do without a real security problem driving it. |
| `TokenPermissionsID` | 2 | high (Scorecard's own severity label) | **Configuration hygiene, real but narrow.** `ci.yml` and `publish.yml` lack an explicit top-level `permissions:` block, so `GITHUB_TOKEN` gets its repository-default (broader) permission set for those workflows. Legitimate defense-in-depth gap; not release-blocking (no evidence either workflow's steps actually use the token beyond checkout/standard actions). Not fixed in this phase per the freeze — documented for Codex/maintainer decision. |
| `VulnerabilitiesID` | 1 | high | **Real, but a dev-only, no-current-fix npm transitive dependency, not a production Python attack surface.** `GHSA-jmr9-qjv8-65gv` (CVE-2026-56876, `extract-zip` ≤2.0.1, unvalidated symlink path traversal). Traced via `package-lock.json`: `node_modules/extract-zip`, `"dev": true`, pulled in transitively (Puppeteer-style dependency chain: `debug`/`get-stream`/`yauzl`/`extract-zip`) — not a runtime dependency of the deployed Python application, and this project processes no user-supplied zip files. No patched version exists upstream yet (`"patched": null`). Low practical exploitability; real and open, correctly not silently dismissed. |
| `SASTID` | 1 | medium | **Likely stale, not a current gap.** Message: "0 commits out of 30 are checked with a SAST tool." CodeQL genuinely runs on every push/PR to `main` today (confirmed live in §3) — this alert most likely predates `codeql.yml`'s addition (this directive's own Phase 1) and Scorecard has not yet rescanned. Needs a rescan to confirm, not a code fix. |
| `MaintainedID` | 1 | high | **Likely false/noise for this specific check.** Message: "project was created in last 90 days" — contradicted by this repository's own extensive git history (hundreds of commits spanning well over 90 days, visible in `git log`). Consistent with Scorecard measuring GitHub's repository-object creation/rename timestamp rather than actual project age (a known false-positive pattern after a repo rename — this project was previously named `responsible-ai-platform`/`ResponsibleAI`). Not independently confirmed against GitHub's repo-settings API in this pass; flagged as likely noise, not verified as noise. |
| `FuzzingID` | 1 | medium | **Real, already named.** No OSS-Fuzz/ClusterFuzzLite continuous-fuzzing integration exists — distinct from Phase 17's one targeted Hypothesis property test, which Scorecard's check does not detect (it looks for a specific continuous-fuzzing integration, not any property-based test in the repo). Matches `SECURITY_ASSURANCE_CASE.md` §8's own pre-existing statement. |
| `DependencyUpdateToolID` | 1 | medium | **Real.** No Dependabot/Renovate configuration exists — distinct from `dependency-review.yml`, which reviews dependencies *already proposed* in a PR but does not proactively open update PRs. Legitimate, easy-ish fix (`.github/dependabot.yml`), not made in this phase — adding new CI automation during a freeze is a judgment call left to Codex/maintainer, not self-authorized here. |
| `CodeReviewID` | 1 | high | **Real, already known and accepted.** "Found 0/30 approved changesets." Matches the Progress Ledger's own pre-existing note: `required_approving_review_count: 0` accepted as a structural reality of this founder-led, single-maintainer repository (`CODEOWNERS` itself states this isn't a fabricated team), not force-fixed. |

**No dependency, action, or workflow was changed in this pass to
mechanically raise the Scorecard number** — every category above is
triaged with reasoning, and only genuinely release-blocking security
configuration defects would have warranted a fix under the freeze
rules; none of these 58 findings met that bar.

---

## 12. Codex review instruction

**Assume this implementation is insecure until executable evidence
proves otherwise.**

Codex should attempt to falsify, specifically:

- Authority containment (can any path escalate beyond a granted
  `AuthorityContext`?)
- Delegation attenuation (`validate_attenuation()` — can a child
  claim wider authority than its parent?)
- Tenant isolation (can any repository leak across `org_id`?)
- Neural privacy (can N0-N2 data leave local scope without consent —
  noting per §6/§7 that no live code path currently produces or moves
  any real neural data at all, so this is presently a design-level
  question, not a live-exploit one)
- Consent enforcement (`evaluate_neural_data_flow()` — any bypass of
  the fail-closed default?)
- Action binding (`compute_action_digest`/`NeuralIntentAttestation` —
  can a mutated action still pass a stale authorization?)
- Replay resistance (approval/execution-permit/OAuth-state/SAML
  `InResponseTo` reuse)
- Cryptographic isolation (per §4 — is the dormancy of Phase 2's
  scheme itself exploitable, e.g. does any code path assume it's
  active when it isn't?)
- LLM isolation (can attacker-controlled `ActionRequest.arguments`
  influence a governance decision? Proven false in Phases 8/10, but
  Codex should re-attempt, not trust the existing test.)
- Citadel containment (`_validate_authorization()`'s four checks,
  target-fingerprint drift — can any executor be tricked into running
  without them?)
- Audit integrity (can the hash chain be silently regenerated? Proven
  possible by a full-DB-write attacker in Phase 13's own adversarial
  test — the mitigation is external anchoring, which has no automated
  pipeline; see Phase 13's report)
- Fail-closed operation (see §8's matrix — attack the UNTESTED cells
  first)

For every finding, provide: **ID, severity, invariant violated,
affected file, affected function, preconditions, reproduction,
expected behavior, actual behavior, impact, blast radius, whether a
regression test exists, root-cause recommendation.**

See also `docs/enterprise-neural/CODEX_ATTACK_MAP.md` for the
file-by-file starting map.

---

## 13. No merge

**PR #50 has not been merged, auto-merge has not been enabled, and no
push to `main` has occurred as part of this or any prior phase on this
branch.** Claude is the builder; Claude cannot independently certify
this architecture's security. Codex is the next reviewer.
