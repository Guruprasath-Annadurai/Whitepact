# Phase 3 — Infrastructure owner approval

**Status: OWNER DECISION REQUIRED. Not approved by this engineering pass.**

## Decision requested

Approve or refuse staging provisioning for the Hetzner layout in `infra/terraform/environments/staging`, capped to the mandatory resources in `docs/enterprise/cloud/CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md`.

Mandatory staging subtotal recorded there: **35.95 EUR/month excluding VAT**.

## Explicit non-approvals

Engineering does not approve:

- `terraform apply`
- Production provisioning
- Cloudflare plan upgrades
- Google Cloud staging or disaster-recovery spend
- DNS cutover
- Secret rotation
- Public launch

## If the owner approves staging

The existing workflow `.github/workflows/deploy-staging-manual.yml` requires `workflow_dispatch` input `confirm_gate1` to equal `APPROVE_STAGING_CLOUD_PROVISIONING`. Its deploy job currently validates Terraform and does not apply. Extending it to apply is a separate change after this approval, not part of this branch's authority.

Required with the approval:

- Exact git SHA allowed to be planned
- Hetzner project and token location
- Admin CIDR
- Confirmation that 35.95 EUR/month ex VAT plus tax is acceptable
- Whether optional server backups (5.592 EUR/month ex VAT, 20% of the four server SKUs) are in or out. They are outside the 35.95 ceiling.
- Statement that production remains unapproved

## If the owner refuses

Leave the roots unapplied. The validate result in `PHASE_03_CLOUD_ARCHITECTURE_ACCEPTANCE.md` still stands as an offline check.

## Gate

BLOCKED until the owner records the decision above.
