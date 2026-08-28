# Changelog

All notable changes to this project are documented here.
Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- Enterprise Neural Phase 14 — Resilience + Fail-Closed Operations
  Matrix (2026-08-28) (`tests/test_resilience_fail_closed_matrix.py`)
  — audit-driven, not a rebuild: `THREAT_MODEL.md` already documents
  evidence-write failures failing closed and Trust Index lookups
  failing open, deliberately asymmetric; `TestAuthoritySubsystemCrashFailsClosed`
  already proved `WhitePactRuntimeGateway.evaluate()` crashes fail
  closed too, by simple exception propagation (no try/except needed —
  a crash structurally prevents evidence being written or the executor
  being reached). Auditing `apply_governance()` in full found six more
  repository dependencies called before `evaluate()`
  (`ceiling_repo`, `policy_repo`, `delegation_repo`,
  `workflow_rule_repo`, `autonomy_budget_repo`, `intent_repo`) relying
  on the identical propagation mechanism, none individually
  regression-tested for it. This phase generalizes the existing crash
  test's exact pattern across all six, parametrized: a crash in any
  one never produces the tool's real payload and never fabricates an
  evidence record. Two dependencies (`recent_*_count()` helper calls,
  `evidence_repo.list_recent_actions()`) are only reached under
  additional preconditions the shared parametrized sweep can't cover
  without separate setup — named as a residual gap, not silently
  assumed covered. 6 new tests; full suite 3132 passed, 1 skipped, 0
  failed.

- Enterprise Neural Phase 13 — Immutable Audit + Evidence Anchoring
  Evidence (2026-08-28) (`tests/test_evidence_chain_anchoring.py`) —
  audit-driven, not a rebuild: `ENTERPRISE_SECURITY.md` already
  documents that no hash chain alone can defend against an attacker
  with full DB write access recomputing the entire chain from
  scratch — only external anchoring (periodic publication to
  write-once storage) can. `governance/evidence_bundle.py`'s
  offline-verifiable, digest-bearing bundle export (already real,
  already tested, already API-exposed) already provides exactly the
  artifact such an anchor needs; only the choice of *where* to publish
  it is a real, cloud/infra-specific gap, correctly out of scope
  without an explicit target named. This phase makes the underlying
  claim concrete and reproducible rather than leaving it as prose: (1)
  a full-chain-regeneration attack, simulated by writing directly to
  `governance_evidence` and recomputing every downstream hash, passes
  `EvidenceRepository.verify_chain()` — proving the documented
  limitation is real; (2) a bundle digest captured before the attack
  differs from one captured after, for the identical record range —
  proving the mitigation actually works; (3) a negative control
  confirms two exports of unchanged content produce the identical
  digest, so (1) and (2) aren't artifacts of unrelated digest
  instability. 3 new tests; full suite 3126 passed, 1 skipped, 0
  failed.

- Enterprise Neural Phase 12 — Platform + Network + Service Isolation
  (2026-08-28) (`mcp/server.py`'s `platform_isolation_problems()`) —
  audit-driven: `THREAT_MODEL.md` already documented DNS rebinding
  protection defaulting to disabled for the hosted MCP HTTP/SSE
  transport, application-layer message signing as out of scope
  (TLS-only, deployer responsibility), and per-connection SSE
  DoS protection as not yet built (no config knob to check, named
  rather than papered over). This phase closes the one genuinely
  actionable gap: DNS-rebinding-disabled had no startup-time
  visibility, unlike `dashboard.config.multi_replica_problems()`'s
  existing precedent for exactly this shape of check. New pure
  function `platform_isolation_problems()`, wired into
  `_build_http_app()` to log a warning (not a hard failure, same
  non-blocking posture as the `multi_replica` precedent) when
  transport security ends up disabled. Also corrects a stale
  `THREAT_MODEL.md` claim ("no upstream/third-party MCP proxy executor
  exists yet") that Phase 11 disproved — `UpstreamMCPExecutor` has the
  identical bypass-invariant property, independently tested. 2 new
  tests; full suite 3123 passed, 1 skipped, 0 failed.

- Enterprise Neural Phase 11 — Citadel Execution Containment Evidence
  (2026-08-28) (`tests/test_citadel_execution_containment.py`) —
  audit-driven, not a rebuild: Phase 0's audit flagged execution-permit
  binding as "partially implemented... not yet a general Citadel-style
  containment boundary"; since then, Execution Permit v2 and the JIT
  Credential Broker generalized `ExecutionAuthorization` well beyond
  MCP-mediated internal tool calls to `UpstreamMCPExecutor`
  (target-fingerprint drift detection, per-call narrowly-scoped
  credentials, DNS re-validation before dispatch) — already real,
  already tested. This phase adds regression-tested evidence: every
  concrete `Executor` implementation calls the shared
  `_validate_authorization()` (exactly two call sites, both known);
  `check_target_fingerprint()` has exactly one call site
  (`upstream_executor.py` — `InternalToolExecutor` correctly never
  calls it); a fresh authorization with no target fingerprint never
  raises `AuthorizationTargetDriftError` through the real
  `InternalToolExecutor`; and the shared replay/mismatch protections
  hold identically on both executors, proven independently rather than
  assumed to transfer. Also confirms `mcp/server.py`'s second
  `dispatch_tool()` call site is the already-documented, correctly
  out-of-scope ungoverned-stdio-transport path (Phase 8 Gap 1 / Phase
  10 Gap 2), not a new bypass. 7 new tests; full suite 3121 passed, 1
  skipped, 0 failed.

- Enterprise Neural Phase 10 — Brain Policy + Risk Engine Evidence
  (2026-08-28) (`tests/test_brain_policy_risk_boundary.py`) —
  audit-driven, not a rebuild: SPEC.md §2.5 already names "the Brain"
  as the existing `governance/gateway.py` risk-classification +
  policy-evaluation pipeline, and `gateway.py`'s own docstring already
  labels those steps "Phase 9" (`risk.py`) and "Phase 10"
  (`policy.py`) — real, persisted (`db/policy_repository.py`), tested
  (41 pre-existing direct tests), and unconditionally wired into both
  live governed-call paths (`mcp/governance_integration.py`,
  `mcp/upstream_dispatch.py`). This phase adds regression-tested
  evidence: `Policy.evaluate()` has exactly one call site
  (`gateway.py`); `classify_action_risk()` has exactly the three
  audited call sites; every `DecisionResult` the gateway produces
  carries a real `RiskTier`; a matching `Policy` rule actually gates
  the outcome through the real gateway; and an attacker-controlled
  `ActionRequest.arguments` payload shaped to look like a risk/policy
  override has zero effect on either. 13 new tests, 100% coverage on
  the exercised modules; full suite 3114 passed, 0 failed.
- Enterprise Neural Phase 8 — LLM + Agent Security Boundary Evidence
  (2026-08-28) (`tests/test_llm_agent_security_boundary.py`) —
  audit-driven, not a rebuild: most of the directive's "LLM must never
  issue authority or create execution permits" requirements already
  held structurally, built under prior initiatives. This phase adds
  regression-tested evidence rather than new architecture: structural
  guards confirming `ExecutionAuthorization` and `AuthorityGrant` each
  have exactly one gated construction site in the real, shipped source
  tree, and `mint_neural_intent_attestation` has zero call sites
  outside its own module; runtime tests confirming
  `authorize_execution()` requires a real `DecisionResult` from the
  governance gateway and ignores attacker-controlled
  `ActionRequest.arguments` entirely, even a payload crafted to look
  like a decision object. Two genuine, pre-existing gaps named
  explicitly rather than silently left implicit: the self-hosted stdio
  MCP transport remains ungoverned (no organizational identity to
  evaluate against), and LLM-supplied tool arguments aren't schema-
  validated before reaching governance — both correctly out of this
  phase's scope (each is a separate, larger initiative). 7 new tests.
  Full suite: 3102 passed, 0 failed.

- Enterprise Neural Phase 7 — Neural Intent Attestation + Action
  Binding (2026-08-28) (`governance/neural/attestation.py`) —
  `NeuralIntentAttestation`, minted and verified via
  `governance/crypto`'s existing signing primitives (a new
  `KeyPurpose.NEURAL_ATTESTATION` value, additive), implementing the
  directive's mutation-invalidates-authorization property literally:
  `verify_neural_intent_attestation` compares the attestation's stored
  action digest against the digest of what's actually about to
  execute and rejects on any mismatch — changing the amount, the
  recipient, or the purpose after attestation invalidates it.
  Fail-closed verification order (signature → expiry → mutation →
  embedded decision status), so a forged attestation never reaches the
  later checks. Unlike Phases 5/6, this is fully implemented and
  tested end-to-end (not merely a typed contract) — attestation is a
  pure transformation over already-typed objects, not hardware- or
  model-dependent. 24 new tests (2 Hypothesis property tests,
  including the literal ₹1,000→₹100,000 and recipient-A→B scenarios
  the directive names), 100% coverage. Full suite: 3095 passed, 0
  failed.

- Enterprise Neural Phase 6 — Neural Signal Integrity + Decoder Safety
  (2026-08-28) (`governance/neural/decision.py`) — `NeuralDecision`
  (every field the directive requires: schema version, calibrated
  probability, uncertainty, signal quality, decoder/calibration
  identity+version+hash, subject/session/device context, expiry) with
  `__post_init__` rejecting NaN, +/-Infinity, out-of-range confidence
  values, and non-increasing expiry unconditionally.
  `NeuralDecisionStatus` (VALID/AMBIGUOUS/REJECTED) and
  `classify_decision_status()` (checks uncertainty before probability,
  so genuine uncertainty is AMBIGUOUS rather than a misleading
  REJECTED), plus `is_expired`/`matches_context`/`is_stale_decoder`.
  Deliberately **no decoder** — same reasoning as Phase 5: no real
  trained model or device signal exists to validate one against. 40
  new tests (3 Hypothesis property tests), 100% coverage. Full suite:
  3069 passed, 0 failed.

- Enterprise Neural Phase 5 — BCI Device Trust + Capability Contract
  (2026-08-28) (`governance/neural/device.py`) — `DeviceTrustLevel`
  (TRUST_A-D), `CapabilityState` (VALIDATED/EXPERIMENTAL/UNAVAILABLE),
  `NeuralCapabilityManifest` (validates channel count, sampling rate,
  and a trust-capability ceiling at construction — a `TRUST_D`
  device's manifest cannot claim any capability `VALIDATED`, since an
  unverified transport gives no basis for that measured-confidence
  claim), and the `BCIDeviceAdapter` `Protocol`. Deliberately adds
  **no** BrainFlow/LSL/vendor-SDK dependency and **no concrete device
  adapter** — with no real device or vendor decision to validate
  against, building one now would be exactly the kind of fabricated
  capability claim the directive prohibits. 18 new tests (3 Hypothesis
  property tests), 100% coverage. Full suite: 3028 passed, 0 failed.

- Enterprise Neural Phase 4 Step 2 — Neural Vault Persistence
  (2026-08-28) (`db/neural_vault_repository.py`, migration `0031`) —
  `NeuralConsentRepository` (append-only consent ledger, revocation
  inserts a new version rather than mutating) and `NeuralVaultRepository`
  (Vault index storing metadata/references, never raw N0/N1/N2 content —
  `NeuralVaultEntry` has no payload field at all, an architectural
  enforcement, not a convention). Soft-delete semantics kept explicit
  per the design doc's "deletion semantics must be explicit"
  requirement. 17 new tests, 100% coverage. Migration verified via a
  real `alembic upgrade head`/`downgrade -1`/`upgrade head` cycle. Full
  suite: 3009 passed, 0 failed.

- Enterprise Neural Phase 4 — Neural Data Classification + Consent
  Policy (2026-08-28) (`governance/neural/`, new subpackage; see
  `docs/enterprise-neural/04_PHASE4_DESIGN.md`) — the N0-N5
  `NeuralDataClass` classification vocabulary, `NeuralPayload` (a
  mandatory-classification wrapper whose `__repr__` never renders raw
  payload bytes, closing the accidental-log-leak class of risk), the
  8-category `ConsentCategory`/`ConsentRecord` model (no blanket "I
  agree" — each category granted/revoked independently), and
  `evaluate_neural_data_flow()`, a fail-closed consent policy
  evaluator (missing or revoked consent → DENY, "latest version wins"
  resolution). 26 new tests (2 Hypothesis property tests), 100%
  coverage, exported from `governance/__init__.py` as `neural`. This
  is Step 1 of Phase 4's build — the Neural Vault persistence layer
  and end-to-end leakage tests remain. Net-new product surface: zero
  neural/BCI code existed before this phase.

- Enterprise Neural Phase 2 Step 5 — Generalized Rotation Script,
  Phase 2 complete (2026-08-28)
  (`scripts/rotate_field_encryption_key.py`) — the existing legacy
  Fernet rotation script now also supports migrating to, or rotating
  within, the new `governance/crypto` scheme via `RAI_ROOT_KEY`,
  reusing its original sweep logic unchanged (proof Step 3's
  dual-scheme `EncryptedString` design needed zero changes to support
  this). A real data-corruption risk was found and fixed before this
  landed: running the migration without also keeping the legacy
  `RAI_FIELD_ENCRYPTION_KEY` set would silently re-encrypt
  still-undecrypted legacy ciphertext as if it were plaintext,
  double-wrapping it. A pre-flight check now refuses to proceed when
  it detects this condition. 11 new tests plus full manual CLI
  verification against a real `alembic`-migrated database (both the
  refusal and success paths). Full suite: 2965 passed, 0 failed. This
  closes Phase 2 (Cryptographic Foundation + Key Management) — all 5
  implementation steps complete; see
  `docs/enterprise-neural/02_PHASE2_STEP5_REPORT.md`'s final verdict
  for what the phase does and does not deliver (the key-management
  foundation is real and tested; nothing in the running application
  activates it yet — that remains a separate, unscheduled step).

- Enterprise Neural Phase 2 Step 4 — Canonical Signing + SAML Session
  Key Rotation (2026-08-28) (`governance/crypto/signing.py`,
  `auth/saml.py`) — `sign()`/`verify()`, an HMAC-SHA256 helper binding
  `KeyId` into the signed material, and SAML session-token signing
  (`mint_session_token`/`validate_session_token`) wired onto it via
  `configure_session_signing_key()`, alongside the legacy
  `SAMLConfig.session_secret` path. **Scope correction from the
  original design doc**, found by reading `webhooks/manager.py`'s
  actual secret-sharing model before implementing: the design doc's
  Sec 3.11 treated webhook payload signing the same as SAML session
  signing, but a webhook's HMAC secret is shared with an external
  receiver (Slack, PagerDuty, a customer endpoint) — WhitePact
  rotating it internally without the receiver rotating in lockstep
  would silently break their signature verification. Webhook signing
  is deliberately **not** wired onto this scheme; SAML session tokens
  (signed and verified entirely within this codebase) are a correct
  fit. 6 new tests, 100% coverage on the new module. Full suite: 2954
  passed, 0 failed.

- Enterprise Neural Phase 2 Step 3 — Field Encryption Dual-Scheme
  Wiring (2026-08-28) (`db/encryption.py`) — `EncryptedString` now
  supports the new `governance/crypto`-based envelope scheme
  alongside legacy `RAI_FIELD_ENCRYPTION_KEY` Fernet, activated via
  `configure_field_encryption_key()`. Format detection uses an
  explicit, versioned string prefix (`"wpcrypto2:"`), not a
  structural guess. Two real bugs found and fixed before merge: the
  first design attempt detected format by decoding stored values as
  base64 and checking a byte — running the full regression suite
  surfaced 12 failures, because base32 TOTP secrets
  (`pyotp.random_base32()`) use an alphabet that's a strict subset of
  base64's at a block-aligned length, so genuine plaintext TOTP
  secrets "successfully" decoded as base64 and were misidentified as
  ciphertext, breaking every MFA flow. Replaced with the explicit
  prefix. Separately, `governance/crypto/envelope.py`'s
  `decode_envelope()` was found to decode leniently
  (`validate=False`, Python's base64 default) rather than strictly,
  silently discarding invalid characters instead of rejecting
  malformed input — fixed to decode strictly. 13 new/updated tests,
  100% coverage on `db/encryption.py`. Full suite: 2949 passed, 0
  failed. Application-startup wiring to actually activate the new
  scheme in production is explicitly out of scope for this step — see
  `docs/enterprise-neural/02_PHASE2_STEP3_REPORT.md`.

- Enterprise Neural Phase 2 Step 2 — Persistent Key Store (2026-08-28)
  (`db/crypto_key_repository.py`, migration `0030`) — `CryptoKeyRepository`,
  a DB-backed `WrappedKeyStore` (`governance/crypto/provider.py`)
  replacing Step 1's `InMemoryWrappedKeyStore` for real deployments.
  `key_id` (the canonical `KeyId.to_string()` encoding) is the table's
  primary key, so a concurrent write racing to generate the same
  purpose/tenant/environment/version now hits a real database
  uniqueness constraint and raises `KeyVersionConflictError` instead
  of silently overwriting — closing the concurrency-safety residual
  risk Step 1's report flagged. Fixed a real bug caught by `mypy`
  before merge: `LocalEnvelopeKeyProvider`'s `store` constructor
  parameter was over-narrowed to `InMemoryWrappedKeyStore | None`
  instead of the `WrappedKeyStore` Protocol, which would have
  rejected any conforming store (including this one) at the type level
  — defeating the entire point of the abstraction Step 1 built.
  15 new tests (repository CRUD/query contract, tenant/environment
  isolation, and end-to-end `LocalEnvelopeKeyProvider` behavior wired
  onto the DB-backed store, including persistence across separate
  repository instances against the same DB — simulating a process
  restart), 100% coverage on the new repository. Migration verified to
  apply and reverse cleanly via a real `alembic upgrade head` /
  `downgrade -1` / `upgrade head` cycle against a fresh SQLite DB, not
  just via the test suite's `metadata.create_all()` path. Exported
  from `db/__init__.py`. Nothing in the existing codebase writes to
  this table yet — wiring `db/encryption.py`, `webhooks/manager.py`,
  and `auth/saml.py` onto this provider is still a later Phase 2 step.

- Enterprise Neural Phase 2 Step 1 — Cryptographic Foundation, Key
  Management package (2026-08-28) (`governance/crypto/`, new
  subpackage; see `docs/enterprise-neural/02_PHASE2_DESIGN.md` for the
  full design) — `KeyId`/`KeyPurpose`/`KeyStatus` key-hierarchy
  vocabulary, the `KeyProvider` Protocol every future call site
  (`db/encryption.py`, `webhooks/manager.py`, `auth/saml.py`) is meant
  to depend on rather than a concrete provider, and the one
  production-capable implementation this phase builds:
  `LocalEnvelopeKeyProvider` — real envelope encryption (HKDF-derived
  per-purpose/tenant KEK wraps random DEKs via AES-256-GCM), not a
  fake KMS. Self-describing encrypted envelope format
  (`governance/crypto/envelope.py`) binds its `KeyId` into the AEAD
  authentication tag, so tampering with the embedded key identity
  breaks decryption the same as tampering with ciphertext. Two real
  bugs found and fixed during property testing before merge: a
  `KeyId` string encoding where an actual tenant named `"-"` or
  containing a NUL byte collided with reserved sentinels, and a
  version-numbering bug where retiring or revoking a key outside of
  `rotate()` could cause the next `get_encryption_key()`/`rotate()`
  call to silently regenerate and overwrite an existing key version's
  wrapped DEK. 47 new tests (2 Hypothesis property tests, explicit
  misuse-test coverage for corrupted ciphertext, tampered AAD, wrong
  tenant/purpose keys, revoked/retired-key distinction, malformed
  envelopes, and no-secret-leakage-in-errors), 100% coverage on the
  new package, exported from `governance/__init__.py` as `crypto`.
  Wiring existing call sites onto this provider and the persistent
  `crypto_keys`-table-backed `WrappedKeyStore` are later Phase 2 steps
  — this step ships only the package, Protocol, and the in-memory
  store (explicitly non-persistent, documented as dev/test-only).
- Heart → WhitePact Production Integration, Phase 2 — Identity
  Adapter (2026-08-26) (`governance/identity_authority_adapter.py`)
  — the boundary between real, already-live authentication (static
  API key, OIDC JWT, VC-JWT) and the Heart's own `RootAuthorityRecord`
  vocabulary. Deliberately conservative, fail-safe mapping:
  `IdentityContext.kind` `"human"`/`"api_key"` (org-admin-provisioned)
  map to a terminal `RootType`; every other kind — including the
  ambiguous `"oidc"` (no discriminator today between human-SSO and
  machine client-credentials tokens) — maps to a non-terminal type
  requiring a resolvable `authority_source` chain before
  `validate_root_chain()` (H3) will ever report `VALID`. Producing a
  record here proves nothing about legitimate authority by itself —
  authentication is not authority, the separation this whole phase
  exists to keep explicit. 19 new tests (4 Hypothesis property tests),
  100% coverage, exported from `governance/__init__.py`.
- Heart → WhitePact Production Integration, Phase 1 — Authority
  Contract (2026-08-26) (`docs/heart-production/`, new initiative,
  distinct from the completed Heart library initiative) — Phase 0
  (`docs/heart-production/00_CURRENT_RUNTIME_MAP.md`) audits the
  current live decision path with file:line citations: confirms
  `AuthorityContext` is synthesized fresh from authentication alone on
  every governed call (`mcp/governance_integration.py:247-252`), never
  from a proof of legitimate authority — authentication is being used
  as authorization today. Identifies the exact Heart insertion point:
  the continuous delegation re-check block already ahead of
  `gateway.evaluate()` in `apply_governance()`. Phase 1
  (`governance/authority_grant.py`, `docs/heart-production/01_AUTHORITY_CONTRACT.md`):
  `AuthorityGrant` — the canonical boundary object bundling the
  Heart's `AuthorityEnvelope` (what's granted, H2) and
  `LegitimacyEnvelope` (why it's legitimate, H12) with minimal
  request-context, with every field classified as an authenticated
  fact, user-provided claim, or verified authorization fact.
  `effective_authority`/`legitimacy` are never derived from the
  unverified `requested_*` fields. `to_authority_context()` reuses the
  existing H2 `envelope_to_authority_context()` adapter unmodified —
  `gateway.evaluate()` itself is not touched. 12 new tests (2
  Hypothesis property tests), 100% coverage, exported from
  `governance/__init__.py`.
- WhitePact Heart / Sovereignty Kernel, Phases H0-H2 (2026-08-25) — a
  new, deliberately small trusted-computing-base layer beneath the
  existing governance code, answering "why does this machine have the
  legitimate right to exercise this authority at all," logically prior
  to `WhitePactRuntimeGateway.evaluate()`. Phase H0
  (`docs/heart/HEART_CURRENT_STATE.md`) audits every existing
  authority component before any new code, confirming no root-of-trust
  concept, unified revocation epoch, or immutable versioned
  constitution exists today. Phase H1
  (`governance/constitution.py`): `AuthorityConstitutionVersion` — a
  versioned, canonicalized, historically-immutable set of fifteen
  constitutional laws (H1-H15), distinct from the existing,
  deliberately org-mutable `Policy`. `_CONSTITUTION_HISTORY` is a
  `MappingProxyType` — mutation attempts raise `TypeError`, a real
  enforced guarantee. Deliberately not cryptographically signed
  (`docs/heart/HEART_SIGNING_DECISION.md`). Phase H2
  (`governance/authority_lattice.py`): `AuthorityEnvelope` — fifteen
  explicit authority dimensions with deterministic `compare_envelopes()`
  (`LEGITIMATE_SUBSET`/`ESCALATION`/`UNREPRESENTABLE_CONSTRAINT`, never
  a bare boolean) and `intersect_envelopes()` (never widens through
  union). Also closes a real, previously-documented gap in existing,
  live-used code: `validate_attenuation()` (`governance/models.py`)
  never checked `allowed_hours_utc` for attenuation — fixed directly.
  A second real bug — a naive hour-window-intersection reconstruction
  that could silently widen access for disjoint wraparound overlaps —
  was caught by a Hypothesis property test on its first run and fixed
  with a self-verifying construction before merge. These phases ship
  the constitution and lattice objects only — no wiring into the live
  decision path beyond the one attenuation fix, no other change to
  existing governance behavior. 60 new tests total
  (`tests/test_constitution.py`, `tests/test_authority_lattice.py`,
  5 new cases in `tests/test_authority_attenuation.py`), including
  Hypothesis property tests. Phases H3-H17 (root of authority, consent
  proof, purpose binding, revocation epoch, the Heart veto itself,
  formal/adversarial verification, performance, enterprise hardening)
  are real, separately-scoped future work, not claimed complete here.
- WhitePact Heart Phase H3 — Root of Authority (2026-08-26)
  (`governance/root_authority.py`, new file) — the first executable
  form of constitutional laws H1 ("every machine authority has a
  legitimate root") and H2 ("machines cannot originate authority").
  `RootType` distinguishes terminal roots (`HUMAN`, `ORGANIZATION`)
  from non-terminal ones (`SERVICE_PRINCIPAL`, `WORKLOAD_IDENTITY`)
  that must chain, via `authority_source`, to a terminal root.
  `validate_root_chain()` walks that chain against an abstract
  `RootResolver` (no `db.*` dependency, continuing H1/H2's
  TCB-minimization discipline), returning an explicit
  `RootValidationStatus` for every failure mode —
  `ROOT_TYPE_CANNOT_SELF_ORIGINATE`, `SOURCE_NOT_FOUND`,
  `CYCLE_DETECTED`, `CHAIN_TOO_DEEP`, `REVOKED`, `NOT_YET_VALID`,
  `EXPIRED` — never silently treating an unresolved or invalid chain
  as legitimate. A real bug found during self-review before any test
  existed: the first draft conflated an intermediate ancestor's
  *type* with its *temporal validity* when deciding a failure status,
  which would have misreported a revoked ancestor with a status
  implying its type was the defect rather than its revocation — fixed
  and permanently regression-tested. 34 new tests
  (`tests/test_root_authority.py`, including 4 Hypothesis property
  tests), 100% branch coverage on the new module. No DB persistence
  layer and no wiring into the live decision path yet — ships the
  validated domain object and algorithm only, same pattern as H1/H2.
- WhitePact Heart Phase H4 — Consent Proof (2026-08-26)
  (`governance/consent_proof.py`, new file) — a structured,
  digest-bound record that a specific human (or otherwise-legitimate
  root) actually consented to a specific grant of authority, for a
  specific purpose, distinguishable from mere authentication.
  `ConsentMethod` names how consent was captured (explicit UI action,
  signed document, recorded verbal consent, authenticated API call, or
  standing delegated policy) with no default value. `validate_consent_proof()`
  composes with Phase H3 by taking an already-computed
  `RootValidationResult` as a parameter rather than resolving the root
  chain itself, keeping zero runtime dependency on `root_authority.py`.
  Root legitimacy is checked before the proof's own temporal state, so
  an illegitimate root is never masked by also reporting independent
  expiry. 21 new tests (`tests/test_consent_proof.py`, including 3
  Hypothesis property tests), 100% branch coverage on the new module.
  No DB persistence layer and no wiring into the live decision path
  yet — ships the validated domain object and algorithm only.
- WhitePact Heart Phase H5 — Purpose Binding (2026-08-26)
  (`governance/purpose_binding.py`, new file) — the executable form of
  constitutional law H4 ("authority remains bound to purpose").
  Absorbs the existing `governance/intent.py` `IntentContract` by
  reference (`intent_ref`) rather than duplicating its purpose-scoping
  logic, per `docs/heart/HEART_CURRENT_STATE.md` §4. The genuinely new
  piece: ties a declared `IntentContract` to the exact `ConsentProof`
  (Phase H4) that authorized it via `consent_ref`, with purpose
  matching required to be exact-string (never semantic), mirroring
  `IntentContract.goal`'s own "never machine-parsed" precedent.
  `validate_purpose_binding()` composes with H4 by taking an
  already-computed `ConsentValidationResult` as a parameter, keeping
  zero runtime dependency on `consent_proof.py`/`intent.py`. Check
  ordering (`CONSENT_MISMATCH` before `PURPOSE_MISMATCH` before
  `INTENT_MISMATCH`) is deliberate and tested, so the most fundamental
  problem always surfaces first. 17 new tests
  (`tests/test_purpose_binding.py`, including 3 Hypothesis property
  tests), 100% branch coverage on the new module. No DB persistence
  layer and no wiring into the live decision path yet.
- WhitePact Heart Phase H6 — Delegation Kernel (2026-08-26)
  (`governance/delegation_kernel.py`, new file) — composes the three
  independent Heart legitimacy checks from H3-H5 (root, consent,
  purpose) with a `DelegationRecord`'s own active/revoked/expired
  state into one verdict (`DelegationLegitimacyStatus`). Reuses
  `DelegationRecord`/`DelegationRepository`/`DelegationGraph` as-is,
  per `docs/heart/HEART_CURRENT_STATE.md` §3's REUSE classification —
  no delegation data model changes. The genuinely new piece: even a
  well-formed, correctly-attenuated delegation says nothing about
  whether the delegator's own authority traces to a legitimate root,
  was actually consented to, and stays bound to its declared purpose;
  this module is the composition point for those three answers.
  Ordering (root → consent → purpose → the delegation's own state)
  mirrors H4/H5's established "upstream legitimacy before local state"
  principle. Documents an honest limitation: `DelegationRecord` has no
  field cross-referencing the specific root/consent/purpose objects
  behind it, so this module cannot verify the three results supplied
  actually pertain to the delegation in question — that's the
  caller's responsibility, stated explicitly rather than assumed. 12
  new tests (`tests/test_delegation_kernel.py`, including 2 Hypothesis
  property tests), 100% branch coverage on the new module. No DB
  persistence layer and no wiring into the live decision path yet.
- WhitePact Heart Phase H7 — Non-Delegable and Human-Reserved
  Authority (2026-08-26) (`governance/non_delegable_authority.py`,
  new file) — the executable form of constitutional law H11
  ("non-delegable authority remains non-delegable"). A fixed,
  Heart-owned registry maps action-type `fnmatch` patterns (reusing
  `IntentContract`'s own pattern-matching mechanism) to
  `NON_DELEGABLE` (can never appear in any delegated grant — amending
  the constitution, issuing/revoking a root of authority, overriding a
  Heart veto) or `HUMAN_RESERVED` (may be delegated to initiate, but
  execution must always require a human in the loop, unconditionally).
  Deliberately narrow — only meta-level operations that would let a
  delegate undermine the Heart's own guarantees are reserved; ordinary
  business-domain action types stay governed by existing org policy.
  `NON_DELEGABLE` always wins when both severities match, property-
  verified. 13 new tests (`tests/test_non_delegable_authority.py`,
  including 3 Hypothesis property tests), 100% branch coverage.
  Deliberately standalone this phase — not yet called from H6's
  `validate_delegation_legitimacy()` or any live decision path, named
  explicitly as a remaining risk.
- WhitePact Heart Phase H8 — Authority Lifetime (2026-08-26)
  (`governance/authority_lifetime.py`, new file) — the executable form
  of constitutional laws H13 ("historical authorization does not
  imply current authorization") and H14 ("material authority mutation
  requires reauthorization"). None of the four Phase H3-H6 verdict
  types carry an evaluation timestamp, so nothing stops a caller from
  treating a computed verdict as permanently true. `check_lifetime()`
  answers two independent staleness questions: `STALE_BY_MUTATION`
  (the underlying object's `canonical_digest` changed since
  evaluation, checked first) and `STALE_BY_AGE` (older than a
  `LifetimeWindow`, checked second) — generalizing the existing, live
  "continuous re-authorization" pattern from one object type to all
  four Heart verdict types. Named default windows (24h/24h/1h/5min for
  root/consent/purpose/delegation) are suggestions, not enforced.
  Deliberately never re-runs validation itself. 16 new tests
  (`tests/test_authority_lifetime.py`, including 3 Hypothesis property
  tests), 100% branch coverage. One real test-authoring bug caught by
  the property test's own shrinker (float-rounding noise at an exact
  boundary), not by inspection. Deliberately standalone — not yet
  called from any H3-H6 function or live decision path.
- WhitePact Heart Phase H9 — Revocation Kernel (2026-08-26)
  (`governance/revocation_kernel.py`, new file) — `RevocationEpoch`, a
  monotonically increasing counter per `(organization_id, scope)`
  closing the one confirmed gap in this codebase's revocation story:
  five independent mechanisms (delegation cascading revocation and
  expiry, Authority Passport revocation and drift detection, API key
  revocation) share no counter. `check_revocation_epoch()` turns "has
  anything been revoked since I was issued" into one integer
  comparison. None of the five existing mechanisms are refactored;
  this phase does not decide what bumps which scope's epoch, deferred
  as integration work. 15 new tests (`tests/test_revocation_kernel.py`,
  including 3 Hypothesis property tests), 100% branch coverage. Also
  closes a second named gap: `revoke_branch()`'s cascading revocation
  had no dedicated concurrency test or latency measurement. 4 new
  tests added to `tests/test_concurrency.py`, including one genuine
  race-condition finding (concurrent `revoke_branch()` calls on the
  same identity can each report having revoked it, though the database
  itself ends up correctly revoked) and one confirmed protection (a
  `grant()` racing its parent's `revoke_branch()` is correctly
  rejected, not allowed to orphan an active child).
- WhitePact Heart Phase H10 — Authority Conflict Resolver (2026-08-26)
  (`governance/authority_conflict_resolver.py`, new file) —
  `resolve_authority_conflicts()`, the single point that decides, when
  several of the independent Phase H3-H9 legitimacy checks are
  available for the same authority decision and they disagree, which
  verdict wins. Fixed precedence, most severe first: `NON_DELEGABLE`
  (H7) → `REVOKED` (H9) → `ROOT_NOT_LEGITIMATE` (H3) →
  `CONSENT_NOT_LEGITIMATE` (H4) → `PURPOSE_NOT_BOUND` (H5) →
  `DELEGATION_NOT_LEGITIMATE` (H6) → `STALE` (H8) → `LEGITIMATE`. Every
  input is optional — `None` means "not evaluated," never "failed."
  `human_reserved` is a separate, non-blocking signal surfaced
  alongside the overall status. Deliberately never calls any of the
  seven H3-H9 functions itself, keeping zero runtime dependency on any
  of them. 18 new tests (`tests/test_authority_conflict_resolver.py`,
  including 2 Hypothesis property tests), 100% branch coverage. Not
  yet wired into any live decision path with real inputs.
- WhitePact Heart Phase H11 — Heart Veto (2026-08-26)
  (`governance/heart_veto.py`, new file) — the first Heart module
  whose entire purpose is to have real teeth rather than only report a
  status. `apply_heart_veto()` derives a `HeartVetoRecord` from an
  already-computed `ConflictResolutionResult` (H10) — any status other
  than `LEGITIMATE` vetoes. `enforce_heart_veto()` raises
  `HeartVetoError` for a vetoed record and is a no-op otherwise, with
  no parameter of any kind that could suppress, downgrade, or bypass a
  veto — verified structurally by inspecting the function's actual
  signature, not just claimed in a docstring. A vetoed record can only
  become not-vetoed by re-running `apply_heart_veto()` against a
  genuinely different, freshly-legitimate `ConflictResolutionResult`.
  `human_reserved` (H7) passes through unchanged regardless of veto
  outcome. 17 new tests (`tests/test_heart_veto.py`, including 3
  Hypothesis property tests), 100% branch coverage. Not yet wired into
  any live decision path — the veto has no teeth in production until
  something calls `enforce_heart_veto()`.
- WhitePact Heart Phase H12 — Legitimacy Envelope (2026-08-26)
  (`governance/legitimacy_envelope.py`, new file) — the single,
  portable, digestible artifact that packages the Heart's final
  verdict (H11's `HeartVetoRecord`) into an exportable object with an
  identity (`envelope_id`), context (`organization_id`/
  `subject_identity_id`), a timestamp, and a `canonical_digest` — the
  same shape every other Heart record type (H1, H3, H4, H5) already
  has. Wraps the already-final `HeartVetoRecord` rather than
  re-embedding the seven individual upstream H3-H9 results, since the
  veto already is H10's precedence-resolved answer. `explain()`
  reuses the established deterministic-explanation pattern
  (`explain_constitution()`, `explain_authority()`) — a plain
  structured dict, never an LLM call. 13 new tests
  (`tests/test_legitimacy_envelope.py`, including 3 Hypothesis
  property tests), 100% branch coverage. Completes the full H3-H12
  chain of individually-tested, individually-composable Heart
  primitives; only the entry point (H13) remains before this
  first-version Heart is minimally end-to-end wireable.
- WhitePact Heart Phase H13 — Sovereignty Kernel Entry Point
  (2026-08-26) (`governance/sovereignty_kernel.py`, new file) — the
  first, and so far only, place in this codebase that actually calls
  the H3-H12 Heart functions together, for one real request, and
  returns one `LegitimacyEnvelope`. `evaluate()` runs whichever of the
  applicable H3-H9 checks the supplied inputs (root/consent/intent/
  purpose_binding/delegation/requested_action_types/revocation epoch)
  make possible, skipping any whose prerequisites are missing, then
  composes them via H10, applies the H11 veto, and wraps the result in
  H12's envelope. Partial input is a first-class case, not degraded
  behavior. The default `RootResolver` fails closed. 18 new tests
  (`tests/test_sovereignty_kernel.py`, including 3 Hypothesis property
  tests), 100% statement coverage. One real test-authoring bug caught
  by the test itself failing on first run, fixed before merge. The
  Heart's full H3-H13 chain is now, for the first time, minimally
  end-to-end wireable in one call — still not wired into any live
  decision path.
- WhitePact Heart Phase H14 — Formal and Property-Based Assurance
  (2026-08-26) (`docs/heart/HEART_INVARIANTS.md`,
  `tests/test_heart_formal_properties.py`, new files) — an honest
  ledger of every invariant claimed by Phases H1-H13, each paired with
  the test that verifies it, with unverified claims (the H6/H10
  cross-reference gaps) marked explicitly rather than omitted. Adds 4
  cross-cutting property tests spanning the full H3-H13 chain that no
  single phase's own tests could exercise: `evaluate()` is always
  consistent with manually composing H10+H11; denial is monotonic
  (adding any blocking condition to a legitimate chain always flips
  the result); every canonical-digest function across the Heart is
  sensitive to every one of its own fields; `is_legitimate` is a pure
  function of the supplied verdicts, independent of each record's
  non-deterministic identity fields. 12 new tests, `mypy`/`ruff check`/
  `ruff format --check` clean. No new `src/` module — verification
  work only. Explicitly not formal (TLA+/Coq-grade) verification,
  stated plainly rather than approximated by property testing alone.
- WhitePact Heart Phase H15 — Adversarial Heart Gauntlet (2026-08-26)
  (`tests/test_heart_adversarial_gauntlet.py`, new file) — deliberately
  attacked the Heart's own assumptions and found two real
  vulnerabilities, both fixed. **Cross-reference confusion**: a
  `DelegationRecord` for a completely unrelated identity and purpose,
  supplied alongside a genuinely legitimate but unrelated root/consent/
  purpose chain, validated as `LEGITIMATE` end-to-end via `evaluate()`
  (H13) — fixed by adding optional `expected_subject_identity_id`/
  `expected_purpose` cross-reference parameters to
  `validate_delegation_legitimacy()` (`governance/delegation_kernel.py`,
  H6), producing a new `DELEGATION_MISMATCH` status, now wired from
  `evaluate()`; backward-compatible (both default to `None`).
  **Case-relabeling bypass**: `check_non_delegable_authority()`
  (`governance/non_delegable_authority.py`, H7) relied on
  `fnmatch.fnmatch()`'s platform-dependent case sensitivity, so a
  request for `"HEART.VETO.OVERRIDE"` silently evaded the all-lowercase
  registry — fixed by explicitly `.casefold()`-ing both sides before
  comparison. Also confirms three protections hold (exact chain-depth
  boundary, purpose-matching resistance to whitespace/Unicode
  homoglyph tricks) and names one accepted design tradeoff
  (revocation-epoch checking trusts its caller-supplied `current`
  input, a deliberate TCB-minimization consequence, not a bug). 13
  new tests; `delegation_kernel.py`/`non_delegable_authority.py`/
  `sovereignty_kernel.py` all remain at 100% coverage.
  `docs/heart/HEART_INVARIANTS.md` updated to reflect the narrowed
  (not eliminated) H6 cross-reference gap.
- WhitePact Heart Phase H16 — Performance (2026-08-26)
  (`docs/heart/HEART_PERFORMANCE.md`, `tests/test_heart_performance.py`,
  new files) — the first latency/throughput baseline for the Heart's
  hot paths, measured on one development machine (explicitly not a
  tuned SLA). `evaluate()` (H13) and `validate_root_chain()` (H3) are
  fast and roughly constant-cost (~17us/call, ~58,000 calls/sec
  single-threaded) — the dominant cost is Python call overhead, not
  the comparison logic. One real, documented scaling characteristic
  found (not a bug): `check_non_delegable_authority()` (H7) is
  O(action_types × registry size) in the worst case, ~4.35ms for a
  1000-entry action-type set with no match — not currently reachable
  by any code path in this codebase, but flagged for future callers.
  5 new tests with generous (10-250x baseline) regression-guard
  bounds, matching H9's own established latency-test philosophy.
  Explicitly does not measure concurrent throughput, live-path (DB/
  network) latency, or memory usage.
- WhitePact Heart Phase H17 — Enterprise Hardening (2026-08-26, FINAL
  PHASE — completes the WhitePact Heart / Sovereignty Kernel
  initiative, H0-H17) — found and fixed a real hardening gap: none of
  the 13 Heart modules (H1-H13) were re-exported from
  `governance/__init__.py`, inconsistent with every other governance
  type in the package. Fixed by adding all 13 modules' public API to
  `governance/__init__.py`'s imports and `__all__`, with
  `sovereignty_kernel` exported as a module (matching the `sk.evaluate(...)`
  convention this session's own test suites already used). Adds
  `docs/heart/HEART_ENTERPRISE_READINESS.md`, the closing document for
  the full initiative: a table of every phase's deliverable, a list of
  all six real bugs found and fixed across H0-H17, an explicit list of
  everything not done (no live wiring, no persistence layer, no real
  identity/consent integration, no formal verification, the still-open
  root/consent cross-reference gap), and a final verdict — complete as
  a verified, composable authority-legitimacy library; not yet a
  production authority system. 15 new tests in
  `tests/test_governance_package_exports.py` confirming every Heart
  symbol is reachable via package-level imports and a full Heart
  decision works end-to-end without touching internal submodule
  paths. No import cycle introduced.
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
- Intent Contract (Authority Everywhere Phase 4) —
  `governance/intent.py`: `IntentContract` lets an agent declare a
  `goal` plus optional bounds (`max_value_usd`, `allowed_targets`/
  `denied_targets`, `allowed_action_types`) before starting a task;
  `WhitePactRuntimeGateway.evaluate()` gained an optional `intent`
  parameter, checked before the org's own delegated-authority checks,
  denying (`INTENT_VIOLATED`) any subsequent action from that agent
  that strays outside what it promised. New `verified_principals`-style
  append-only table `governance_intent_contracts` (migration `0028`,
  `db/intent_repository.py`, "latest declared, still-active contract
  wins" resolution). New endpoints
  `POST /api/governance/intent-contracts` and
  `GET /api/governance/intent-contracts/{agent_id}/active`.
- Authority Passport (Authority Everywhere Phase 5) —
  `governance/authority_passport.py`: `AuthorityPassport` exports a
  principal's authorized bounds from either the org's current
  `OrgAuthorityCeiling` or an active `DelegationRecord` into a
  portable, revocable, independently verifiable credential.
  `verify_passport()` re-checks a passport against its live source on
  every fetch (`VALID`/`DRIFTED`/`SOURCE_NOT_FOUND`/`REVOKED`/`EXPIRED`)
  — **not cryptographically signed**, same reasoning `attestation.py`
  already gives for its own records. New append-only
  `governance_authority_passports` table (migration `0029`,
  `db/authority_passport_repository.py`). New endpoints
  `POST /api/governance/authority-passports` (ADMIN+),
  `GET /api/governance/authority-passports/{id}` (fetch + verify), and
  `POST .../{id}/revoke`.
- Delegation Graph as a first-class object (Authority Everywhere
  Phase 6) — `governance/delegation_graph.py`: `DelegationGraph`/
  `DelegationGraphNode` package the already-correct delegation logic
  (`validate_attenuation()`, `revoke_branch()`) into a queryable
  org-wide forest, independent of any single decision. New
  `DelegationRepository.get_org_graph()` (the full forest) and
  `get_descendants()` (public, read-only, forward-direction
  counterpart to `revoke_branch()`'s internal traversal), both built
  from each identity's current state so a re-delegated identity shows
  up under its new parent only. New endpoints
  `GET /api/governance/delegations/{identity_id}/descendants` and
  `GET /api/governance/delegations/graph`. No new invariant, no new
  migration — pure read-only export of existing state.
- See `docs/architecture/AUTHORITY_EVERYWHERE.md` and
  `MIGRATION_WHITEPACT_V2.md` Sections 17-24 for the full design and
  structured phase verdicts. 24 + 17 + 26 + 20 + 21 + 35 + 35 + 18 new
  tests (`tests/test_tool_trust.py`, `tests/test_jit_credential.py`,
  `tests/test_causal_influence.py`,
  `tests/test_outcome_reconciliation_attestation.py`,
  `tests/test_verifiable_credential.py` +
  `tests/test_mcp_verified_principal.py`,
  `tests/test_intent_contract.py` + `tests/test_mcp_intent_contract.py`,
  `tests/test_authority_passport.py`, `tests/test_delegation_org_graph.py`).

### Fixed

- MCP review-contract hardening pass (2026-08-25), prompted by a
  reported OpenAI Plugins Directory review outcome for the 2026-08-13
  submission that **this repository has no corroborating record of**
  (no rejection notice, reviewer feedback, or outcome of any kind is
  documented anywhere in this codebase or its git history — see
  `compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md` for the full,
  evidence-based writeup). Independently of that unresolved question,
  auditing the actual submitted test contract against the live tools
  surfaced three real, reproducible contract mismatches, now fixed:
  - `rai_trust_score` documented `score`/`risk_tier` field names that
    the tool never returned (it returned `trust_score`/`risk`) —
    fixed additively; both name pairs now present, neither renamed.
  - `rai_hallucination` had no way to compare a response against a
    stated source at all — the exact submitted test case ("source
    says Tuesday, response says Wednesday"), run verbatim, produced
    `risk_level: "low"`, the opposite of its documented result. Fixed
    with a new optional `source` argument and a bounded,
    general-purpose (not test-specific) day-of-week/month/number
    contradiction check, plus an additive `hallucination_detected`
    field.
  - `rai_org_status` was documented as looking up a real org's plan
    tier and usage via a demo API key; at first audit it had no such
    capability at all — every field was caller-supplied, no org-id or
    auth parameter existed. Tool description corrected to state this
    explicitly at the time; **wired for real the same day** — see the
    dedicated entry below.
  - Also hardened `rai_compliance`/`rai_eu_ai_act_classify`'s
    descriptions (both claimed EU AI Act coverage with genuinely
    different input shapes — a real tool-routing collision risk) and
    corrected 8 stale "27 tools" references (actual count: 30) across
    `README.md` and the submission prep doc.
  - New regression suite `tests/openai_review/` (29 tests) encodes the
    full submitted test contract — including a direct regression test
    for the empirically-reproduced hallucination failure — as a
    permanent, machine-checked artifact
    (`tests/openai_review/review_contract.py` is the single source
    of truth). 2515 tests passed full-suite (up from 2486); `mypy`/
    `ruff` clean.
- `rai_org_status` live-org wiring (2026-08-25, same-day follow-up to
  the finding above) — on the hosted MCP transport with an
  authenticated caller, `_handle_org_status()` now reads
  `mcp/server.py`'s `_current_org`/`_current_usage_repo` ContextVars
  (already populated on every authenticated request) and merges in
  real `org_id`, `plan`, and `usage.calls_this_month`/`monthly_quota`/
  `quota_status` alongside the existing caller-supplied rollup.
  Verified with a real MCP protocol round trip against a real org/API
  key (`tests/test_mcp_org_status_live.py`) — `org_id` and `plan`
  match the real org, and `usage.calls_this_month` correctly counts
  real prior calls in the billing period, not a fabricated number. The
  self-hosted stdio transport has no org context by design and
  correctly still returns the caller-supplied-only rollup, with no
  `org_id`/`plan`/`usage` fields present at all — a structural
  absence, not a placeholder.

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
