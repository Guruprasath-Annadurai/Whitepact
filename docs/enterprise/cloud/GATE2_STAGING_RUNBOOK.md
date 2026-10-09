# Gate 2 staging runbook (dry run)

This runbook prepares the next gate. It does not change Cloudflare, DNS, R2, Hetzner, or GCP.

## Edge

Cloudflare proxies an A record to the Hetzner load balancer. TLS mode is Full (strict). The origin checks the Cloudflare client certificate (authenticated origin pull). HSTS starts at `max-age=0`, then 300 seconds, then 86400 seconds with `includeSubDomains`. Preload stays off until the owner asks for it.

WAF baseline is the Cloudflare managed ruleset plus OWASP core, created only when the account plan flag is set. Rate limits are route-specific (login, signup, API, MCP, webhooks, exports, health) and are not production-tuned until staging evidence exists.

The contract is `scripts/cloud/gate2/edge-contract.json`. Check it with:

```bash
python3 scripts/cloud/gate2/verify_dry_run.py
```

## Origin lockdown

Before cutover, only the NAT server has a public address and SSH is limited to the founder `/32`. After cutover the Hetzner load balancer still accepts TCP/443 from the public Internet. It cannot restrict that port to Cloudflare CIDRs. A direct client reaches the origin TLS listener and is rejected unless it presents the Cloudflare authenticated-origin certificate. SaaS, authority, and execution stay without public IPv4. The verifier reads `saas_public_ipv4 = false` from the staging root and does not edit it.

## Backup and restore

Postgres dumps are gzip-compressed and encrypted with Fernet (authenticated AES-CBC plus HMAC) before any upload. The key is `WHITEPACT_BACKUP_ENCRYPTION_KEY` and is not stored next to the object. R2 credentials are not the backup key. Plaintext `.sql.gz` is not uploaded. Staging retention is 30 days and never deletes the newest viable recovery points. Restore validates the manifest before it creates a staging database. The active database is not dropped first. A restore is accepted only when the decrypted checksum matches and the staging checks pass.

Local proof, with no bucket creation:

```bash
bash scripts/cloud/gate2/backup_restore_dry_run.sh
```

`--upload` is refused.

## Drill, alerts, rollback

A drill is the local encrypt/decrypt script plus a later restore into an empty staging database after apply is authorized. Alert if a backup is older than 26 hours, origin TLS fails, or the drill fails.

Rollback of a bad Gate 2 cutover, once it exists, is: set the hostname back to DNS-only, remove the origin-pull requirement, and keep the private tiers unchanged. This branch does not perform that change.

Deploy and rollback of the servers themselves stay behind Owner Gate 1. No apply is authorized here.
