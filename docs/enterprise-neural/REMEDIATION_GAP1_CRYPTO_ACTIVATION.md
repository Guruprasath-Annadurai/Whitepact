# Remediation Gap 1 — Crypto Foundation Activation: Design

## Reproduction (before assuming the documented finding is correct)

Confirmed by direct source inspection at the frozen PR #50 head
(`9d1fdad`), re-confirmed on this remediation branch:

- `configure_field_encryption_key()`/`configure_session_signing_key()`
  have zero call sites in `src/responsibleai/` outside their own
  definitions and test files.
- No application-startup path (`dashboard/app.py`'s `lifespan`,
  `mcp/server.py`'s `_build_http_app()`) constructs a
  `LocalEnvelopeKeyProvider`/`CryptoKeyRepository` or calls either
  `configure_*` function.
- `EncryptedString.process_bind_param()` falls through to plaintext
  when neither the new scheme nor legacy `RAI_FIELD_ENCRYPTION_KEY` is
  configured — a real, by-design plaintext fallback.

The finding is reproduced, not assumed.

## Complete field/path inventory

**Sensitive database fields using `EncryptedString`** (`grep -rn
EncryptedString src/responsibleai/db/engine.py`):
- `audit_log.ip_address`
- `public_incident_reports.reporter_name`, `.reporter_contact`
- `org_api_keys.mfa_secret` (TOTP seed)
- `webhook_configs.secret` (HMAC signing secret)

**Signing paths**: SAML session tokens
(`auth/saml.py::mint_session_token`/`validate_session_token`) — HMAC
today, envelope-signing capable once activated.

**HMAC paths (unrelated to Phase 2's KeyProvider, out of scope for
this activation)**: webhook payload signing (`webhooks/manager.py`,
two-party secret, `HMAC-SHA256` — Phase 2's own Step 4 report already
found this correctly out of scope: the receiver, not WhitePact alone,
holds the secret, so envelope-encrypting WhitePact's own copy doesn't
change what an attacker who compromises the DB can do — they'd need
the receiver's copy too, which this database never has).

**Key lookup paths**: `_get_active_field_encryption_key()`,
`_get_active_session_signing_key()` — module-level state, set only by
the two `configure_*` functions.

**Existing failure modes** (already correct, verified in
`CODEX_REVIEW_HANDOFF.md` §4): a value carrying the new-scheme prefix
with no active key raises `DecryptionError` (fail-closed) — this path
is real and tested, just unreachable today since nothing writes the
prefix.

**Missing failure mode**: there is currently no way to require the new
scheme be active — a deployment cannot express "refuse to start unless
real encryption is configured."

## Production activation architecture

New module: `src/responsibleai/db/crypto_activation.py`.

**Settings additions** (`dashboard/config.py`), mirroring the existing
`multi_replica` self-declaration pattern exactly — non-breaking,
opt-in, no default behavior change:

- `enterprise_mode: bool = False` — shared fail-closed gate for this
  gap and (future) Gap 2's stdio governance; a self-declaration, not
  itself a behavior change on its own.
- `crypto_root_key: str | None = None` — hex-encoded 32-byte root key.
  Never logged (Pydantic's own repr would print it; the activation
  module logs only the resolved `KeyId`, never the key material or the
  raw setting value — verified by the "secrets do not appear in logs"
  test below).

**`activate_production_crypto(settings, engine) -> None`** — called
once at application startup (`dashboard/app.py`'s `lifespan`,
`mcp/server.py`'s `_build_http_app()`), **before the first request is
served**:

1. If `enterprise_mode` is `False`: no-op. Development/self-hosted
   default is completely unchanged — this is the "development
   compatibility... clearly labeled, impossible to mistake for
   enterprise production mode" requirement: the *absence* of an
   explicit `enterprise_mode=true` is what selects dev-compatible
   behavior, not a separate flag that could be left on by accident.
2. If `enterprise_mode` is `True`:
   - `crypto_root_key` must be set and decode to exactly 32 bytes —
     otherwise raise `CryptoActivationError` at startup (fail closed:
     the process does not start serving requests with encryption
     silently disabled).
   - Construct `CryptoKeyRepository(engine)` (the durable,
     DB-backed `WrappedKeyStore` — not `InMemoryWrappedKeyStore`,
     which loses all key state on restart).
   - Construct `LocalEnvelopeKeyProvider(root_key=..., environment=...,
     store=repository)`.
   - Resolve and activate the field-encryption key:
     `provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, tenant_id=None)`
     → `configure_field_encryption_key(key_id, dek)`.
   - Resolve and activate the session-signing key:
     `provider.get_encryption_key(KeyPurpose.SESSION_SIGNING, tenant_id=None)`
     → `configure_session_signing_key(key_id, dek)`.
   - Any failure in the above (bad key format, DB error) propagates —
     the application does not start.

**Backward compatibility, key versioning, rotation, revocation,
tenant/purpose/environment separation**: all already provided by the
existing `governance/crypto/` Phase 2 foundation (`KeyId` encodes
purpose+tenant+version+environment; `CryptoKeyRepository.put()` raises
`KeyVersionConflictError` on a concurrent-write race;
`LocalEnvelopeKeyProvider.rotate()`/`.revoke()` already exist and are
tested) — this activation module adds no new crypto logic, only the
startup wiring that was previously missing.

**KMS/HSM extensibility**: unchanged from Phase 12's finding — the
`KeyProvider` Protocol is the seam; `activate_production_crypto()`
constructs a `LocalEnvelopeKeyProvider` today, but any future
`AWSKMSKeyProvider`/`VaultTransitKeyProvider` implementing the same
Protocol would need only this one construction site changed, not any
caller. **No fake KMS is implemented in this pass** — `LocalEnvelopeKeyProvider`
is the one real, testable, production-capable route the directive asks
for; a real cloud-KMS integration remains out of scope without a named
provider and credentials to test against (unchanged reasoning from
Phase 12).

**Never logged, never embedded in source**: `crypto_root_key` is read
from environment/`.env` only (Pydantic Settings' existing mechanism);
the activation module's own logging (see implementation) logs only
`key_id.to_string()` (purpose/tenant/version/environment — never
secret material) and never the setting value or resolved DEK bytes.

## What this does not do (explicitly out of scope for this pass)

- Does not implement a real cloud KMS/HSM backend.
- Does not migrate existing legacy-Fernet-encrypted data to the new
  scheme (a rotation-script concern, already handled by
  `scripts/rotate_field_encryption_key.py` from Phase 2 Step 5 —
  unaffected by this activation work).
- Does not change webhook HMAC signing (correctly out of scope,
  two-party secret).
