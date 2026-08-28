# WhitePact Enterprise Neural — Codex Attack Map

Companion to `CODEX_REVIEW_HANDOFF.md`. Most security-sensitive
files/functions on this branch, grouped by subsystem, with the
invariant each is supposed to hold, the most likely attacker strategy
against it, and the existing tests (real files, verified to exist at
the review commit — see `CODEX_REVIEW_HANDOFF.md` §0).

**Assume every invariant below is false until the cited tests are
independently re-run and the code independently re-read.**

---

## CRYPTO

**`src/responsibleai/governance/crypto/`** (`types.py`, `provider.py`,
`local_envelope.py`, `envelope.py`, `signing.py`)

| | |
|---|---|
| Key function/class | `KeyId`, `LocalEnvelopeKeyProvider`, `encrypt_envelope`/`decrypt_envelope`, `encode_envelope`/`decode_envelope` |
| Invariant | Every DEK is wrapped under a per-purpose/tenant/environment KEK; `KeyId` is bound into AEAD AAD so a wrapped key/ciphertext can't be silently reused under a different purpose/tenant; `decode_envelope` is strict (rejects malformed base64 rather than silently decoding garbage) |
| Attacker strategy | Cross-tenant key confusion (does `KeyId.to_aad()` actually prevent decrypting tenant A's data with tenant B's key?); base64/encoding confusion (Phase 2 found and fixed a real TOTP/base64 collision here — verify the fix holds); version-conflict races on concurrent key writes |
| Existing tests | `tests/test_governance_crypto.py` |

**`src/responsibleai/db/crypto_key_repository.py`, `db/encryption.py`, `auth/saml.py` (signing portion)**

| | |
|---|---|
| Key function/class | `CryptoKeyRepository` (`put`/`get_current`/`get_max_version`), `EncryptedString`, `configure_field_encryption_key`/`configure_session_signing_key` |
| Invariant | New-scheme ciphertext is unambiguously distinguished from legacy/plaintext via an explicit prefix; concurrent key writes raise `KeyVersionConflictError`, never silently overwrite | 
| Attacker strategy | **See `CODEX_REVIEW_HANDOFF.md` §4 first — this scheme is not activated in production.** The real attack surface today is the legacy Fernet path and the plaintext fallback, not the new envelope scheme (which nothing calls). Test whether a deployment can be tricked into believing field encryption is active when it isn't. |
| Existing tests | `tests/test_crypto_key_repository.py`, `tests/test_field_encryption.py`, `tests/test_saml.py`, `tests/test_rotate_field_encryption_key.py` |

---

## NEURAL

**`src/responsibleai/governance/neural/`** (`types.py`, `policy.py`, `device.py`, `decision.py`, `attestation.py`, `evidence.py`)

| | |
|---|---|
| Key function/class | `evaluate_neural_data_flow` (fail-closed consent), `NeuralCapabilityManifest.__post_init__` (trust-level ceiling on `VALIDATED`), `classify_decision_status`/`is_expired`/`is_stale_decoder` (misuse rejection), `mint_neural_intent_attestation`/`verify_neural_intent_attestation` (mutation-invalidates-authorization), `evaluate_capability_validation_claim` (evidence-gated `VALIDATED`) |
| Invariant | No data flow without an active, non-revoked consent record; no `VALIDATED` capability claim from a `TRUST_D` device or without qualifying evidence; a mutated action never verifies against a stale attestation; NaN/Inf/expired/stale decisions are rejected, never silently treated as valid |
| Attacker strategy | **All of this is contract-only — §6 of the handoff.** The real attacker question is whether any of these functions could be bypassed *if* a live call site existed — since none does, the more relevant question for Codex is whether the contracts themselves are internally sound (would correctly reject a real attack if wired up), and whether any other code silently assumes one of these checks already runs when it doesn't. |
| Existing tests | `tests/test_governance_neural_device.py`, `tests/test_governance_neural_decision.py`, `tests/test_governance_neural_attestation.py`, `tests/test_neural_evidence.py`, plus consent/classification tests under `tests/test_neural_vault_repository.py` |

---

## NEURAL STORAGE

**`src/responsibleai/db/neural_vault_repository.py`, migration `0031`**

| | |
|---|---|
| Key function/class | `NeuralVaultRepository` (`create_entry`/`list_for_subject`/`soft_delete`), `NeuralConsentRepository` |
| Invariant | `NeuralVaultEntry` structurally carries no payload field — cannot leak raw neural content even if the whole table is dumped |
| Attacker strategy | Confirm this is actually structural (no code path adds a payload column or a JSON blob field later without anyone noticing); tenant isolation on this table specifically (see TENANT ISOLATION below) |
| Existing tests | `tests/test_neural_vault_repository.py` |

---

## HEART / AUTHORITY

**`src/responsibleai/governance/authority_grant.py`, `root_authority.py`, `delegation_graph.py`, `revocation_kernel.py`, `identity_authority_adapter.py`, `gateway.py`**

| | |
|---|---|
| Key function/class | `build_authority_grant` (single gated construction site, Phase 8 regression guard), `validate_root_chain`, `identity_context_to_root_type` (fail-safe kind mapping), `WhitePactRuntimeGateway.evaluate()` |
| Invariant | `AuthorityGrant`/`ExecutionAuthorization` have exactly one construction site each (structurally proven, `tests/test_llm_agent_security_boundary.py`); an ambiguous identity kind (`"oidc"`) never maps to a terminal root type; **`apply_governance()` does not currently call any Heart-production module at all** — see `CODEX_REVIEW_HANDOFF.md` §5 |
| Attacker strategy | Find a second, unaudited construction site for `AuthorityGrant`/`ExecutionAuthorization` (the guard is a text-scan heuristic, not AST-based — a `getattr(module, "AuthorityGrant")(...)` bypass would not be caught); attempt to make `identity_context_to_root_type` misclassify a machine identity as terminal |
| Existing tests | `tests/test_authority_grant.py`, `tests/test_root_authority.py`, `tests/test_delegation_chains.py`, `tests/test_delegation_graph.py`, `tests/test_revocation_kernel.py`, `tests/test_identity_authority_adapter.py`, `tests/test_llm_agent_security_boundary.py` |

---

## BRAIN

**`src/responsibleai/governance/gateway.py`, `policy.py`, `risk.py`, `workflow.py`**

| | |
|---|---|
| Key function/class | `WhitePactRuntimeGateway.evaluate()` (the ordered decision chain), `classify_action_risk`, `Policy.evaluate()`, `check_composition_violation` |
| Invariant | Every action gets a real `RiskTier`, always recorded; `Policy.evaluate()` has exactly one call site (`gateway.py`, Phase 10 regression guard); risk tiering is table-driven, not content-inferred, so argument-shaped evasion cannot change a tool's tier |
| Attacker strategy | Attacker-controlled `ActionRequest.arguments` shaped to look like a risk-tier or policy-effect override (proven ineffective in Phase 10 — re-attempt); a policy rule ordering bug shadowing a `DENY` behind a broader `ALLOW` (engine-level property is tested; a *specific org's* policy authoring is not this codebase's problem to solve) |
| Existing tests | `tests/test_governance_core.py`, `tests/test_governance_policy.py`, `tests/test_governance_risk.py`, `tests/test_workflow_authority.py`, `tests/test_brain_policy_risk_boundary.py` |

---

## CITADEL / EXECUTION

**`src/responsibleai/governance/execution.py`, `jit_credential.py`, `upstream_executor.py`, `mcp/tools.py` (`dispatch_tool`)**

| | |
|---|---|
| Key function/class | `authorize_execution` (only construction site), `_validate_authorization` (shared four-check validator), `check_target_fingerprint` (Execution Permit v2 drift detection), `issue_jit_credential`/`consume_jit_credential`, `InternalToolExecutor.execute`/`UpstreamMCPExecutor.execute` |
| Invariant | Every concrete `Executor` calls the shared validator (exactly two call sites, Phase 11 regression guard); a stale/forged/replayed authorization is refused before any side effect; a JIT credential is single-use, time-boxed, bound to exactly one authorization; `ExecutionAuthorization` never crosses a process boundary (§9 of the handoff) |
| Attacker strategy | A third executor added without calling `_validate_authorization()`; replay after a downstream failure (proven refused in Phase 14's own adversarial test — re-attempt); target-fingerprint drift bypass (server config changed between authorize and execute) |
| Existing tests | `tests/test_executor_bypass_invariant.py`, `tests/test_citadel_execution_containment.py`, `tests/test_upstream_gateway.py`, `tests/test_jit_credential.py`, `tests/test_tool_trust.py::TestExecutionPermitV2FingerprintDrift` |

---

## MCP

**`src/responsibleai/mcp/server.py` (hosted HTTP + stdio), `mcp/upstream_dispatch.py`, `mcp/governance_integration.py`**

| | |
|---|---|
| Key function/class | `_call_tool` (shared handler, both transports), `apply_governance`, `_build_transport_security` (DNS-rebinding protection), `_AuthFailureLimiter` |
| Invariant | A governed (hosted, `mcp_governance_enabled=True`) call always routes through `apply_governance()` → `InternalToolExecutor`, never a direct `dispatch_tool()` call; **the stdio path has no such invariant at all — see `CODEX_REVIEW_HANDOFF.md` §10, this is the single most important MCP-layer fact for Codex to internalize** |
| Attacker strategy | Any refactor of `_call_tool()` that reintroduces a direct `dispatch_tool()` call on the governed path (guarded by Phase 8's regression test); brute-forcing Bearer auth (rate-limited by `_AuthFailureLimiter`, in-memory unless Redis configured — cluster-wide only if `redis_url` set); DNS rebinding (off by default absent `RAI_MCP_HTTP_ALLOWED_HOSTS`/`ORIGINS`, now at least visible via `platform_isolation_problems()`, Phase 12) |
| Existing tests | `tests/test_mcp_server.py`, `tests/test_mcp_governance_dispatch.py`, `tests/test_mcp_transport_security.py`, `tests/test_platform_isolation.py`, `tests/test_ssrf_guard_fuzz.py` |

---

## AUDIT / EVIDENCE

**`src/responsibleai/db/evidence_repository.py`, `governance/evidence_bundle.py`**

| | |
|---|---|
| Key function/class | `EvidenceRepository.record`/`verify_chain`, `build_evidence_bundle`/`verify_evidence_bundle` |
| Invariant | Write-once (no `update`/`delete`); `verify_chain()` detects link-by-link tampering; a bundle digest captured before a full-chain-regeneration attack detects it, where `verify_chain()` alone cannot (proven in Phase 13's own adversarial test) |
| Attacker strategy | Full-DB-write chain regeneration (proven to defeat `verify_chain()` alone — the anchoring mitigation has no automated publication pipeline, so in practice nothing captures a bundle digest before an attack happens unless an operator does it manually); a race in `_hydrate_chain()`/concurrent `record()` calls under load |
| Existing tests | `tests/test_evidence_bundle.py`, `tests/test_evidence_chain_anchoring.py` |

---

## TENANT ISOLATION

**Every repository under `src/responsibleai/db/` carrying an `org_id` column; `governance/crypto/`'s tenant-scoped `KeyId`; the neural vault; evidence repository; execution/authorization org-match checks**

| | |
|---|---|
| Key function/class | `_validate_authorization`'s org-mismatch check (`AuthorizationOrganizationMismatchError`); every repository's `org_id`-scoped queries |
| Invariant | No repository read/write can cross an `org_id` boundary; a `KeyId` for tenant A can never decrypt tenant B's data (AAD-bound) |
| Attacker strategy | A repository method missing its `WHERE org_id = ?` filter (convention-enforced, not structurally unbypassable — `SECURITY_ASSURANCE_CASE.md`'s own C3 claim names one real historical instance found-and-fixed: an `org_id: null` audit bug); cross-tenant `ExecutionAuthorization` reuse (guarded, tested) |
| Existing tests | `tests/test_tenant_isolation.py`, plus the org-scoping tests embedded in nearly every repository's own test file |

---

## Reading order suggestion for Codex

1. `CODEX_REVIEW_HANDOFF.md` §4 (crypto activation) and §9
   (`ExecutionAuthorization` boundary) — the two most concrete,
   evidence-heavy findings.
2. `CODEX_REVIEW_HANDOFF.md` §6 (trust boundary diagram) and §7 (data
   flow) — to calibrate exactly how much of the neural track is real
   vs. contract-only before spending time attacking neural code paths
   that cannot currently be reached in production.
3. This file's HEART / AUTHORITY and BRAIN sections, cross-referenced
   with `CODEX_REVIEW_HANDOFF.md` §5 — the actual live decision path.
4. CITADEL / EXECUTION and MCP — where a real exploit would have to
   land to matter today.
