# WhitePact Enterprise Cloud V1 — Multi-provider architecture

**Status:** IMPLEMENTED_NOT_DEPLOYED (IaC in `infra/terraform/`)  
**Doctrine:** Agents may reason freely; consequential execution requires independently enforced authority.

## Provider roles (not active-active multicloud)

| Provider | Role | Production dependency |
|----------|------|------------------------|
| **Hetzner Cloud** | Primary compute, private network, PostgreSQL host tier, execution isolation | **Required** |
| **Cloudflare** | DNS, TLS, CDN, DDoS, WAF (plan-limited), R2 off-site backups | **Required** for public edge; backups optional but recommended |
| **Google Cloud** | Optional credit-funded staging, security tests, secondary encrypted backups | **Optional** — must shut down without breaking Hetzner production |

## Verified repository baseline (audit @ branch `cursor/whitepact-enterprise-cloud-v1-f7a9`)

| Component | Location | Notes |
|-----------|----------|--------|
| Application | `src/responsibleai/` | Dashboard, governance, MCP, authority kernel |
| Container | `Dockerfile`, `docker-compose.prod.yml` | PG+Redis internal network; localhost bind |
| Kubernetes | `helm/rai-governance/` | Production values, PDB, non-root, probes |
| Migrations | `migrations/` | Alembic discipline |
| CI | `.github/workflows/ci.yml` | Tests, security scans |
| Prior cloud IaC | None | **New** `infra/terraform/` |

## Trust boundaries (Hetzner)

```
                    Internet
                        │
                        ▼
              ┌─────────────────┐
              │   Cloudflare    │  TLS, WAF, rate limit (plan-dependent)
              │   (proxied)     │
              └────────┬────────┘
                        │ origin only
                        ▼
              ┌─────────────────┐
              │ Hetzner LB      │  SaaS subnet (dashboard :8765, MCP :8766)
              └────────┬────────┘
                        │
     ┌──────────────────┼──────────────────┐
     ▼                  ▼                  ▼
 SaaS replicas    Authority tier      Execution tier
 (policy read)    PostgreSQL          (MCP/upstream egress allowlist)
 no signing       no public IP        no policy/signing keys
```

- **Authority tier** holds PostgreSQL, revocation epochs, audit chains, grant admission (Phase 7A kernel).
- **Execution tier** cannot modify policy, signing material, or audit evidence (firewall + deployment separation).
- **SaaS tier** serves API/dashboard/MCP ingress; connects to DB over private network only.

## Application mapping

| WhitePact chain stage | Hosting |
|----------------------|---------|
| Identity / session / API keys | SaaS tier + `RAI_AUTH_*` |
| Policy / approval / judgment | SaaS + DB on authority tier |
| Short-lived grants / nonce consumption | Authority DB + kernel |
| Isolated execution | Execution tier + `isolation/broker` |
| Evidence / audit | Authority DB; backups to R2 (+ optional GCS) |

## Region selection

Default Terraform `location = fsn1` (Falkenstein). **Singapore (`sin`)** requires owner verification of:

- Hetzner location availability and pricing: https://www.hetzner.com/cloud  
- Data residency / latency requirements  
- Service limits (LB, volumes)

## Deployment artifacts

- Dev: `infra/terraform/environments/development/` — minimum CX22-class nodes  
- Prod: `infra/terraform/environments/production/` — **OWNER_APPROVAL_REQUIRED** before `terraform apply`  
- Edge: `infra/terraform/modules/cloudflare-edge/`  
- Optional GCP: `infra/terraform/modules/gcp-staging-optional/`

## What is not claimed

- No live Hetzner/Cloudflare/GCP resources provisioned in this programme pass.  
- No active-active multicloud HA.  
- Production remains functional if GCP credits expire.
