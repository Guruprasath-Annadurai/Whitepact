# WhitePact Cloud — Private Staging Plan (owner approval only)

**Status:** PLAN ONLY — no resources provisioned by this document or PR #128.

## 1. Hetzner resources (production-shaped, disposable)

From `infra/terraform/environments/production/terraform.tfvars.example` and `docs/infrastructure/CLOUD_COST_AND_CREDITS.md`:

| Resource | Qty | Type (example) | Indicative €/mo |
|----------|-----|----------------|-----------------|
| SaaS nodes | 2 | cx32 | ~€15–20 each |
| Authority node | 1 | cx32 | ~€15–20 |
| Execution nodes | 2 | cx22 | ~€6–8 each |
| Load balancer | 1 | LB11 | ~€5.39 |
| Private network | 1 | — | €0 |

**Indicative recurring (ex-egress):** **€60–90/mo** compute + LB; re-verify on [Hetzner Cloud pricing](https://www.hetzner.com/cloud).

**Development minimum** (single CX22): **€15–25/mo** for IaC smoke only.

## 2. Cloudflare (required for Access JWT path)

| Service | Purpose | Permission / note |
|---------|---------|-------------------|
| DNS zone | Public names (staging subdomains) | Zone DNS edit (scoped API token) |
| Cloudflare Access | Employee JWT (`access_gateway.py`) | Application + policy admin; JWKS URL wired in config |
| Tunnel (optional) | Origin without public SaaS IP | Tunnel create + route |
| R2 (optional) | Encrypted backup target | Bucket scoped token; separate from app admin |

**Paid risk:** Access seats / Business features — confirm plan before enable. **No production DNS cutover** in staging.

## 3. Credential provisioning (safe procedure)

1. Owner creates **disposable** Hetzner project + API token (read/write server, read network).
2. Owner creates **scoped** Cloudflare API token (DNS + Access only; no account-wide).
3. Store in GitHub **environment secrets** for a `staging` environment — never commit.
4. Terraform: `terraform plan` only in CI; **`terraform apply` only after explicit owner approval** on a labeled staging window.
5. Application secrets (grant signing keys, DB): generated in staging vault; **no reuse of production material**.
6. **Teardown:** `terraform destroy` with same tfvars + delete CF Access apps + revoke tokens (see §6).

## 4. Security test matrix (real staging)

| Area | Test | Pass criterion |
|------|------|----------------|
| Grants | Issue → verify → single consume | Second consume fails; revoked grant fails |
| Concurrency | Issue vs `terminate_local_access` | No grant after termination |
| JWT | Live Access JWKS | Invalid alg/issuer/aud rejected |
| Offboarding | Employee terminate | Local fail-closed; external steps logged UNRESOLVED until confirmed |
| Network | nftables cloud-init | Execution egress deny-by-default; only allowlisted CIDRs |
| Terraform | `validate-terraform.sh` | Clean validate on staging tfvars |
| Executor | `PRIVILEGED_EXECUTOR_ENABLED` | Remains false until boundary wired |

Automated slice: `pytest tests/whitepact_cloud tests/infrastructure/`.

## 5. Firewall and recovery verification

- Confirm **LB → SaaS** only on 443; authority on private IP.
- SSH/admin only from `admin_cidr_allowlist`.
- Snapshot or volume backup **one** recovery drill; document RTO in runbook (`10_DISASTER_RECOVERY.md`).
- Restore test on **disposable** volume, then destroy.

## 6. Automatic removal of disposable resources

| Step | Action |
|------|--------|
| 1 | Label all staging resources `environment=staging-disposable` |
| 2 | Calendar teardown date (max 14 days default) |
| 3 | `terraform destroy -auto-approve` only after owner sign-off on destroy ticket |
| 4 | Revoke Hetzner + Cloudflare tokens |
| 5 | Delete R2 staging bucket contents |
| 6 | Archive evidence (CI URLs, test logs) to internal store — not public repo |

## 7. Itemized budget summary (owner approval)

| Line | Monthly (indicative) |
|------|---------------------|
| Hetzner staging (minimal) | €15–25 |
| Hetzner staging (prod-shaped) | €60–90 |
| Cloudflare plan uplift | $0–$200+ (plan dependent) |
| R2 storage/ops | usage-based |
| Engineer time (apply/monitor/teardown) | out of band |

**Total recurring envelope (prod-shaped + CF Pro):** plan **€80–120/mo** EU compute/LB plus Cloudflare — align with `12_COST_AND_OPERATIONS.md`.

**Gate:** **OWNER_APPROVAL_REQUIRED** before any `terraform apply`, paid CF upgrade, or DNS record pointing to live staging.
