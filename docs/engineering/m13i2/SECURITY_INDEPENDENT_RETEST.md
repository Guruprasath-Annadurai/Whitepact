# Independent security retest

I2 preserves the original eight reproducer blobs against `57c69344961196fd89b40e8ffec65c06a1898fce`; the exact-candidate preflight passes at initial I2 checkpoint `7b2c84f31220216c68c222c2655a8ae8215a8f69`, tree `9466dceca5be17739d5998d4fbaca39f2c4536e2`. Preflight is a preservation check, not security acceptance.

Initial exact-head CI run [38805855458](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38805855458) independently executed the unchanged original suites: Python 3.11 **36 passed**, one warning, 35.73s; Python 3.12 **36 passed**, one warning, 28.69s. Extended revocation/egress scope: **202 passed** on each version, one warning, 76.70s/70.28s. Skip guards passed with zero skips. Real Ubuntu/container scope: **15 passed**, zero skips, 108.44s. These are initial I2 checkpoint results, not yet the final product/harness tree.

The same run retained the genuine WebAuthn-origin customer failure, 101 inherited lint errors and the unsigned `39619c4...` checkpoint. Security-owned sources and original reproducer assertions remain unchanged.

Fresh local original-suite run also completed: **36 passed**, one deprecation warning, zero skips, 321.41s on Darwin with disposable PostgreSQL. It started from the initial I2 checkpoint while unrelated docs/harness integration continued; it is source-scope evidence, not a clean final-HEAD receipt. Final exact-head CI remains the authoritative candidate receipt.

Original tests retain their real scope: some exercise seeded software credentials, controlled scheduling, injected cancellation or service-level fixtures. Native Linux/container execution must be distinguished from Darwin skips. None of these alone proves the real customer WebAuthn/authority journey or physical multi-host crash recovery.

No security-owned enforcement or original reproducer assertion is modified. Full independent acceptance remains BLOCKED where the actual customer contract fails.
