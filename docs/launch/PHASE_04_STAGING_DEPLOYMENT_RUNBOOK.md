# Phase 4 — Staging deployment runbook

**Gate: BLOCKED for deployment. The steps below stop before provisioning.**

Staging is not deployed. This runbook is the offline procedure an operator may execute only after the owner approval in `PHASE_03_INFRASTRUCTURE_OWNER_APPROVAL.md`.

## Provenance

1. Check out the exact SHA the owner named. Do not deploy a branch name.
2. Record `git rev-parse HEAD` and `git rev-parse HEAD^{tree}`.
3. Confirm GitHub Actions is green on that SHA, including Python 3.11 and 3.12.
4. Confirm Antigravity has a written result for that same SHA. A Cursor log is not that result.

`0cdef3947503adf7c3f08a5116a4808deda1d3f7` is CI-green and still contains WP-LAUNCH-P1-MEMORY-SCOPE-01. Do not stage that SHA. Stage the successor only after its own CI and independent retest.

## Preflight

```bash
terraform version
terraform -chdir=infra/terraform/environments/staging init -backend=false -input=false
terraform -chdir=infra/terraform/environments/staging validate
terraform fmt -check -recursive infra/terraform
python scripts/check_pinned_actions.py
python scripts/release_evidence_check.py docs/launch/evidence/rc-0cdef394.json
```

`release_evidence_check.py` must print `NO-GO` until live evidence exists. A NO-GO here means "do not call the environment launched". It does not forbid a later owner-authorized plan.

## Plan

Only after the owner supplies credentials out of band:

```bash
terraform -chdir=infra/terraform/environments/staging plan -out=staging.plan
```

Read the plan. Expected shape, subject to variables: NAT gateway, private SaaS node, authority node, execution node, PostgreSQL node, load balancer TCP 443, firewalls, and the existing SSH key `whitepact-staging-admin`. Refuse the plan if it adds public IPv4 on the SaaS node, opens execution egress beyond the approved CIDRs, or includes production.

Do not run `terraform apply` from this document.

## After a future authorized apply

These checks are the operator's job. They are not done.

1. Authority service health responds only on the private path.
2. Execution worker cannot open a direct connection to the authority database.
3. Migrations apply forward once and refuse a second divergent head.
4. A consequential tool call without a fresh grant is denied.
5. Backup job writes an encrypted object and a restore to a scratch database matches the source digest.
6. Rollback is redeploy of the previous pinned SHA, or destroy of staging only, under a new owner approval.

The manual workflow `.github/workflows/deploy-staging-manual.yml` checks the gate phrase and runs validate. It does not SSH, build an image, or apply.

## Gate

BLOCKED. No staging environment exists from this work.
