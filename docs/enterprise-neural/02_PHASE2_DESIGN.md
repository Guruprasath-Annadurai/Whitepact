# Phase 2 — Cryptographic Foundation + Key Management: Design

STATUS: Design only. No runtime code changed by this document.

## 1. Existing cryptographic usage — full inventory (ground truth)

| Use | Location | Primitive | Key origin today | Rotation today |
|---|---|---|---|---|
| Field-level encryption (`audit_log.ip_address`, `public_incident_reports.reporter_name`/`.reporter_contact`, `org_api_keys.mfa_secret`, `webhook_configs.secret`) | `db/encryption.py` (`EncryptedString`) | Fernet (AES-128-CBC + HMAC-SHA256) via `MultiFernet` | `RAI_FIELD_ENCRYPTION_KEY` env var, comma-separated key list | **Yes, real** — prepend new key, `scripts/rotate_field_encryption_key.py` re-encrypts, drop old key after verification. Documented in `compliance/KEY_MANAGEMENT.md`. |
| API-key storage | `db/org_repository.py::_hash_key` | SHA-256 (one-way hash, not encryption — correct primitive for "verify without recovering") | N/A — hash has no key | N/A |
| Webhook payload signing | `webhooks/manager.py` | HMAC-SHA256 | Per-webhook `config.secret`, deployer-supplied at registration time, floor-validated by `crypto_policy.py::validate_webhook_secret` (≥32 chars) | **No rotation mechanism** — a deployer must manually update `config.secret` and reconfigure the receiving endpoint; no dual-secret transition period exists. |
| OIDC JWT verification | `auth/oidc.py` | RS256/RS384/RS512/ES256/ES384/ES512 via `PyJWT[crypto]`, public key fetched from the IdP's own JWKS endpoint | **Not WhitePact's key at all** — this is verification of a key the IdP controls and rotates on its own schedule via its published JWKS (`kid`-based lookup, `AsyncJWKSClient` re-fetches hourly). `crypto_policy.py::validate_rsa_key_size` rejects any key under 2048 bits. | IdP's responsibility, transparent to WhitePact via JWKS `kid` rotation. |
| SAML response signature verification | `auth/saml.py` | XML-DSig via `signxml.XMLVerifier`, IdP's own signing certificate | IdP's key, same trust model as OIDC's JWKS | IdP's responsibility. |
| SAML post-login session token | `auth/saml.py::mint_session_token` | HMAC-SHA256 | `SAMLConfig.session_secret`, deployer-configured | **No rotation mechanism** documented. |
| Audit-log tamper-evidence hash chain | `db/audit_repository.py::_compute_entry_hash` | SHA-256, chained (`entry_hash = sha256(prev_hash + fields)`) | N/A — this is a hash chain, not encryption; no key exists to rotate | N/A |
| `ExecutionAuthorization.action_digest` | `governance/execution.py`, via `governance/approval.py::compute_action_digest` | SHA-256 canonical digest, **deliberately unsigned** | N/A — same reasoning as the hash chain; the module's own docstring explains why signing would be premature (never crosses a process/trust boundary today) | N/A |
| `AuthorityGrant.canonical_digest` (Heart, Production Integration Phase 1) | `governance/authority_grant.py` | SHA-256 canonical digest, tamper-*evidence*, not tamper-*proof* | N/A | N/A |
| API-generated secrets (raw API keys, TOTP seeds) | `db/org_repository.py` (`secrets.token_urlsafe(32)`), `auth/mfa.py` (`pyotp.random_base32()`) | CSPRNG generation, not encryption | Generated fresh per credential, never reused | N/A — one-shot generation, revocation is the "rotation" equivalent (`revoke_key`) |
| Sigstore build provenance / signed release tags | `.github/workflows/publish.yml` | Sigstore OIDC keyless signing (build provenance); SSH-signature verification against `security/release-signers.allowed` (release tags) | Sigstore's own ephemeral keys (build provenance); the founder's own SSH key (release signing) | Managed entirely outside this application — GitHub Actions OIDC + Sigstore Fulcio/Rekor, and the founder's personal key custody. Out of scope for an application-level KMS. |

**Existing floor-enforcement**: `governance/crypto_policy.py` (referenced by
`auth/oidc.py` and implicitly by webhook secret validation) already
enforces NIST-aligned minimums (2048-bit RSA, 32-char/256-bit-equivalent
HMAC secrets) on the two places this codebase trusts an *externally
supplied* key. This is real, current, and should be extended to, not
replaced by, Phase 2's work.

## 2. What Phase 2 is actually solving

The gap is narrower than "no cryptography exists" — cryptography here is
already correctly chosen (Fernet, HMAC-SHA256, RS/ES-family JWT
verification, real XML-DSig via `signxml`, CSPRNG generation) and mostly
well-documented. The real gaps, precisely:

1. **`RAI_FIELD_ENCRYPTION_KEY` is a single, flat, application-wide key** —
   no purpose separation (the same key protects `audit_log.ip_address`,
   `webhook_configs.secret`, and `org_api_keys.mfa_secret` alike), no
   tenant separation, no key IDs distinguishable from key material (a key
   *is* its own identifier — you can't ask "which key encrypted this row"
   without trying to decrypt with each candidate).
2. **No KMS/HSM-capable abstraction exists** — the Fernet mechanism is
   the only "key management" in the codebase, and it is not designed to
   be swapped for a managed KMS later without touching every call site.
3. **Webhook secrets and SAML session secrets have no rotation
   mechanism** at all (unlike field encryption, which has a real,
   documented one).
4. **No envelope encryption** — one key directly encrypts data, rather
   than a root key wrapping per-purpose/per-tenant data keys.

## 3. Target architecture

### 3.1 Key hierarchy

```
Root Key-Encrypting-Key (KEK)
  — one per environment (dev/test/prod), held by the KeyProvider backend
  ↓ wraps
Purpose+Tenant Data-Encrypting-Keys (DEK)
  — e.g. (purpose="field_encryption", tenant=org_id)
  — e.g. (purpose="webhook_signing", tenant=org_id)
  — e.g. (purpose="audit_evidence", tenant=None — chain is process-global)
  ↓ encrypts/signs
Actual data (field values, webhook payloads, future NeuralIntent
attestations if that initiative proceeds)
```

This is a genuine hierarchy change from today's flat model: today
`RAI_FIELD_ENCRYPTION_KEY` *is* the DEK, directly. The target makes it a
KEK that wraps per-purpose DEKs, so purposes can be rotated and revoked
independently (Requirement 2, 5 below) and a future per-tenant
bring-your-own-key model (explicitly out of scope for Phase 2, per
`compliance/KEY_MANAGEMENT.md` §4's own existing statement) has somewhere
to attach without a redesign.

### 3.2 Key purpose separation

Enumerate purposes as a closed, versioned set (mirrors the existing
`_KIND_TO_ROOT_TYPE`-style explicit-mapping-table pattern already used in
`governance/identity_authority_adapter.py`):

```python
class KeyPurpose(StrEnum):
    FIELD_ENCRYPTION = "field_encryption"  # replaces RAI_FIELD_ENCRYPTION_KEY's current sole job
    WEBHOOK_SIGNING = "webhook_signing"  # new: gives webhook secrets real rotation
    SESSION_SIGNING = "session_signing"  # new: SAML/OIDC-adjacent session tokens
    AUDIT_ANCHOR = "audit_anchor"  # new, Phase 13 dependency: external evidence-chain anchoring
```

A DEK for one purpose must never decrypt/verify data written under
another purpose — enforced by binding the purpose into the wrapped-key
request itself (the provider interface takes `purpose` as a required
parameter, not an optional hint), so a caller cannot accidentally request
the wrong DEK and get a false negative/positive.

### 3.3 Key identifiers and versions

```python
@dataclass(frozen=True)
class KeyId:
    purpose: KeyPurpose
    tenant_id: str | None  # None = application-global (e.g. audit anchor)
    version: int  # monotonic, starts at 1
    environment: str  # "dev" | "test" | "prod" — never cross-loadable
```

Ciphertext/ signatures produced under this design carry their `KeyId` as
associated (unencrypted, authenticated) metadata — AEAD's "additional
authenticated data" (AAD) — so a wrong-key or wrong-purpose decrypt
attempt fails fast on ID mismatch before even attempting the
cryptographic operation, and so old ciphertext is self-describing for
rotation sweeps (today's `scripts/rotate_field_encryption_key.py` has to
try-decrypt blindly with `MultiFernet`; the target design can look up the
exact key by ID first).

### 3.4 Rotation

Generalizes the existing, already-correct field-encryption rotation
procedure (Section 1 above) to every purpose:
1. Generate new DEK version for `(purpose, tenant)`.
2. New writes use the new version immediately (`KeyProvider` always
   returns the highest version for encryption).
3. Reads resolve by the `KeyId` embedded in the ciphertext's AAD — no
   more try-every-key `MultiFernet` fallback needed once IDs are embedded,
   though the transition period from today's un-versioned ciphertext
   still needs try-fallback (see Migration, §14).
4. Re-encryption sweep script (generalizing
   `rotate_field_encryption_key.py` to be purpose-aware) moves old-version
   data to the new version.
5. Old version is marked `retired` (revoked for new use, still
   decryptable) until a sweep confirms zero rows reference it, then purged
   from the provider.

### 3.5 Revocation

A DEK version can be marked `revoked` (not just `retired`) when a key is
suspected compromised — `revoked` differs from `retired` in that
decryption is refused even for old data (fail closed), whereas `retired`
still permits decrypting pre-existing data during a graceful rotation
window. This distinction doesn't exist in the current Fernet mechanism
(there's only "in the list" or "not in the list").

### 3.6 Expiry

Session-signing and audit-anchor purposes get a mandatory `expires_at` on
each key version (a session-signing key that's never rotated forever is a
standing risk); field-encryption and webhook-signing DEKs are
rotation-driven rather than time-expiry-driven (data encrypted under them
must remain readable indefinitely per business need — see Migration/
compat notes).

### 3.7 KMS/HSM provider abstraction

```python
class KeyProvider(Protocol):
    async def get_encryption_key(
        self, purpose: KeyPurpose, tenant_id: str | None
    ) -> tuple[KeyId, bytes]: ...
    async def get_decryption_key(self, key_id: KeyId) -> bytes: ...
    async def rotate(self, purpose: KeyPurpose, tenant_id: str | None) -> KeyId: ...
    async def revoke(self, key_id: KeyId) -> None: ...
    async def retire(self, key_id: KeyId) -> None: ...
```

Every call site (`db/encryption.py`, `webhooks/manager.py`, `auth/saml.py`)
depends on this Protocol, never on a concrete provider — this is the
seam a future `AWSKMSKeyProvider`/`VaultTransitKeyProvider` plugs into
without touching business logic, per the directive's explicit requirement.

### 3.8 The one production-capable path this phase actually builds

Per the directive: build the correct provider contract plus **one**
genuinely production-capable path, not every cloud KMS. Given WhitePact's
own stated constitutional requirement to remain "cloud independent,
vendor independent" (`ENTERPRISE_SECURITY.md`'s posture, and this
directive's own "PRIMARY PRODUCT" section), and that the existing
reference deployment is a specific vendor stack (Render/Supabase) while
self-hosted deployment is the default and most common path
(`ENTERPRISE_SECURITY.md` "Data residency" table) — the chosen production
path is:

**`LocalEnvelopeKeyProvider`**: a real envelope-encryption implementation
where the root KEK comes from `RAI_ROOT_KEY` (or a
`RAI_ROOT_KEY_PROVIDER=file:///path` / secrets-manager-injected env var,
same custody guidance `compliance/KEY_MANAGEMENT.md` already gives for
today's field-encryption key), and DEKs are generated per purpose/tenant,
wrapped (AES-256-GCM, KEK-wrapping-DEK) and persisted in a new
`crypto_keys` table (`key_id` columns + wrapped DEK ciphertext + status +
timestamps — never plaintext DEK material at rest). This is not "an env
var dictionary pretending to be a KMS" — it performs real envelope
encryption with real key hierarchy, versioning, and revocation state
machine; it is simply self-hosted rather than calling out to a managed
HSM. `AWSKMSKeyProvider` (or Vault Transit) becomes a documented,
interface-conforming future addition — not built in Phase 2 — for
deployments that want the root KEK held in an actual managed HSM instead
of an env-var-derived key.

### 3.9 Envelope encryption

Concretely: KEK (from `RAI_ROOT_KEY`, via HKDF-derived per-purpose
sub-keys — never the raw root key used to encrypt data directly) wraps a
randomly generated DEK using AES-256-GCM key wrap; the DEK, also
AES-256-GCM, encrypts/decrypts the actual field value. This gives
constant-time key rotation for the *root* (re-wrap DEKs, cheap) separate
from data re-encryption (re-encrypt-and-rewrite rows, expensive, only
needed when a DEK itself is compromised) — a real operational win over
today's model where every rotation requires a full data sweep.

### 3.10 AEAD choice

**AES-256-GCM** (via `cryptography.hazmat.primitives.ciphers.aead.AESGCM`,
already a transitive dependency, already vetted — no new dependency
needed) for both KEK-wrapping and DEK-encryption. Chosen over
ChaCha20-Poly1305 for this codebase specifically because: (a) it is what
`cryptography`'s own `AESGCM`/`AESGCMSIV` classes provide without adding a
new dependency, (b) hardware AES-NI is universally available on the
deployment targets this project documents (self-hosted x86/ARM VPS,
managed Postgres providers), so there's no meaningful performance reason
to prefer ChaCha20-Poly1305's software-only advantage here. Nonces:
96-bit, `os.urandom(12)` per encryption (never derived, never reused —
GCM's catastrophic failure mode) stored alongside ciphertext (not secret).

### 3.11 Canonical signing/verification interface

Generalizes the existing `hmac.new(secret, body, hashlib.sha256)` pattern
in `webhooks/manager.py` and `auth/saml.py` into one shared function that
both call, taking a `KeyId`-resolved key from `KeyProvider` instead of a
raw deployer-supplied string — closes the "no rotation for webhook/session
secrets" gap (§1) by giving them the same versioned-key rotation as field
encryption, for free, once they're on the same provider.

### 3.12 Tenant isolation

`KeyId.tenant_id` is a required dimension of every key lookup for
tenant-scoped purposes (`field_encryption`, `webhook_signing`) — a
`KeyProvider` implementation must refuse (not silently ignore) a request
for tenant B's data encrypted with tenant A's key context. This is
enforced at the `KeyProvider` interface level, not left to callers to get
right — the same "don't rely on handlers remembering to add org_id
manually" principle the directive's own §14 (tenant isolation) states,
applied to key material specifically.

### 3.13 Dev/test/prod separation

`KeyId.environment` is part of every key's identity; a
`LocalEnvelopeKeyProvider` instance is constructed with a fixed
environment value at startup (from the same config source that already
distinguishes `RAI_DATABASE_URL` dev/test/prod, not a new mechanism) and
refuses to load or produce keys tagged for a different environment — a
key generated in `dev` structurally cannot decrypt `prod` data even if
the env-var files were accidentally mixed up.

### 3.14 Migration from current Fernet field encryption

Breaking-change analysis: **not a hard break** if sequenced correctly.
- Existing `RAI_FIELD_ENCRYPTION_KEY`-encrypted columns keep working
  during a transition window: `EncryptedString`'s decrypt path tries the
  new `KeyProvider`-resolved key first (by embedded `KeyId` in AAD), and
  falls back to the legacy flat-Fernet `MultiFernet` path for ciphertext
  written before migration (recognizable by absence of the new AAD
  envelope format — old Fernet tokens don't carry it).
- A migration script (parallel to `rotate_field_encryption_key.py`) sweeps
  existing rows: decrypt with legacy Fernet, re-encrypt via the new
  `KeyProvider` under `KeyPurpose.FIELD_ENCRYPTION`.
- Old `RAI_FIELD_ENCRYPTION_KEY` env var stays supported (read-only,
  legacy-fallback path) until an explicit deprecation is announced in
  `CHANGELOG.md`/`RELEASING.md` — consistent with this project's stated
  backward-compatibility discipline.

### 3.15 Backwards compatibility

No public Python API, CLI, MCP, or HTTP API signature changes — this is
entirely internal to `db/encryption.py`, `webhooks/manager.py`,
`auth/saml.py`'s implementation, not their call sites' contracts. The only
externally visible change is a **new**, optional `RAI_ROOT_KEY` env var;
`RAI_FIELD_ENCRYPTION_KEY` continues to work unmodified for any deployer
who doesn't opt into migration immediately.

### 3.16 Failure behavior when KMS is unavailable

`LocalEnvelopeKeyProvider` has no external network dependency (root key
is local env/file-backed), so "KMS unavailable" mainly matters for a
*future* `AWSKMSKeyProvider`. Design the `KeyProvider` Protocol's
contract now so that failure mode is specified up front: any
`get_encryption_key`/`get_decryption_key` call that cannot reach its
backend **raises**, never silently falls back to plaintext or a
default key — the calling `EncryptedString`/webhook-signing/
session-token code must propagate that failure and refuse the operation
(fail closed), matching Law 7 ("MISSING SECURITY CONTEXT = DENY") and the
existing `EvidenceRepository.record()` fail-closed precedent in
`mcp/governance_integration.py`.

### 3.17 Backup/recovery implications

Root KEK custody (§3.8, same guidance as today's `compliance/
KEY_MANAGEMENT.md` §2) is the single recovery-critical secret — losing it
makes every wrapped DEK, and therefore all encrypted data, permanently
unreadable. The new `crypto_keys` table (wrapped DEKs) is backed up
alongside the rest of the database by existing backup tooling
(`scripts/backup-postgres.sh`) — wrapped DEK ciphertext is safe to include
in a database backup (it's useless without the KEK, held separately per
custody guidance), unlike a hypothetical design that stored raw DEKs.

### 3.18 Auditability without secret leakage

Every `KeyProvider` operation (rotate, revoke, retire, and — notably —
every `get_decryption_key` call, since "who decrypted what, when" is
itself security-relevant) emits an audit event via the existing
`EvidenceRepository`/`AuditRepository` machinery, carrying `KeyId` (safe —
it's a purpose/tenant/version/environment tuple, not secret material) and
never the key bytes themselves — consistent with this codebase's existing
discipline (`EvidenceRecord` never stores raw argument values;
`db/encryption.py`'s error path never echoes key values).

### 3.19 Zero-downtime key rotation

Follows directly from §3.4: because DEKs are wrapped by a KEK rather than
directly holding data, rotating the KEK only requires re-wrapping DEKs
(fast, no data table scan) — a genuinely zero-downtime operation distinct
from rotating a DEK itself (which does require the existing-pattern data
sweep, same cost as today's Fernet rotation, but now scoped to one
purpose/tenant at a time instead of the whole database).

### 3.20 Tests for cryptographic misuse (design-level test plan)

Maps directly to the directive's non-negotiable Phase 2 test list — see
§4 below for the concrete mapping to this design's objects.

## 4. Non-negotiable Phase 2 tests — mapped to this design

| Required test | How this design satisfies it |
|---|---|
| Corrupted ciphertext → reject | AES-GCM's authentication tag fails verification on any bit-flip; `KeyProvider.get_decryption_key` callers must catch `InvalidTag` and re-raise a typed `DecryptionError`, never a bare passthrough |
| Modified authenticated metadata → reject | `KeyId` is embedded in GCM's AAD — GCM cryptographically binds AAD to the ciphertext; tampering with the embedded `KeyId` breaks the auth tag the same as tampering with ciphertext |
| Wrong tenant key → reject | `KeyProvider.get_decryption_key(key_id)` with a `tenant_id` mismatch against the caller's actual tenant context must be checked at the call site (defense in depth beyond AAD binding) — test constructs ciphertext for tenant A, attempts decrypt as tenant B, asserts refusal |
| Wrong-purpose key → reject | Same mechanism — `KeyPurpose` mismatch, either via AAD binding or explicit `KeyId.purpose` check |
| Revoked key → reject | `revoke()` transitions state; `get_decryption_key` on a `revoked` (not merely `retired`) key raises unconditionally |
| Unsupported key version → reject | A `KeyId.version` with no corresponding stored wrapped-DEK row raises `KeyNotFoundError`, never silently generates a new key |
| Nonce misuse cannot occur through public API | No public method accepts a caller-supplied nonce; every encryption call generates its own via `os.urandom(12)` internally — test asserts the public interface has no nonce parameter to misuse |
| Malformed encrypted envelope → reject | AAD/ciphertext parsing (envelope format: `key_id \| nonce \| ciphertext \| tag`) raises `ValueError` on any structurally invalid input, tested with truncated/reordered/extra-field envelopes |
| Missing KMS → fail closed for security-critical operations | Per §3.16 — provider raises, caller propagates, no plaintext fallback |
| Rotation old→new works | Property test: encrypt under version N, rotate, encrypt under version N+1, both remain independently decryptable |
| Data encrypted before rotation remains readable per policy | `retired` (not `revoked`) old versions stay decryptable — test explicitly distinguishes this from the revoked case above |
| New writes use current key version | Every `get_encryption_key` call returns the highest non-revoked, non-retired version for that purpose/tenant — test asserts monotonicity |
| Secrets never appear in logs/traces/errors | Extend the existing leakage-test pattern this project already uses (`db/encryption.py`'s error path never echoes key values) to every new `KeyProvider` error path and the new audit events (§3.18) |
| Cross-tenant decryption impossible through normal application interfaces | End-to-end test through `EncryptedString`/webhook-signing call sites (not just the `KeyProvider` unit level) — tenant A's application code path can never resolve tenant B's key even via a normal (non-adversarial) code path, only via the already-tested-and-rejected direct `KeyProvider` misuse above |

## 5. What Phase 2 implementation will NOT do

- Will not implement `AWSKMSKeyProvider`/`VaultTransitKeyProvider` —
  interface-conforming stubs/documentation only, per the directive's
  explicit "do not add all cloud providers merely to inflate Phase 2."
  - Will not touch `auth/oidc.py`'s JWKS verification or `auth/saml.py`'s
  XML-DSig verification logic — those verify *externally controlled* keys
  (the IdP's), which is a different trust boundary Phase 2's KeyProvider
  doesn't own; only `mint_session_token`'s HMAC key moves onto the new
  provider (§3.11).
- Will not change the audit-log hash chain's fundamental design
  (unsigned SHA-256 chain) — external anchoring is explicitly Phase 13's
  scope, not Phase 2's; `KeyPurpose.AUDIT_ANCHOR` is defined now so Phase
  13 has a key to use, but no signing is wired into the audit chain this
  phase.
- Will not sign `ExecutionAuthorization`/`AuthorityGrant` digests — both
  modules' own docstrings already explain why that's deliberately
  deferred (never crosses a process boundary today); Phase 11 (Citadel)
  is where that reasoning gets revisited if a real cross-process executor
  is built.

## 6. Breaking-migration verdict

**Not a breaking migration.** New `crypto_keys` table (additive
migration, next number after `0029`/whatever `docs/heart-production/`
Phase 3 lands first — sequenced against that, not duplicated), new
optional `RAI_ROOT_KEY` env var, existing `RAI_FIELD_ENCRYPTION_KEY`
continues to function unmodified during and after this phase.
Rollback: drop the `crypto_keys` table, unset `RAI_ROOT_KEY`, existing
Fernet-encrypted data remains readable via the legacy path (never
removed by this phase). Mixed-version deployment (a rolling deploy with
old and new code running simultaneously against the same DB): safe,
because the legacy Fernet path is untouched and the new `crypto_keys`
table is additive — old code simply never reads it.

## 7. Implementation plan for Phase 2 (design → build sequencing)

1. `governance/crypto/` new package: `KeyPurpose`, `KeyId`, `KeyProvider`
   Protocol, `LocalEnvelopeKeyProvider`, envelope format helpers.
2. `crypto_keys` migration (additive).
3. Wire `db/encryption.py` to try new-provider-first, legacy-Fernet-
   fallback (§3.14).
4. Wire `webhooks/manager.py` and `auth/saml.py::mint_session_token` onto
   the shared canonical signing interface (§3.11).
5. Migration/rotation script generalizing
   `scripts/rotate_field_encryption_key.py`.
6. Full non-negotiable test list (§4), property-based where the directive
   requires it (rotation monotonicity, cross-tenant/purpose isolation).
7. `docs/enterprise-neural/02_PHASE2_REPORT.md` per the mandatory Phase
   Report format, only after all of the above pass.

Phase 2 design audit complete. Awaiting go-ahead to begin implementation
per Step 1 above.
