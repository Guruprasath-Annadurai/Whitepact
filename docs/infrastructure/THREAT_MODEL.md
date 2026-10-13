# Enterprise Cloud V1 — Threat model (infrastructure layer)

**Status:** IMPLEMENTED_NOT_DEPLOYED  
Complements `SECURITY_THREAT_MODEL.md` (application).

## Assets

- PostgreSQL (grants, nonces, audit chains, tenant data)
- Signing / policy configuration (authority tier)
- API keys, OIDC client secrets (secrets manager — not in git)
- R2/GCS backup objects
- Hetzner load balancer origin IP

## Threats and mitigations

| Threat | Mitigation | Verification |
|--------|------------|--------------|
| Agent executes without grant | App authority kernel + MCP integration | `tests/test_phase7a_authority_kernel.py`, staging Stage 3 |
| Cross-tenant access | RBAC + org scoping | B4 security-state HTTP tests (Cell B) |
| Replay / expired / revoked grant | Nonce + epoch + TTL | Repository + B4 adversarial restore |
| Compromised execution node | No public IP; egress allowlist; no signing keys on exec | Hetzner firewall module |
| Direct origin bypass | Cloudflare proxied DNS only; origin firewall allows LB paths | TESTED_IN_SIMULATION (config); live test OWNER_APPROVAL |
| Secret leakage in backups | `age` encrypt before R2; separate backup IAM | `backup-encrypt-r2.sh.example` |
| Backup tampering / deletion | R2 versioning + retention; separate credentials | OWNER_APPROVAL for lock policies |
| Stale backup restores authority | Application must reject stale epochs/nonces post-restore | B4 security-state rehearsal |
| Cloudflare outage | Documented: DNS/cache only; origin on Hetzner | BACKUP_AND_DISASTER_RECOVERY.md |
| GCP credit expiry | No mandatory prod dependency | Architecture doc |

## Out of scope for IaC pass

- Live penetration test  
- SOC 2 / ISO claims  
- Production WAF rule tuning without owner plan tier
