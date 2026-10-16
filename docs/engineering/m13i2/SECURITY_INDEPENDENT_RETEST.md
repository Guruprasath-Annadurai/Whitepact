# Independent security retest

I2 preserves the original eight reproducer blobs against `57c69344961196fd89b40e8ffec65c06a1898fce`; the exact-candidate preflight passes at initial I2 checkpoint `7b2c84f31220216c68c222c2655a8ae8215a8f69`, tree `9466dceca5be17739d5998d4fbaca39f2c4536e2`. Preflight is a preservation check, not security acceptance.

Initial exact-head CI run [38805855458](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38805855458) independently executed the unchanged original suites: Python 3.11 **36 passed**, one warning, 35.73s; Python 3.12 **36 passed**, one warning, 28.69s. Extended revocation/egress scope: **202 passed** on each version, one warning, 76.70s/70.28s. Skip guards passed with zero skips. Real Ubuntu/container scope: **15 passed**, zero skips, 108.44s. These are initial I2 checkpoint results, not yet the final product/harness tree.

The same run retained the genuine WebAuthn-origin customer failure, 101 inherited lint errors and the unsigned `39619c4...` checkpoint. Security-owned sources and original reproducer assertions remain unchanged.

Fresh local original-suite run also completed: **36 passed**, one deprecation warning, zero skips, 321.41s on Darwin with disposable PostgreSQL. It started from the initial I2 checkpoint while unrelated docs/harness integration continued; it is source-scope evidence, not a clean final-HEAD receipt. Final exact-head CI remains the authoritative candidate receipt.

Original tests retain their real scope: some exercise seeded software credentials, controlled scheduling, injected cancellation or service-level fixtures. Native Linux/container execution must be distinguished from Darwin skips. None of these alone proves the real customer WebAuthn/authority journey or physical multi-host crash recovery.

No security-owned enforcement or original reproducer assertion is modified. Full independent acceptance remains BLOCKED where the actual customer contract fails.

## Newly published ATLAS checkpoint

Exact PR #212 checkpoint `d0041e4f6e9436bcdcec30612a6e35e10dc6af8f` was independently reviewed outside the unified candidate. Its two existing origin tests plus unchanged original suites passed **38 tests**, one warning, zero skips, 175.91s. Existing application tests passed **3**, 11.81s, using SQLite/ASGI fixtures. The actual fresh PostgreSQL/HTTP journey confirmed **22 phases** and observed the local origin mismatch resolved, then correctly stopped before real authenticator completion. No browser authenticator assertion, consent/root/execution or authority revocation is thereby qualified.

New pure defensive configuration tests preserve **two failures** for missing/non-HTTPS production origin, alongside one HTTPS control pass. Signed isolated review commit `d1fe6964cb79abc70eec149e8e3fa5fd236010b9` changes tests only, parent exact ATLAS checkpoint. Capability projection, consent/policy/expiry and cascade atomicity gaps remain source/test-review blockers. See `ANTIGRAVITY_INTEGRATION_HANDOFF.md` for exact scope and owner actions. ATLAS implementation is **NOT integrated**; neither its report nor the 38 passing assertions clears those blockers.

`scripts/check_security_regressions.py` also freshly passed **18 tests in 37.30s** against the integrated source. Separate `git diff --exit-code` verification confirmed no changes from I1 to enterprise/runtime enforcement, original independent reproducer directory, R3/root-hardening suites, or the original I1 customer-origin reproducer. These checks do not clear privileged customer acceptance.
