# Key Management — `RAI_FIELD_ENCRYPTION_KEY`

> Scope: this document covers the opt-in application-layer field encryption
> key (`db/encryption.py`, `RAI_FIELD_ENCRYPTION_KEY`) — the key that
> encrypts specific PII/secret columns (`audit_log.ip_address`,
> `public_incident_reports.reporter_name`/`.reporter_contact`,
> `webhook_configs.secret`, `org_api_keys.mfa_secret`). It does **not**
> cover whole-database encryption at rest, which is the deployer's
> infrastructure responsibility (disk/volume encryption — see
> `ENTERPRISE_SECURITY.md`), nor TLS/transport encryption, nor Postgres's
> own credentials. Those have their own custody stories; this document is
> specifically about the one key this application generates and manages
> ciphertext with.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. Generating a key

```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

This produces a single Fernet key (256 bits, base64-encoded). Set it as
`RAI_FIELD_ENCRYPTION_KEY` in `.env.prod` (or wherever your deployment
reads environment variables from) — never commit it to git, never put it
in a Dockerfile `ENV` instruction, and never log it.

---

## 2. Custody — where this key should actually live

**Do not** store this key in:
- The git repository, in any form (including "encrypted" — if the
  decryption key for *that* also lives in the repo, nothing is protected).
- A Docker image layer, `Dockerfile ENV`, or `docker-compose.yml` inline
  value.
- Application logs, error messages, or crash reports — `db/encryption.py`'s
  error path deliberately never echoes the key value back, only a generic
  "not a valid Fernet key" message.

**Do** store it in one of, in order of preference for a production
deployment:
1. A secrets manager your infrastructure already has (AWS Secrets Manager,
   GCP Secret Manager, HashiCorp Vault, Doppler, etc.), injected into the
   container's environment at start time.
2. Your VPS provider's own secret/environment-variable feature, if it has
   one separate from plain files.
3. `.env.prod` with `chmod 600`, on a host you control, as the baseline —
   this is what `DEPLOY_RUNBOOK.md` and `scripts/deploy.sh` currently do,
   and it's an acceptable starting point for a single-VPS deployment, but
   graduate to (1) or (2) once you have real customer data at stake.

Whoever holds this key can read every field it protects across every
tenant, in plaintext, given raw database access. Treat it with the same
seriousness as a database root password — restrict who has access to the
value itself (not just who can restart the service with it configured).

---

## 3. Rotation procedure

`RAI_FIELD_ENCRYPTION_KEY` accepts a comma-separated list of keys, not just
one — this is what makes rotation possible without a maintenance window
where some rows are unreadable.

1. **Generate a new key** (Section 1).
2. **Prepend it** to the existing value: `RAI_FIELD_ENCRYPTION_KEY=<new>,<old>`.
   Order matters — the *first* key encrypts all new writes; every key in
   the list is tried on read, so old ciphertext keeps working.
3. **Restart the application** (or redeploy) with the updated value. At
   this point: new writes use the new key, old rows are still readable
   (via the old key, still in the list) but not yet re-encrypted.
4. **Run the re-encryption sweep**:
   ```bash
   RAI_FIELD_ENCRYPTION_KEY="<new>,<old>" RAI_DATABASE_URL=... \
       python scripts/rotate_field_encryption_key.py
   ```
   This reads every row of every encrypted column (which decrypts via
   whichever key in the list matches) and writes it back unchanged (which
   always encrypts with the current first key) — after it completes, every
   row is under the new key.
5. **Verify** — spot-check a few rows, or re-run the sweep script with only
   the new key set (`RAI_FIELD_ENCRYPTION_KEY=<new>`) against a **read
   replica or backup**, not production, to confirm nothing depends on the
   old key anymore before you drop it for real.
6. **Drop the old key**: set `RAI_FIELD_ENCRYPTION_KEY=<new>` (just the new
   one) and restart. Only do this after step 5's verification — dropping
   the old key before every row is confirmed re-encrypted will make any
   remaining old-key rows silently fall back to the "pre-encryption
   plaintext" passthrough path in `EncryptedString.process_result_value`
   (returning whatever's stored as-is, which for a row still under the old
   key is unreadable ciphertext, not a crash — worth knowing that failure
   mode is silent, not loud).
7. **Destroy the old key** wherever it was held in custody (Section 2) —
   rotation isn't complete until the retired key is actually gone, not just
   unused.

**How often**: no hardcoded schedule enforced by the code. A reasonable
baseline for a solo-maintained project: annually, or immediately if the key
is ever suspected of exposure (a leaked `.env.prod`, a compromised host, an
departing team member who had access). Document whenever a real rotation
happens — this file doesn't track rotation history itself; that belongs in
your own operational log or `CHANGELOG.md`.

---

## 4. What this does *not* cover

- **Whole-database encryption at rest** — infrastructure-layer, deployer's
  responsibility (see `ENTERPRISE_SECURITY.md`).
- **Backups** — `scripts/backup-postgres.sh` produces a `pg_dump` file that
  contains the *ciphertext* for encrypted columns (since the dump is taken
  at the database layer, below the application's encryption), but plaintext
  for every other column. Encrypt the backup file itself at the storage
  layer if it needs to be protected as a whole — this key doesn't do that.
- **Multi-key custody across independent trust boundaries** (e.g., a
  customer bringing their own key, envelope encryption with a KMS) — this
  is a single, application-wide key, not per-tenant. A per-tenant
  bring-your-own-key model would be a materially larger feature, not a
  configuration change to this one.
