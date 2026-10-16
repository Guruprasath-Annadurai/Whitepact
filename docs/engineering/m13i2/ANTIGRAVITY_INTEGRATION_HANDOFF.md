# Antigravity integration handoff

The unified product candidate preserves PR #206 `57c69344961196fd89b40e8ffec65c06a1898fce` and PR #208 `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`. Newly published [ATLAS PR #212](https://github.com/Guruprasath-Annadurai/Whitepact/pull/212), exact `d0041e4f6e9436bcdcec30612a6e35e10dc6af8f` (tree `b5bf547c1e237a3d19e78b866c6bd0514f700234`), descends from I1 through implementation commit `ecd97da72b953817aae94070b2ccbe3f8d6e37ba`. It was reviewed in a separate worktree and **NOT integrated** because qualification remains blocked.

## Independent ATLAS disposition

- Existing origin plus original suites: **38 passed**, one warning, zero skips, 175.91s. Application tests: **3 passed**, 11.81s, explicitly SQLite/ASGI fixtures; not PostgreSQL application-authorization proof.
- Actual fresh PostgreSQL/HTTP customer attempt: **22 confirmed / 1 blocked**. Local application and expected origin both `http://localhost:59461`; the old mismatch is resolved for this observed local scope. Stop is now `REAL_AUTHENTICATOR_CEREMONY_NOT_COMPLETED`. No fake passkey or authority seed was used.
- Defensive production-configuration invariants: **1 passed / 2 failed**. `_svc()` accepts explicit `http://app.example.com` in production and falls back to default origin when configuration is missing. These are pure constructor/configuration tests, with a stub engine and no credentials, HTTP exploit or authority journey. Preserved signed review commit `d1fe6964cb79abc70eec149e8e3fa5fd236010b9`, tree `a79d5eec90c9e14c0428cff86cb84ee834baa406`, parent exact ATLAS checkpoint. File: `tests/test_m13i2_atlas_origin_configuration.py` on `codex/whitepact-m13-i2-atlas-review`.
- Capability enumeration checks an unrevoked root row, active delegation and agent lifecycle, then emits `AUTHORIZED`, `requires_approval=false`, `requires_passkey_stepup=false`, `consent_id=null`. The inspected implementation does not evaluate consent/policy or root expiry for that projection. Existing new tests exercise the no-root pending case, not these authorization claims. This is a source/test coverage gap; no bypass was attempted.
- Application disable commits application/agent/consent changes before separate delegation-revocation transactions. Application validation during registration occurs before the insertion transaction. The claimed immediate cascade/concurrency/crash guarantees are unqualified; existing tests cover lifecycle state, not active grants or actual concurrent failure.
- The typed capability reader coerces flags and returns `authorityEnforced=true` without validating the complete authority projection. Do not enable authorization displays/actions from this contract. Several documented request/status/response shapes differ from implementation; inspect actual code before integration.

Required owner action: provide corrected exact security commits and independent tests for the production-origin, consent/policy/expiry, atomic cascade and documented-schema contracts. Narrow application GET previews may be possible after a separate verified read-only contract review; this candidate imports none of the unqualified checkpoint.

## Required owner contracts

1. Resolve the real WebAuthn application-origin mismatch through the security-owned configuration contract. Preserve the I1 failing runner and provide the exact fix commit plus supported deployment/browser-origin configuration.
2. Define authenticated tenant-scoped application ownership and executable-capability APIs. Existing agent registration and reported root/consent records are insufficient evidence of effective execution permission.
3. Supply a real supported path through passkey completion, consent, root, application, agent, delegation, policy, approval, controlled execution, evidence and revocation. No seeded authority or fake ceremony can qualify it.
4. Disposition inherited security-source/test lint and unsigned security commits without policy exceptions, forged signoffs or protected-history rewriting.
5. Qualify an expected-organization/version precondition for organization rename. Current pathless PATCH acts on cookie principal organization; validating the acknowledgement after a concurrent cookie switch cannot undo a write to the unintended workspace. Product keeps the new rename UI disabled; a preflight GET is not an atomic fix.

Prior concrete handoff: https://github.com/Guruprasath-Annadurai/Whitepact/pull/208#issuecomment-6197828920 . Current integration evidence: https://github.com/Guruprasath-Annadurai/Whitepact/pull/211 .

Future integration requires exact commit ancestry/diff review, reproduction of the old failure, independent fix validation and regression before merging into a separate candidate. Do not edit Antigravity's branch or active directory.
