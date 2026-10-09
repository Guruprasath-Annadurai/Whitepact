# Provider eligibility checklist

Retrieved 2026-10-09 from the provider pages cited in each section. Free-tier
terms change. Re-read the cited page against the actual account before any
future authorization. Do not treat this checklist as a completed signup.

Eligibility for this program means: the candidate fits the published $0
allowance **and** the account cannot silently graduate into paid billing.
A resource that is merely "free if you stay inside a credit" is a temporary
alternative, not the persistent candidate.

## Decision

| Provider | Role in this design | Eligible now? | Why |
|---|---|---|---|
| GitHub Actions, standard runners | CI and security tests | Yes, for this public repo | No persistent infrastructure. Public repositories are not billed for standard GitHub-hosted minutes |
| Oracle Cloud Always Free Ampere A1 | Candidate persistent dev VM | Conditional | 2 OCPU / 12 GB fits the 4 GB floor. Capacity, home region, card-on-file, and idle reclamation are unchecked |
| Google Cloud Free Trial | Temporary staging only | Not as a $0 persistent host | Always Free `e2-micro` is 1 GB RAM, below the floor. Trial credit is time-boxed |
| Existing AWS credits | Temporary alternative only | Unknown | Credit balance, expiry, and plan type are not in this repository |
| Neon Free | Disposable Postgres tests | Only for synthetic schema tests | Managed multi-tenant database. Does not meet enterprise isolation |
| Cloudflare Free | Edge and object tests | Only off production DNS | Workers cannot host WhitePact. R2 is not an evidence store |

## 1. GitHub Actions

- [x] Repository visibility is public (`Guruprasath-Annadurai/Whitepact`).
- [x] Current workflows use `ubuntu-latest` only. No larger runners, no self-hosted runners, no macOS-only jobs added by this package.
- [ ] Confirm in GitHub billing that Actions spending limit remains $0 and that no larger runner has been enabled.
- [ ] Do not upload customer evidence, API keys, or production database dumps as artifacts.

Standard public-repo runners cover lint, unit tests, the Postgres 16 service container, wheel smoke, CodeQL, gitleaks, dependency review, Scorecard, and Helm lint. Container-isolation tests run when the runner's Docker daemon is available; they are not a substitute for a dedicated isolation host, because the runner is shared with the job.

## 2. Oracle Cloud Always Free

Source: [Always Free Resources](https://docs.oracle.com/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) and the [Free Tier overview](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier.htm), plus Oracle's free-tier page for the separate $300 / 30-day trial.

- [ ] Account exists and the operator can open Limits, Quotas and Usage.
- [ ] Home region is recorded. Always Free compute, block volume, and the quota in this module are valid only in that region. South Korea North (Chuncheon) cannot host Always Free A1.
- [ ] Ampere capacity is actually available in that home region. "Out of host capacity" is not permission to pick a paid shape or another region.
- [ ] No existing A1 instances already consume the 2 OCPU / 12 GB allowance.
- [ ] Block storage in use, including boot volumes of deleted-but-not-purged instances, is low enough that 50 GB boot + 50 GB data stays inside 200 GB.
- [ ] Volume backup count is under the five-backup cap after this candidate's backups, or backups are not enabled.
- [ ] The image OCID is marked Always Free Eligible, Ubuntu, and aarch64. Any other image can bill.
- [ ] The account is not upgraded to Pay As You Go as part of this work. Upgrade is an explicit billing change.
- [ ] If the tenancy is still inside the $300 / 30-day trial, the candidate stays at 2 OCPU and 12 GB. Oracle disables and then deletes A1 instances that exceed the Always Free total 30 days after trial end unless the account is upgraded.
- [ ] A credit card on file, which `DEPLOY_RUNBOOK.md` already records as an OCI signup requirement, is acknowledged as a charge path. The quota and the shape allowlist do not cover console actions outside this module.
- [ ] Idle-reclamation rule is accepted: Oracle may reclaim an Always Free instance when, for 7 days, CPU p95 is under 20%, network utilization is under 20%, and (for A1) memory utilization is under 20%. This design does not add a fake workload to avoid that rule.

Rejected OCI "free" options:

- `VM.Standard.E2.1.Micro`: 1/8 OCPU and 1 GB RAM. Below the 4 GB floor, and each instance still consumes a boot volume of at least 47 GB.
- Autonomous AI Database and MySQL HeatWave: not PostgreSQL. Alembic and asyncpg do not target them.
- Flexible load balancer and network load balancer: not required, and a shape above the 10 Mbps Always Free profile can bill. Omitted from Terraform.
- NAT gateway: paid. Omitted. See the architecture note on the public subnet.

## 3. Google Cloud

Sources: [Free Cloud features](https://docs.cloud.google.com/free/docs/free-cloud-features), [Free Trial terms](https://cloud.google.com/terms/free-trial) (last modified date shown on that page includes 12 February 2026).

- [ ] Billing account type is recorded as Free Trial or Paid. This repository does not prove which one exists. `DEPLOY_RUNBOOK.md` records a failed UPI billing setup. `docs/integrations/FOUNDER_ACTIONS.md` records a Gemini billing link on project `gen-lang-client-0113985869`. Treat any Paid billing account as billable.
- [ ] Free Trial, if unused and still available, is $300 for 90 days and, per Google, does not bill until someone upgrades to a paid account. Confirm that sentence against the current FAQ before relying on it.
- [ ] Do not upgrade the billing account. Upgrade is what starts charges beyond remaining credit.
- [ ] Always Free Compute Engine is one non-preemptible `e2-micro` in `us-west1`, `us-central1`, or `us-east1`, plus 30 GB-months of standard disk and 1 GB of North America egress (China and Australia excluded). One gigabyte of RAM does not run Postgres, Redis, dashboard, MCP, and a 512 MB sandbox.
- [ ] A larger trial VM spends the $300 credit. It is temporary staging only, with a shutdown date before day 90 and before the credit balance hits zero.
- [ ] GPUs, Cloud SQL, and any non-Always-Free disk class are out of scope. Cloud SQL's separate trial is not this design.
- [ ] Budget alerts may be created later. They notify. They do not stop spend unless a separate automated billing disable exists, and even that disable is not instantaneous.

## 4. AWS credits

Sources: [AWS Free Tier](https://aws.amazon.com/free/) and the [15 July 2025 Free Tier update](https://aws.amazon.com/blogs/aws/aws-free-tier-update-new-customers-can-get-started-and-explore-aws-with-up-to-200-in-credits/).

- [ ] Account creation date is recorded. Accounts created before 15 July 2025 stay on the legacy Free Tier. Newer accounts are on the credit-based Free plan or a Paid plan.
- [ ] Remaining credit balance and expiry are read from Billing and Cost Management. This repository does not contain that balance. Do not assume $200; that figure is the new-account maximum, not a measurement of this account.
- [ ] Plan type is recorded. On a Paid plan, usage past credits bills the payment method. On the new Free plan, Google-style "no charge until upgrade" language applies only while the account stays on that plan; joining an Organization or Control Tower can expire credits and upgrade the account.
- [ ] No NAT gateway, no Application or Network Load Balancer, no unattached Elastic IP, no RDS instance left allocated, no Marketplace AMI.
- [ ] Public IPv4 addresses are a charge class on AWS. Confirm the current rate before allocating one.
- [ ] Stopping an EC2 or RDS instance does not delete EBS or RDS storage. Cleanup means delete, not stop.
- [ ] `t3.micro` / `t4g.micro` class Always Free or credit-covered shapes are 1 GB RAM. They fail the same floor as `e2-micro`. A larger instance spends credits and is temporary only.

## 5. Neon Free

Source: [Neon plans](https://neon.com/docs/introduction/plans), retrieved 2026-10-09.

- [ ] Plan is Free, with no payment method and no upgrade to Launch or Scale.
- [ ] One project, synthetic data only, 1 GB storage cap understood. Account-wide cap is 20 GB across projects.
- [ ] 100 CU-hours per project per month understood. Compute suspends after 5 minutes and that suspend cannot be disabled on Free. A connection held open by CI will burn the quota; GitHub Actions must keep using its own Postgres service container.
- [ ] Public network transfer cap is 5 GB per project per month. Exceeding CU-hours or transfer suspends compute until the next period. Exceeding storage blocks writes that grow storage. Those are product limits, not evidence of tenant isolation.
- [ ] Not used for customer evidence, field-encryption keys, or production mode.

## 6. Cloudflare Free

Sources: [Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) and [Workers limits](https://developers.cloudflare.com/workers/platform/limits/).

- [ ] Account has no payment method, or the operator accepts that a payment method turns R2/Workers overage into a bill.
- [ ] Workers Free stays inside 100,000 requests/day and 10 ms CPU. That cannot run WhitePact.
- [ ] R2 Free stays inside 10 GB-month, 1 million Class A operations, and 10 million Class B operations. Egress fees are not the risk; a paid plan or an attached payment method is.
- [ ] No DNS record is created or edited on the production zone. A Tunnel hostname is a DNS change and stays unauthorized.
- [ ] No Worker implements ALLOW / DENY / REQUIRE_APPROVAL. Edge filtering is not the governance decision.

## 7. Local machine

- [x] `docker compose` (SQLite dashboard) and `docker compose -f docker-compose.prod.yml` (Postgres + Redis) already exist.
- [ ] Host has Docker, 4 GB RAM free, and no production `.env` loaded.
- [ ] Container isolation tests are the local or VM place to prove `--network=none`, not a free SaaS runtime.
