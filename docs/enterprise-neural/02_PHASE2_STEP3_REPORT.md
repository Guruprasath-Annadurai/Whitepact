# Phase 2 — Cryptographic Foundation + Key Management: Step 3 Report

STATUS: **PASS** (Step 3 of the design doc's implementation sequencing,
Sec 7 — wiring `db/encryption.py` onto the new `KeyProvider`-based
scheme with legacy-Fernet fallback. Steps 4-5 — webhook/SAML signing
migration, generalized rotation script — remain, as does actual
application-startup wiring to call `configure_field_encryption_key()`,
which is explicitly out of this step's scope, see below.)

## Objective

Wire `db/encryption.py`'s `EncryptedString` to try the new
`governance/crypto`-based scheme first, falling back to legacy Fernet,
per `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.14 and Sec 7 Step 3.

## Current state before phase

`EncryptedString` supported exactly one scheme: `RAI_FIELD_ENCRYPTION_KEY`-
based Fernet. No connection to `governance/crypto/` existed.

## Architecture implemented

- `db/encryption.py`: two co-existing schemes on one `TypeDecorator`.
  - **New scheme activation**: `configure_field_encryption_key(key_id,
    dek)` — a plain, synchronous setter installing a module-level
    `(KeyId, bytes)` cache, since `process_bind_param`/
    `process_result_value` are called synchronously by SQLAlchemy and
    can never `await` an async `KeyProvider` call. Resolving the key is
    the *caller's* responsibility, done once at async startup, outside
    this module — this module has no `asyncio` import.
  - **Format detection on read**: an explicit, versioned string prefix
    (`"wpcrypto2:"`) on new-scheme ciphertext, checked with
    `str.startswith()` — not a structural/heuristic guess. See Errors
    found below for why a heuristic-based approach was tried first and
    replaced.
  - **Fail-closed for the new scheme only**: a value carrying the new
    prefix that fails to decrypt raises `DecryptionError`; the legacy
    path's existing `except (InvalidToken, ValueError): return value`
    (a known, expected transitional state for pre-encryption plaintext)
    is unchanged.
  - `clear_field_encryption_key()` — test/deactivation helper.
- `governance/crypto/envelope.py`: **bug fix**, see Errors found below —
  `decode_envelope()` now decodes strictly (`validate=True`-equivalent),
  not leniently.

## Files created

- `docs/enterprise-neural/02_PHASE2_STEP3_REPORT.md` (this file)

## Files modified

- `src/responsibleai/db/encryption.py` — dual-scheme wiring (this
  step's core change).
- `src/responsibleai/governance/crypto/envelope.py` — `decode_envelope`
  strict-decode bug fix.
- `tests/test_field_encryption.py` — 12 new tests, extensive module
  docstring update, autouse fixture to reset the new module-global cache
  between tests.
- `tests/test_governance_crypto.py` — 1 new regression test for the
  `decode_envelope` fix.
- `CHANGELOG.md` — new entry at the top of `[Unreleased]`/`### Added`.

## Database migrations

None this step.

## Security properties added

Field encryption can now use real envelope encryption with key
versioning/rotation/tenant-purpose separation infrastructure, once
activated — closing the "flat, unversioned key" gap the Phase 2 design
doc's Sec 2 identified as the actual problem this whole phase exists to
solve. Fail-closed decryption for the new scheme specifically (no
silent-plaintext-passthrough escape hatch for genuinely new-scheme data).

## Privacy properties added

None beyond what field encryption already provided — this step changes
the encryption mechanism available, not what's classified as sensitive.

## Trust boundaries changed

None yet — `configure_field_encryption_key()` is never called by any
application code path (no app-startup wiring in this step, deliberately
— see "What this step does NOT do" below). Every existing deployment and
test that doesn't call it continues on the legacy-Fernet-or-plaintext
path exactly as before this step, unconditionally.

## Threats mitigated

None newly *mitigated in production* (nothing calls the new scheme yet)
— this step delivers the *mechanism*, verified correct in isolation.

## Threats not yet mitigated

Same as Steps 1-2 (no real deployment activates the new scheme yet).
Webhook and SAML session-secret rotation (Steps 4) remain unwired.

## Known limitations

**Application-startup wiring is explicitly NOT part of this step.**
Actually resolving a `KeyProvider`-issued key and calling
`configure_field_encryption_key()` during `dashboard/app.py`'s `lifespan`
startup sequence is a separate, higher-blast-radius change (it touches
the one live, traffic-serving startup path in the whole codebase) that
deserves its own scoped review, not to be silently bundled into a
module-level wiring change. Tracked as a follow-up, not forgotten.

## Unit test results

`tests/test_field_encryption.py`: 21 tests total (9 pre-existing,
unmodified in behavior, 12 new — `TestConfigureFieldEncryptionKey` (2),
`TestNewSchemeEncryptedString` (4, including the TOTP-collision
regression guard), `TestMixedSchemeCoexistence` (3), plus one added
pre-existing-gap test for `_load_fernet`'s empty-key-list branch). All
passing. `tests/test_governance_crypto.py`: +1 test for the
`decode_envelope` strictness fix.

## Integration test results

`TestMixedSchemeCoexistence` and `TestAuditLogIpAddressEncryption`
(pre-existing, unmodified) exercise the real `AuditRepository` /
`EncryptedString` / DB round trip together, not mocks.

## Property test results

None new this step (Step 1's property tests already cover
`encrypt_envelope`/`decrypt_envelope` at the primitive level; this
step's own tests are example-based, appropriate for the format-
detection and dual-scheme-coexistence logic being tested).

## Fuzz results

Not run — same reasoning as prior steps.

## Adversarial test results

The actual adversarial finding this step produced was found by running
the *existing, unrelated* test suite, not a dedicated adversarial pass —
see Errors found below. Explicit tamper test
(`test_tampered_new_format_ciphertext_fails_closed`) added and passing.

## Regression results

Full suite: **2949 passed, 0 failed**, 83.79s
(`/tmp/full_run_phase2_step3b.log`). Two real bugs required fixes to
reach this (see Errors found below) — the first attempt at this step
broke 12 pre-existing tests.

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not benchmarked — no production call site activates the new scheme yet.

## Backward-compatibility result

Fully backward compatible, verified concretely: the full existing test
suite (2949 tests, including every MFA/TOTP/audit-log/webhook-secret
test that exercises `EncryptedString` today) passes unmodified in
behavior — the new scheme is purely additive and inert until
`configure_field_encryption_key()` is explicitly called, which nothing
in the shipped codebase does yet.

## Migration result

Not applicable this step.

## Rollback procedure

Revert `db/encryption.py` and `governance/crypto/envelope.py` to their
Step 2 state; delete the new test additions. No stored data depends on
the new scheme (nothing writes it in production yet).

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md`, and `db/encryption.py`'s
own module docstring (substantially rewritten to document both schemes,
the format-detection approach, and the collision bug that shaped it).

## Claims now supported by evidence

"`db/encryption.py` can encrypt/decrypt using the new envelope scheme,
correctly coexisting with legacy Fernet ciphertext and pre-encryption
plaintext (including base32 TOTP secrets) in the same column, fail-
closed on tampering or misconfiguration" — true, evidenced by the tests
above and the full-suite regression run.

## Claims still unsupported

"The new scheme is active in any real deployment" — false; nothing calls
`configure_field_encryption_key()` outside tests. That's the explicit
scope boundary of this step.

## Errors found and fixed this phase

Both found through this session's own established discipline (empirical
verification before/alongside tests, full-suite regression run before
declaring done) — not assumed away:

1. **Format-detection heuristic was unsound — a real, systematic
   collision, not a rare edge case.** The first implementation of this
   step distinguished the new scheme from legacy/plaintext by decoding
   the stored value as base64 and checking whether the first decoded
   byte equaled Fernet's fixed version byte (`0x80`). Running the full
   regression suite surfaced 12 failures, all MFA-related
   (`test_mfa_login_flow.py`, `test_org_api.py`). Root cause: `auth/
   mfa.py`'s TOTP secrets are base32 (`pyotp.random_base32()`) — base32's
   alphabet (`A-Z2-7`) is a **strict subset** of base64's, and
   `pyotp.random_base32()`'s 32-character output is base64-block-aligned
   (32 is divisible by 4). A genuine plaintext TOTP secret therefore
   *successfully decodes as base64* essentially every time, and its
   first decoded byte is not `0x80`, so it was misidentified as
   new-scheme ciphertext — and since no key was configured (this step
   never activates the scheme), the fail-closed design correctly raised
   `DecryptionError`, breaking every MFA flow that reads back a stored
   secret. **This was a design flaw, not an implementation bug** — no
   base64-decodability-based heuristic can reliably distinguish "real
   ciphertext" from "plaintext that happens to be composed of base64-
   alphabet characters," and TOTP secrets are a concrete, currently-
   shipping example, not a hypothetical one. **Fix**: replaced the
   heuristic with an explicit, versioned string prefix (`"wpcrypto2:"`)
   on new-scheme ciphertext, checked via `str.startswith()` before any
   decoding is attempted — deterministic, not probabilistic.
2. **`decode_envelope()`'s base64 decoding was lenient, not strict** —
   found empirically while debugging bug #1, and worth fixing at the
   source regardless of the prefix-based redesign above (this function
   is used elsewhere, and any future caller could hit the same class of
   issue). `base64.urlsafe_b64decode()` defaults to `validate=False`,
   which *silently discards* characters outside the base64 alphabet
   instead of raising — so a plaintext string like an IP address
   (`"203.0.113.5"`, which contains `.`, not in the base64 alphabet)
   would still "successfully" decode to meaningless garbage bytes rather
   than raise `EnvelopeFormatError` as the function's docstring implies
   it does. Since `base64.urlsafe_b64decode` has no `validate` parameter
   (only plain `b64decode` does), the fix translates the URL-safe
   alphabet (`-`/`_`) to the standard one (`+`/`/`) first, then calls
   `base64.b64decode(..., validate=True)`. Added a regression test
   (`test_decode_envelope_rejects_plaintext_a_lenient_decoder_would_
   silently_accept`) confirming `decode_envelope("203.0.113.5")` now
   correctly raises.

## Residual risks

- The specific "plaintext collides with an encoding's alphabet" failure
  mode (bug #1) is now closed for field encryption via the explicit
  prefix, but is worth keeping in mind for Steps 4-5 (webhook secrets,
  SAML session tokens) — those are HMAC-signed, not encrypted the same
  way, so the exact collision doesn't recur, but any future format-
  detection logic in this codebase should default to an explicit marker
  over a structural/heuristic guess, per this step's own finding.
- Application-startup wiring (the piece that makes any of this reachable
  in production) remains undone — tracked explicitly, not silently
  deferred.

## Next-phase dependencies

Step 4 (webhook/SAML signing onto the shared `KeyProvider`-based
canonical signing interface) and Step 5 (generalized rotation script)
remain, per the design doc's own sequencing. Separately — not numbered
in the design doc's Step list, but necessary before any of this is real
— application-startup wiring to actually call
`configure_field_encryption_key()` (and the equivalent for webhook/SAML
once Step 4 lands) needs its own scoped change and review.
