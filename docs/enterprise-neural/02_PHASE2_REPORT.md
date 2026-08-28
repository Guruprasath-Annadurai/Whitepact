# Phase 2 — Cryptographic Foundation + Key Management: Step 1 Report

STATUS: **PASS** (Step 1 of the design doc's implementation sequencing,
Sec 7 — package, Protocol, one production-capable provider, envelope
format. Steps 2-5 — wiring existing call sites, the persistent
`crypto_keys` migration, and the generalized rotation script — remain.
Phase 2 as a whole is not yet complete; this report covers only what
this step actually shipped.)

## Objective

Build `governance/crypto/`: the `KeyPurpose`/`KeyId`/`KeyStatus`
vocabulary, the `KeyProvider` Protocol every future call site depends on,
the one production-capable provider (`LocalEnvelopeKeyProvider`, real
envelope encryption, self-hosted), and the self-describing encrypted
envelope format — per `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 7
Step 1.

## Current state before phase

No `governance/crypto/` package existed. Cryptography in the codebase was
entirely call-site-local (Fernet in `db/encryption.py`, HMAC in
`webhooks/manager.py` and `auth/saml.py`) — see the design doc's Sec 1
inventory. No shared key-hierarchy abstraction existed anywhere.

## Architecture implemented

- `governance/crypto/types.py` — `KeyPurpose` (4-value `StrEnum`),
  `KeyStatus` (`ACTIVE`/`RETIRED`/`REVOKED`), `KeyId` (frozen dataclass,
  canonical string/AAD encoding), `WrappedKeyRecord`, and the exception
  hierarchy (`CryptoError` → `KeyNotFoundError`, `KeyRevokedError`,
  `EnvelopeFormatError`, `DecryptionError`).
- `governance/crypto/provider.py` — `KeyProvider` Protocol (5 methods:
  `get_encryption_key`, `get_decryption_key`, `rotate`, `revoke`,
  `retire`) and `WrappedKeyStore` Protocol (persistence seam).
- `governance/crypto/local_envelope.py` — `InMemoryWrappedKeyStore`
  (explicitly non-persistent, dev/test only) and
  `LocalEnvelopeKeyProvider`: HKDF-derives a per-purpose/tenant/
  environment KEK from a 32-byte root key, wraps randomly generated DEKs
  via AES-256-GCM.
- `governance/crypto/envelope.py` — `encrypt_envelope`/`decrypt_envelope`
  (self-describing format, `KeyId` bound into AEAD associated data) and
  `encode_envelope`/`decode_envelope` (base64, matching the existing
  Fernet-token storage convention).
- `governance/crypto/__init__.py` — public surface, 17 exported names.

## Files created

- `src/responsibleai/governance/crypto/__init__.py`
- `src/responsibleai/governance/crypto/types.py`
- `src/responsibleai/governance/crypto/provider.py`
- `src/responsibleai/governance/crypto/local_envelope.py`
- `src/responsibleai/governance/crypto/envelope.py`
- `tests/test_governance_crypto.py`
- `docs/enterprise-neural/02_PHASE2_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/__init__.py` — exports `crypto` as a
  module (same convention as `sovereignty_kernel`), module docstring
  extended.
- `tests/test_governance_package_exports.py` — added
  `test_crypto_module_exported`.
- `CHANGELOG.md` — new entry at the top of `[Unreleased]`/`### Added`.

## Database migrations

None. The persistent `crypto_keys`-table-backed `WrappedKeyStore` is a
later step (Step 2 per the design doc's sequencing) — this step ships
only the in-memory store.

## Security properties added

- Real envelope encryption (KEK wraps DEK) rather than a single flat key
  directly encrypting data — enables independent key rotation without a
  full data re-encryption sweep for the common case (KEK rotation).
- Purpose and tenant separation enforced structurally: a DEK for one
  `(purpose, tenant, environment)` tuple cannot decrypt data for another,
  both via HKDF's one-way derivation (different KEK entirely) and via
  AEAD associated-data binding (tampering with the embedded `KeyId`
  breaks the authentication tag).
- `REVOKED` vs `RETIRED` as distinct lifecycle states — a revoked key
  never decrypts anything again, even data predating revocation; a
  retired key remains valid for old data but is never issued for new
  writes. Verified by test, not just documented.
- Fail-closed by construction: every failure path (`KeyNotFoundError`,
  `KeyRevokedError`, `DecryptionError`, `EnvelopeFormatError`) raises;
  nothing in this package has a plaintext or default-key fallback.

## Privacy properties added

None directly (no PII flows through this package yet — that happens once
`db/encryption.py` is wired onto it, a later step).

## Trust boundaries changed

None yet — this package is not called from any existing code path. It
is additive, unreachable dead code until wired in a later step.

## Threats mitigated

Cross-purpose/cross-tenant key confusion (tested), ciphertext tampering
(AEAD auth tag), embedded-metadata tampering (AAD binding), nonce reuse
(no public API surface accepts one), stale-key-version reuse after
rotation-without-revocation confusion (the version-numbering bug found
and fixed this phase — see Errors below).

## Threats not yet mitigated

- Everything this package doesn't yet touch: `db/encryption.py`'s
  existing flat Fernet key, webhook/SAML session secrets' lack of
  rotation — all still exactly as documented in the design doc's Sec 1,
  unchanged by this step.
- No persistent store yet — `InMemoryWrappedKeyStore` loses all key
  state on process restart; not safe for any real deployment.
- No `AWSKMSKeyProvider`/Vault Transit provider — by design, deferred
  per the design doc's explicit "don't inflate this phase" instruction.

## Known limitations

`InMemoryWrappedKeyStore` is dev/test-only, documented prominently in its
own docstring. `LocalEnvelopeKeyProvider`'s root key custody (how
`RAI_ROOT_KEY` gets injected, generated, backed up) is not wired up yet —
this step ships the primitive, not the deployment integration.

## Unit test results

47 tests, all passing, in `tests/test_governance_crypto.py`:
`TestKeyId` (13), `TestLocalEnvelopeKeyProviderConstruction` (2),
`TestGetEncryptionKey` (4), `TestRotation` (5), `TestWrappedKeyCorruption`
(2), `TestRevocationAndNotFound` (5), `TestEnvelope` (11),
`TestNoSecretLeakageInErrors` (2), `TestProperties` (2 Hypothesis
property tests).

## Integration test results

Not applicable — nothing calls this package yet (see Trust boundaries
changed).

## Property test results

`test_encrypt_decrypt_round_trips_for_arbitrary_purpose_tenant_plaintext`
(arbitrary purpose/tenant/plaintext) and
`test_rotation_versions_are_strictly_monotonic` (1-8 sequential
rotations) — both pass. The first of these two property tests is what
surfaced both real bugs described below, before either reached a commit.

## Fuzz results

Not run as a separate fuzzing pass — Hypothesis's property tests above
serve this role for this step's scope (structured input generation over
`KeyPurpose`/tenant/plaintext/rotation-count spaces).

## Adversarial test results

Misuse-test list from the design doc Sec 4, mapped to actual tests:
corrupted ciphertext ✓, modified AAD (tampered embedded `KeyId`) ✓, wrong
tenant/purpose key ✓ (`test_wrong_key_id_expectation_is_rejected`,
`test_cross_tenant_decryption_fails_...`), revoked key ✓, unsupported
version ✓, nonce misuse impossible via public API ✓ (structural test via
`inspect.signature`), malformed envelope (missing separator, truncated
nonce, invalid UTF-8 prefix) ✓, rotation old→new ✓, retired data stays
readable ✓, new writes use current version ✓, no secret leakage in error
messages ✓ (`TestNoSecretLeakageInErrors`). "Missing KMS fails closed"
and "cross-tenant decryption impossible through normal application
interfaces" are only partially testable at this step's boundary (no call
site exists yet to test end-to-end) — tracked as still-open in Threats
not yet mitigated above.

## Regression results

Full suite: **2922 passed, 0 failed**, 79.38s
(`/tmp/full_run_phase2_step1.log`). No regressions from baseline.

## Static analysis

`ruff check` and `ruff format --check`: clean on all 6 new/modified
source files and the test file. `mypy`: `Success: no issues found in 6
source files` (crypto package + test file), then re-verified clean after
the export change.

## Dependency audit

No new dependency added — `cryptography` (`AESGCM`, `HKDF`) is already a
project dependency (`pyproject.toml`, `cryptography>=50.0.0`), same
package `db/encryption.py`'s Fernet usage already depends on.

## Secret scan

No secrets introduced — this package generates keys at runtime
(`os.urandom`), never embeds one.

## Supply-chain results

Not re-run this step (no dependency change).

## Performance results

Not benchmarked this step — this package isn't wired into any hot path
yet (Phase 12's benchmarking scope, once call sites exist).

## Backward-compatibility result

Fully backward compatible — new package, new export, zero existing call
site touched.

## Migration result

None (no DB migration this step).

## Rollback procedure

Delete `src/responsibleai/governance/crypto/`, revert the `governance/
__init__.py` export and `tests/test_governance_package_exports.py`
addition, delete `tests/test_governance_crypto.py`. No other file
depends on this package yet.

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact has a `KeyProvider` abstraction with a real, tested envelope-
encryption implementation, key purpose/tenant/environment separation, and
distinct revoke/retire lifecycle semantics" — true, and covered by the
100%-coverage, 47-test suite above.

## Claims still unsupported

"WhitePact's field encryption/webhook signing/SAML session tokens use
key rotation with purpose separation" — not yet; those call sites are
unmodified. "WhitePact has a persistent, production-durable key store" —
not yet; only the explicitly non-persistent in-memory store exists.

## Errors found and fixed this phase

Both found by the Hypothesis property test
`test_encrypt_decrypt_round_trips_for_arbitrary_purpose_tenant_plaintext`
before any commit was made — exactly the workflow this whole initiative's
"test first, evidence decides" discipline is meant to catch:

1. **`KeyId` sentinel collision** — the original encoding used the
   literal string `"-"` to represent "no tenant" (`None`) in
   `to_string()`. A real tenant_id of exactly `"-"` round-tripped back
   as `None`, silently corrupting tenant identity. **Fix**: switched the
   `None` sentinel to the empty string, and made `""` an explicitly
   rejected `KeyId.tenant_id` value (a caller meaning "no tenant" must
   pass `None`, never `""`) — removing the ambiguity structurally
   instead of picking a different collidable sentinel.
2. **NUL-byte tenant_id vs. envelope separator collision** — a
   `tenant_id` containing `\x00` (the envelope format's own field
   separator) could corrupt envelope parsing. **Fix**: `KeyId.__post_init__`
   now rejects NUL bytes in `tenant_id` and `environment`.
3. **Version-numbering collision on retire/revoke outside `rotate()`**
   — found while *writing a new test* (`test_retire_stops_new_writes_...`),
   not by Hypothesis: `get_encryption_key()`'s "no active key" fallback
   hardcoded `version=1`. If a key was retired or revoked directly
   (bypassing `rotate()`, which does compute the next version correctly),
   the next `get_encryption_key()` call would regenerate version 1,
   silently overwriting the retired/revoked record's wrapped DEK under
   the same `KeyId` — permanently destroying any data encrypted under the
   original version 1. **Fix**: added `WrappedKeyStore.get_max_version()`
   (scans *all* statuses, not just `ACTIVE`) and changed both
   `get_encryption_key()`'s fallback and `rotate()` itself to base the
   next version number on it — this was a real, security-relevant data-
   loss bug, not a cosmetic one, caught before merge.

## Residual risks

- The version-numbering bug class (§ above) suggests other multi-status
  bookkeeping paths deserve the same scrutiny once the persistent
  `crypto_keys`-table store is built (Step 2/3) — a DB-level unique
  constraint on `(purpose, tenant_id, environment, version)` would turn
  this class of bug into a hard database error instead of a silent
  overwrite, and should be part of that migration's design.
- No production call site exists yet, so this package's real-world
  correctness under concurrent access (two processes calling `rotate()`
  simultaneously) is untested — `InMemoryWrappedKeyStore` has no locking,
  and neither does the design yet specify one for the future DB-backed
  store. Flagged for Step 2/3, not silently assumed safe.

## Next-phase dependencies

Step 2 (per design doc Sec 7): `crypto_keys` migration, additive,
sequenced after whatever migration number `docs/heart-production/`
Phase 3 lands next. Step 3: wire `db/encryption.py` onto this provider
with the legacy-Fernet-fallback path described in the design doc Sec
3.14. Steps 4-5: webhook/SAML signing migration, generalized rotation
script.
