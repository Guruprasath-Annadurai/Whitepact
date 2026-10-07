# Backup and restore evidence

## R2 path (private PostgreSQL — no DB inbound exposure)

```
PostgreSQL (authority, private)
  → pg_dump local (scripts/backup-postgres.sh)
  → gzip
  → Fernet authenticated encryption. The token binds schema version, database name, compression, dump format, required relations, and plaintext hash. The sidecar timestamp and tool version are shape-checked only.
  → upload ciphertext only (scripts/cloud/upload-backup-to-r2.sh)
  → outbound TCP 443 via Hetzner network route 0.0.0.0/0 → NAT gateway → Internet
  → Cloudflare R2 (private bucket)
```

- **No** public PostgreSQL port.
- **No** inbound connection from R2 to the database.
- Restore: download from R2 through NAT → disposable Postgres instance → verify → app smoke.

Live execution pending Owner Gate 1.
