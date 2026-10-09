# Phase 10 — Global rollout runbook

**Public launch is not authorized. No DNS change, announcement, or paid signup was made.**

Each stage needs its own owner authorization and one exact SHA. The evidence checker cannot grant that authorization: while artifact verification is unavailable its decision stays `NO-GO`.

## Stage A — Production infrastructure acceptance

- Owner authorization for production spend, separate from the 35.95 EUR/month staging figure.
- Artifact: the production Terraform plan for the named SHA, reviewed, not applied by this branch.
- Scope: zero customers.
- Security: private authority network, admin CIDR, no public database.
- Performance: not applicable until a host exists.
- Monitoring: alert route named by the owner before apply.
- Rollback: do not apply; if applied later, destroy only under a new approval.
- Evidence: `owner.infrastructure` and `cloud.security.live`.

## Stage B — Immutable release deployment

- SHA whose CI is green and whose Antigravity packet matches `git rev-parse HEAD`.
- Image or wheel digest recorded. The git tag `v1.3.1` is not that SHA.
- Scope: operators only.
- Rollback: redeploy the previous digest. Do not edit the running SHA in place.

## Stage C — Private design partner

- Owner names the partner and the tool allowlist in `conditional_scope`.
- One organization. No public signup.
- Security: tenant test from `PHASE_05_STAGING_TEST_HANDOFF.md` repeated for that organization.
- Rollback: revoke the partner's grants and API keys. Keep evidence.

## Stage D — Limited commercial production

- Owner decisions in `PHASE_07_COMMERCIAL_OWNER_DECISIONS.md` are written.
- Payment provider is the one the owner named, in live mode only after a sandbox replay test.
- Scope: the plans the owner listed.
- Rollback: disable new checkout. Do not delete customer evidence.

## Stage E — Wider availability

- Stages A–D accepted.
- `public.launch` evidence points at the owner announcement approval.
- Codex publishes only claims allowed by `PHASE_08_TECHNICAL_PUBLIC_CLAIMS_REGISTER.md`.
- Rollback: the playbook in `PHASE_10_ROLLBACK_AND_INCIDENT_PLAYBOOK.md`.

## Rehearsal performed

Offline only: Terraform validate, the evidence checker `NO-GO`, and the governance unit tests. No simulated cloud account was billed and no rehearsal traffic was sent.

## Gate

NO-GO for every stage that admits a customer or changes DNS.
