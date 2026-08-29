# Security Remediation Gap 1 — Crypto Foundation Activation: Report

STATUS: **REMEDIATED**. The documented gap (Phase 2's envelope-
encryption foundation built but never activated by any application-
startup path) is closed for the two sensitive paths that exist today
(field encryption, SAML session signing), fail-closed, opt-in, with
zero change to default/development behavior.

## Reproduction

Confirmed, not assumed, before writing any fix (see
`REMEDIATION_GAP1_CRYPTO_ACTIVATION.md`'s "Reproduction" section):
`configure_field_encryption_key()`/`configure_session_signing_key()`
had zero call sites outside their own definitions and test files;
`EncryptedString`'s plaintext fallback was real and reachable.

## What changed

- `dashboard/config.py`: two new `Settings` fields —
  `enterprise_mode: bool = False`, `crypto_root_key: str | None = None`.
  Both opt-in, non-breaking, same pattern as the existing
  `multi_replica` self-declaration.
- `db/crypto_activation.py` (new): `activate_production_crypto(settings,
  engine)` — no-op unless `enterprise_mode=true`; raises
  `CryptoActivationError` (fail-closed, aborts startup) if
  `enterprise_mode=true` but `crypto_root_key` is missing or doesn't
  decode to exactly 32 bytes. On success, constructs a real
  `LocalEnvelopeKeyProvider` backed by the durable, DB-backed
  `CryptoKeyRepository` (not the in-memory dev store) and activates
  both `KeyPurpose.FIELD_ENCRYPTION` and `KeyPurpose.SESSION_SIGNING`.
- `dashboard/app.py`: calls `activate_production_crypto()` in
  `lifespan`, immediately after `_db_engine.init()`, before any
  repository is constructed.
- `mcp/server.py`: identical call in `_build_http_app()`'s own
  `_lifespan()`, same ordering.

## What did not change

- Default behavior (`enterprise_mode=false`, the default) is
  byte-for-byte unchanged — legacy Fernet/HMAC schemes and the
  documented plaintext fallback remain exactly as they were. This is
  deliberate: a deployment that hasn't opted in must not experience
  any behavior change at all.
- No new cryptographic primitive was built. `LocalEnvelopeKeyProvider`,
  `CryptoKeyRepository`, envelope encryption, key versioning,
  rotation, and revocation are all Phase 2 work, unmodified.
- No KMS/HSM backend was implemented — per the directive's own
  instruction not to fabricate one. `LocalEnvelopeKeyProvider` is the
  one real, testable, production-capable route; the `KeyProvider`
  Protocol remains the seam for a future real cloud-KMS integration.
- Webhook HMAC signing was not touched — correctly out of scope
  (two-party secret, Phase 2 Step 4's own finding).

## Mandatory test coverage (directive's own list)

| Requirement | Test | Result |
|---|---|---|
| Missing key → production fail closed | `test_enterprise_mode_true_without_root_key_raises` | PASS |
| Corrupted ciphertext → reject | `test_corrupted_new_scheme_ciphertext_is_rejected` | PASS |
| Wrong key → reject | Covered by existing `tests/test_governance_crypto.py` (AEAD-AAD binding) — not re-tested here, see file docstring | PASS (pre-existing) |
| Wrong tenant → reject | Covered by existing `tests/test_governance_crypto.py` | PASS (pre-existing) |
| Wrong purpose → reject | Covered by existing `tests/test_governance_crypto.py` | PASS (pre-existing) |
| Revoked key → reject | Covered by existing `tests/test_crypto_key_repository.py` | PASS (pre-existing) |
| Unknown key version → reject | Covered by existing `tests/test_crypto_key_repository.py` | PASS (pre-existing) |
| Metadata tampering → reject | `test_corrupted_new_scheme_ciphertext_is_rejected` (AAD includes `KeyId`) | PASS |
| Rotation works | `test_rotated_key_reads_old_ciphertext_and_writes_under_new_version` | PASS |
| Old legitimate ciphertext remains readable | Same test — v1 ciphertext decrypts after rotation to v2 | PASS |
| New writes use current key | Same test — new encryption resolves to v2 | PASS |
| Secrets do not appear in logs | `test_activation_log_output_never_contains_root_key_or_dek` | PASS |
| Enterprise mode cannot silently store plaintext | `test_enterprise_mode_never_silently_stores_plaintext` | PASS |

13 new tests, all passing. Full suite: 3160 passed, 1 skipped, 0
failed.

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean (0 errors, 4
modified/created source files). `bandit -r
src/responsibleai/db/crypto_activation.py -ll`: 0 issues.

## Residual scope, named explicitly

- No migration tooling was added to move existing legacy-Fernet data
  to the new scheme automatically upon activation —
  `scripts/rotate_field_encryption_key.py` (Phase 2 Step 5) already
  exists for that, unaffected by this change and still the correct
  tool for it.
- No real KMS/HSM provider implementation — explicitly out of scope
  per the directive's own "do not invent a fake KMS" instruction.
- `enterprise_mode` is currently scoped to crypto activation only. The
  directive's Gap 2 (stdio governance) references the same "enterprise
  mode" concept; this flag is designed to be reused there, not
  duplicated, but that wiring is not part of this remediation pass.
