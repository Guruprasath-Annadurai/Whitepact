# Phase 3 — Cloud architecture acceptance

**Gate: CONDITIONAL for offline IaC review. BLOCKED for provisioning.**

No `terraform apply` was run. No payable resource was created. No DNS record was changed. No credential was rotated.

## Architecture reviewed

Source of the review is the successor of `0cdef3947503adf7c3f08a5116a4808deda1d3f7`.

| Plane | Intended provider | In this repository |
|-------|-------------------|--------------------|
| Primary compute | Hetzner Cloud | `infra/terraform/modules/whitepact-hetzner-foundation` |
| Edge, TLS, WAF, DNS, R2 | Cloudflare | `infra/terraform/modules/cloudflare-edge` |
| Optional staging / DR | Google Cloud | `infra/terraform/modules/gcp-staging-optional` |

Roots:

- `infra/terraform/environments/development`
- `infra/terraform/environments/staging`
- `infra/terraform/environments/production`

Staging wires a private foundation: NAT gateway, no public IPv4 on the SaaS node, separate server types for SaaS, authority, and execution, admin SSH key looked up by name `whitepact-staging-admin`, and load balancer TCP 443 to origin 443 for Cloudflare Full (strict) plus authenticated origin pull. See `infra/terraform/environments/staging/main.tf`.

## Verification actually run

Terraform v1.9.8.

```bash
terraform -chdir=infra/terraform/environments/development init -backend=false -input=false
terraform -chdir=infra/terraform/environments/development validate
terraform -chdir=infra/terraform/environments/staging init -backend=false -input=false
terraform -chdir=infra/terraform/environments/staging validate
terraform -chdir=infra/terraform/environments/production init -backend=false -input=false
terraform -chdir=infra/terraform/environments/production validate
terraform fmt -check -recursive infra/terraform
```

Result: each `validate` printed `Success! The configuration is valid.` The format check exited 0.

`terraform plan` was not run. There are no Hetzner, Cloudflare, or Google credentials in this session, and a plan that refreshes remote state would be a live read. Plan-only remains an owner-gated step.

## Cost already calculated for staging

From `docs/enterprise/cloud/CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md`. Figures are EUR per month excluding VAT, from that document, not a new quote.

| Resource | EUR/mo ex VAT |
|----------|----------------|
| SaaS CX33 | 8.49 |
| PostgreSQL CX33 | 8.49 |
| Execution CX23 | 5.49 |
| NAT / management CX23 | 5.49 |
| Primary IPv4 | 0.50 |
| Load balancer LB11 | 7.49 |
| **Mandatory subtotal** | **35.95** |

Optional Hetzner backups, a 20 GB volume, Cloudflare Pro, and R2 are extra and are not authorized by validation. VAT is not included. Production cost is not approved by the staging table.

## Risks

- Validation does not prove the Hetzner provider will accept the configuration.
- The staging SSH key `whitepact-staging-admin` must already exist in the project. Creating it is an owner action.
- Optional GCP is not funded by this review.
- Backup encryption and restore have not had a live drill on this candidate.
- A compromised worker must still be unable to reach the authority store except through the private path the module describes. That isolation is not proven until a live staging test.

## Missing before any apply

- Owner Gate 1 phrase and a billing account.
- Hetzner API token stored as a CI secret, not in git.
- Cloudflare API token if the edge module is included in the approved apply.
- Remote state backend and locking. `init -backend=false` does not create one.
- Admin CIDR allowlist values for the operator, supplied as variables, not committed secrets.

## Rollback implication

Because nothing was applied, rollback of this phase is "do not apply". After a future apply, rollback is destroy or a pinned previous SHA only under a separate owner authorization. Do not destroy production to test rollback.

## Gate

CONDITIONAL for the offline validate-and-cost review. BLOCKED for cloud security acceptance, which requires a live environment.
