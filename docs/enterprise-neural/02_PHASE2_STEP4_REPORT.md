# Phase 2 — Cryptographic Foundation + Key Management: Step 4 Report

STATUS: **PASS**, with a scope correction from the design doc's
original framing — see "Scope correction" below. SAML session-token
signing is wired onto the new scheme; webhook payload signing is
deliberately **not**, for a substantive architectural reason found
during this step, not a shortcut.

## Objective

Per `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.11 and Sec 7 Step
4: "generalize the existing `hmac.new(secret, body, hashlib.sha256)`
pattern in `webhooks/manager.py` and `auth/saml.py` into one shared
function that both call, taking a `KeyId`-resolved key from
`KeyProvider` instead of a raw deployer-supplied string."

## Scope correction (found this step, not assumed from the design doc)

The design doc's Sec 3.11 treats `webhooks/manager.py` and
`auth/saml.py` as the same kind of problem. They are not, and treating
them the same would have been a real design mistake:

- **SAML session tokens** (`auth/saml.py`'s `mint_session_token`/
  `validate_session_token`) are signed *and verified* entirely within
  this codebase. No external party ever sees or depends on the exact
  secret value. This is architecturally identical to field encryption
  (Step 3): a WhitePact-owned secret, safe to rotate via the internal
  `KeyProvider` at will.
- **Webhook payload signatures** (`webhooks/manager.py`, `config.secret`)
  are HMAC'd with a secret the *deployer chose and shared with an
  external receiver* — Slack, PagerDuty, or a customer's own webhook
  endpoint, configured on both sides so the receiver can verify the
  signature. WhitePact rotating that secret internally, unilaterally,
  without the receiver rotating in lockstep, would silently break
  signature verification on their end for every future delivery. This
  is a fundamentally different secret-ownership model from field
  encryption or session signing, and no `KeyProvider`-based internal
  rotation scheme is a correct fit for it.

**Consequence**: this step wires SAML session signing onto the new
scheme (a genuine, correct application of the design doc's intent) and
explicitly does *not* touch `webhooks/manager.py` (a genuine, evidenced
reason the design doc's Sec 3.11 wording doesn't hold for that call
site). This is documented in `governance/crypto/signing.py`'s own module
docstring and `auth/saml.py`'s module docstring, not just here, so a
future reader hits the reasoning at the point of use.

## Architecture implemented

- `governance/crypto/signing.py` (new) — `sign(dek, key_id, message) ->
  str` (HMAC-SHA256, hex digest) and `verify(dek, key_id, message,
  signature) -> bool` (constant-time). `key_id` is bound into the
  signed material (`key_id.to_aad() + b"|" + message`), the same AAD-
  binding pattern `envelope.py` uses for encryption — a signature
  produced under one purpose/tenant/version can't be replayed as if it
  came from another.
- `auth/saml.py` — `configure_session_signing_key(key_id, dek)` /
  `clear_session_signing_key()` (same synchronous-setter pattern as
  `db/encryption.py`'s Step 3 wiring, same reason: `mint_session_token`/
  `validate_session_token` are plain sync functions, never `await`).
  `mint_session_token` signs with the new scheme when configured
  (matching "new writes use current key" from every other Phase 2 call
  site), else legacy `SAMLConfig.session_secret` HMAC unchanged.
  `validate_session_token` tries the new-scheme key first (if
  configured), falls back to the legacy secret — **no explicit format
  marker needed here**, unlike Step 3's field encryption: an HMAC
  mismatch is unambiguous (no "successfully decodes to garbage" risk
  the way base64-decodability was for encryption), so trying both is
  safe.

## Files created

- `src/responsibleai/governance/crypto/signing.py`
- `docs/enterprise-neural/02_PHASE2_STEP4_REPORT.md` (this file)

## Files modified

- `src/responsibleai/governance/crypto/__init__.py` — exports `sign`/
  `verify`, module docstring extended.
- `src/responsibleai/auth/saml.py` — dual-scheme session signing, module
  docstring extended with the scope-correction reasoning.
- `tests/test_saml.py` — 6 new tests, autouse reset fixture for the new
  module-global cache.
- `CHANGELOG.md` — new entry.

## Database migrations

None this step.

## Security properties added

Session-token signing key rotation, correctly scoped (a genuinely
internal secret gets genuine rotation infrastructure). No new security
property claimed for webhook signing — correctly, since none was added
there.

## Privacy properties added

None new this step.

## Trust boundaries changed

None yet — `configure_session_signing_key()` is never called by
`dashboard/app.py` (same "mechanism, not activation" scope boundary as
Step 3). Every existing SAML deployment continues on the legacy-secret-
only path unless and until that startup wiring is added.

## Threats mitigated

None newly mitigated *in production* (nothing calls the new scheme yet)
— the mechanism is verified correct in isolation, same posture as Step 3.

## Threats not yet mitigated

Same as prior steps — no application-startup activation yet. Webhook
signing rotation remains genuinely unsolved (not by omission — see Scope
correction; a real solution there would look different: per-webhook
secret rotation coordinated with each receiver, not an internal
`KeyProvider`, and is out of this phase's scope entirely).

## Known limitations

A session token minted under a new-scheme key that is later rotated
stops validating once the old key is no longer the active one — no
multi-version-try fallback exists for the new scheme the way legacy
Fernet's `MultiFernet` tries every key in a list. Accepted deliberately:
session tokens have only a 1-hour TTL, so the exposure window for this
is small and bounded, and building a full rotation-history mechanism for
a token this short-lived isn't proportionate. Documented in
`validate_session_token`'s own docstring, not left implicit.

## Unit test results

`tests/test_saml.py`: 48 tests total (42 pre-existing, unmodified in
behavior, 6 new — `TestConfigureSessionSigningKey` (1),
`TestSessionTokenNewScheme` (4: round trip, legacy-token-still-valid-
after-activation, tamper rejection, clear-reverts-to-legacy)). All
passing.

## Integration test results

`test_legacy_token_still_validates_after_new_scheme_activated` is
genuinely integration-level: mints a token under the legacy path,
activates the new scheme, confirms the old token still validates —
exercising the actual fallback-order logic end to end, not a mock.

## Property test results

None new — same reasoning as Step 3 (example-based tests are
appropriate for this scope; `signing.py`'s primitives are simple enough
that Step 1's envelope-level property-test coverage pattern wasn't
duplicated here).

## Fuzz results

Not run — same reasoning as prior steps.

## Adversarial test results

Tamper rejection explicitly tested for the new scheme
(`test_new_scheme_tampered_token_is_rejected`); wrong-secret rejection
already covered by the pre-existing `test_wrong_secret_is_rejected` for
the legacy path, unaffected by this change.

## Regression results

Full suite: **2954 passed, 0 failed**, 78.69s
(`/tmp/full_run_phase2_step4.log`). No failures required fixing this
step — the scope correction was made *before* writing implementation
code (based on reading `webhooks/manager.py`'s actual secret-sharing
model), not discovered by a broken test.

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

Fully backward compatible — verified via the full existing test suite
(2954 tests, including every SAML/session-token test) passing unmodified
in behavior; the new scheme is inert until
`configure_session_signing_key()` is explicitly called, which nothing in
the shipped codebase does.

## Migration result

Not applicable this step.

## Rollback procedure

Revert `auth/saml.py` and delete `governance/crypto/signing.py`; revert
`governance/crypto/__init__.py`'s export addition; revert
`tests/test_saml.py`'s additions. No stored data depends on the new
scheme.

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md`, `auth/saml.py` and
`governance/crypto/signing.py`'s own module docstrings (both carry the
scope-correction reasoning at the point of use, not only in this report).

## Claims now supported by evidence

"SAML session-token signing can use the new `governance/crypto`-based
key-rotation scheme, correctly falling back to legacy tokens/secrets
during a transition window, fail-closed on tampering" — true, evidenced
above.

## Claims still unsupported

"Webhook payload signing has been migrated to the new scheme" — false,
and **should not become true** without a materially different design
(see Scope correction) — not merely "not done yet." "The new SAML
scheme is active in production" — false; no app-startup wiring exists.

## Residual risks

Same application-startup-wiring gap as Steps 1-3, now spanning three
call sites (`db/encryption.py`, `auth/saml.py`, and — once it exists —
whatever the eventual per-receiver webhook-secret rotation design turns
out to be). Worth wiring all of them together in one startup-sequence
change rather than one-off, once that change is scoped.

## Next-phase dependencies

Step 5 (generalized rotation script, successor to
`scripts/rotate_field_encryption_key.py`) remains. Given this step's
finding, Step 5's scope should explicitly exclude webhook secrets from
whatever "generalized" rotation tooling it builds, or explicitly design
a *separate* per-receiver-coordinated rotation flow for them — not
silently fold them into the same script as field encryption and session
signing.
