# Phase 3/4 cloud execution readiness

**Staging provisioning: NO-GO.** No resource was created. `terraform apply` was not run. `terraform plan` was not run. DNS was not changed.

Reviewed tree: `6801d4ad0047d15a196ab9caeffacf54f9ce557e` (`4068d443c481327c15a14ab281f6cc28122444fc`), plus the local preflight notes in this file. A later commit that only documents this preflight is not a new cloud apply.

## Inventory the staging root would create

`infra/terraform/environments/staging` uses only the Hetzner foundation module. Defaults: location `fsn1`, SaaS `cx33`, authority `cx33`, execution `cx23`, NAT `cx23`. `saas_public_ipv4` is false.

| Resource | Count | Network |
|----------|-------|---------|
| Private network and four subnets (SaaS, authority, execution, management) | 1 network | Private |
| NAT gateway server | 1 | Public IPv4, SSH from admin CIDR or `127.0.0.1/32` if unset |
| SaaS server | 1 | No public IPv4 |
| Authority server (role `postgres-governance`) | 1 | No public IPv4 |
| Execution server | 1 | No public IPv4 |
| Load balancer `lb11`, private target, TCP 443 to origin 443 | 1 | Public listener, private origin |
| NAT firewall | 1 | SSH only |
| SaaS public firewall | 0 | Disabled because SaaS has no public IPv4 |

There is no fifth PostgreSQL server. The cost row labeled PostgreSQL CX33 is this authority server.

Cloudflare edge and R2 resources are not in the staging root. R2 is an egress comment and `scripts/cloud/gate2/enforce_r2_retention.sh`, not a bucket this root creates. Google Cloud is `infra/terraform/modules/gcp-staging-optional` and is not wired into staging. It stays unauthorized.

## Commands run

Terraform v1.9.8, `init -backend=false -input=false`, then `validate`, for development, staging, and production. Each printed `Success! The configuration is valid.` `terraform fmt -check -recursive infra/terraform` exited 0.

No Hetzner, Cloudflare, or Google credential was used. A plan would refresh live state and was not run.

## Local image smoke, not a staging deploy

`docker build -t whitepact-phase3-smoke:local .` completed on this workstation. Image `1f9d9e7a62f9`. `docker run --rm --entrypoint id` printed `uid=1001(appuser)`. The same image has no `/var/run/docker.sock` and `os.geteuid()` is not 0. This does not deploy the image, open a port, or prove worker-to-authority isolation on Hetzner.

## Isolation as written, not as proven live

- Authority and execution servers have `ipv4_enabled = false`.
- Execution input allows SSH only from the management path described in the nftables template.
- Authority egress is limited to the CIDR variable. That variable is required and is not committed.
- SaaS, authority, and execution are separate servers and subnets.
- This is configuration review. It is not a live connection test.

## IAM, secrets, monitoring, budget

- SSH key name `whitepact-staging-admin` must already exist. The configuration looks it up. It does not create a cloud IAM user.
- Tokens stay outside git. This session did not load them.
- No budget or alert resource is in the staging root. That is an owner gap before apply.
- Backup encryption and a restore drill are not done.

## Monthly cost if the owner later approves this inventory

EUR per month, excluding VAT, from `docs/enterprise/cloud/CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md`. Not a new vendor quote.

| Resource | EUR/mo ex VAT |
|----------|----------------|
| SaaS CX33 | 8.49 |
| Authority CX33 (governance database role) | 8.49 |
| Execution CX23 | 5.49 |
| NAT CX23 | 5.49 |
| Primary IPv4 | 0.50 |
| Load balancer LB11 | 7.49 |
| **Staging Hetzner subtotal** | **35.95** |

Cloudflare, R2, GCP, VAT, and backups are extra and are not approved.

## Owner approvals still required

1. Gate 1 phrase and a billing account before any apply.
2. Hetzner token in a secret store, not in the repository.
3. Admin CIDR values supplied as variables.
4. A decision that Cloudflare and GCP stay out of the first apply.
5. Antigravity review of `6801d4ad` itself. The Phase 2 pass on `996795a` is not that review.
