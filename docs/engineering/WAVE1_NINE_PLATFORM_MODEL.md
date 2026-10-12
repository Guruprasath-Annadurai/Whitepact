# Wave 1 nine-platform architecture and offline qualification model

Status: **DESIGN / PARTIAL OFFLINE VALIDATION — PRODUCTION NO-GO**.
Research date: 2026-10-13. Repository baseline: `f338556baf9984ab485f2d4758179fb87e8baa4d` (preserved draft PR #198).

## Ownership and mutation boundary

Codex owns only this new document on `codex/whitepact-wave1-nine-platform-model`, in `/Users/ag/whitepact-wave1-nine-platform-model`. No existing Terraform, runtime, billing, authentication, revocation, Linux containment, workflow or shared security file is changed. Antigravity retains active P0 ownership. Any runtime or provider-policy fix requires coordination, not a change disguised as infrastructure documentation.

No provider account, resource, token, IAM binding, remote state, DNS record, deployment, package publication or billing-plan change was created or accessed. No `terraform init`, `plan`, `apply`, destroy, cloud CLI login or secret inspection occurred. This document is a proposed allocation of the requested platforms, not proof that the allocation is deployed or fully approved. Nine platforms do not mean nine independently authoritative copies of governance state.

## Proposed responsibility and dataflow matrix

| Platform | Proposed responsibility | Data allowed | Explicitly excluded / release dependency |
| --- | --- | --- | --- |
| Google Cloud | Optional API/control-plane compute, preferably near PostgreSQL; optional encrypted disaster-recovery copy | Authenticated requests and scoped runtime configuration; encrypted backups | Not an authority oracle. Cloud Run lifecycle/background-watch behavior and Linux containment remain unqualified. Existing module is a staging backup bucket, not Cloud Run deployment |
| AWS | Optional independent recovery/export storage and offline compatibility target | Encrypted recovery exports, manifest hashes, minimally scoped object metadata | Not a live second authority database; no S3/Object Lock promise without retention, restore, cost and IAM review |
| Cloudflare | Public static website, ingress TLS/CDN, route protection; optional non-authoritative edge adapter | Public assets; opaque authenticated traffic to approved origin | No edge-minted grants, tenant authority or billing entitlements; no origin bypass on Worker quota exhaustion |
| Oracle | Optional isolated Linux staging/qualification runner or recovery compute | Synthetic test inputs and approved encrypted restore sets | Not automatic production failover; free compute capacity/reclamation is unsuitable as an assumed availability guarantee |
| Neon | Candidate managed PostgreSQL system of record | Tenant-scoped governance, nonce/epoch, approval, outcome/evidence and mirrored billing records under canonical schema | Region, connection pooling, transaction semantics, recovery and residency require real qualification; outage must prevent new consequential admission |
| Upstash | Optional Redis-compatible cache, rate limiter and non-authoritative queue transport | Bounded infrastructure state, opaque IDs; no raw grants/secrets in queue tickets | Queue/lease/cache is never authority. Command/TTL/consistency compatibility and durable reconciliation must be qualified |
| Better Stack | External availability monitoring and operational incident reporting | Health status and sanitized operational aggregates | No tokens, request bodies, canonical evidence payloads or private tenant details; cannot establish execution success from HTTP availability |
| Deno Deploy | Optional public documentation/demo adapter using synthetic or public inputs | Public assets and clearly marked zero-effect examples | Not Python/Linux execution host or a governance mirror; no real consequence fallback when Core is unavailable |
| GitHub | Source review, immutable commit provenance, pinned CI and qualification artifacts | Public source and sanitized test/build evidence | CI success is not production qualification; no credential-bearing PR logs or cloud deployment permission granted by this model |

Minimal recommended path is **client → protected ingress → authenticated Core → canonical PostgreSQL → guarded consequence boundary**, with evidence persisted under the server contract. Redis and monitoring remain side channels. Optional AWS/Oracle recovery must be manual, independently verified and fencing-aware; never run active-active governance databases with divergent epochs/nonces. Deno is not required in the consequence path. Platform count is not a reliability metric.

## Security and failure contracts requiring owner validation

1. **Admission truth:** Only Core's server-derived tenant/principal, authority/consent/policy checks and durable grant/nonce checks can authorize effects. Infrastructure availability, commercial tier, cached ALLOW or an SDK object must not substitute. PostgreSQL unreachable means no new consequential dispatch; an already transmitted effect can remain UNKNOWN and must not be blindly replayed.
2. **Ingress:** Validate Host/Origin and session/CSRF at the canonical backend. Use TLS to origin with certificate validation and independently enforced origin access restrictions. Security-critical Worker routes must be fail-closed, not merely configured with an advisory quota. A Worker outage must not expose a less-protected alternate origin.
3. **Secrets/IAM:** Separate provider credentials by account/environment and exact service. CI pull requests get no production secrets. Prefer reviewed short-lived deployment identity only in a separately authorized release workflow; do not add `id-token: write` here. Runtime database role cannot change infrastructure; infrastructure credentials cannot mint governance authority. Secrets belong in approved runtime secret stores, not browser build variables, Terraform example files, queue tickets, logs or monitoring payloads. Remote Terraform state must be treated as sensitive even when outputs are marked sensitive.
4. **Egress:** Allow only explicitly required provider endpoints from the relevant process. Protected workloads cannot reach metadata services/private destinations merely because another cloud is on the architecture diagram. DNS-pinned transport, redirect policy and containment must remain Antigravity-qualified runtime controls; this model does not independently prove them.
5. **Redis outage/quota:** No infrastructure-error fallback to ALLOW. Rate-limit and queue failure policies must be explicit per route; dangerous admissions stop rather than silently bypass limits. Queue duplicate/loss reconciliation must use canonical durable facts, not Redis as the source of authorization truth. Existing in-flight executions require separately verified continuity semantics.
6. **Observability:** Health/readiness failure is an operational signal, not evidence of effect non-occurrence. Export sanitized IDs/aggregate timings. Monitor database, queue and certificate failure separately; telemetry loss must not produce a fabricated security PASS. Restore exercises must verify tenant boundaries, nonce/epoch continuity and evidence integrity before reopening execution.
7. **Cross-cloud latency:** Measure actual p95/p99 database round trips, cold-start readiness and cancellation propagation. No synchronous authority chain should depend on unnecessary geographically separated services. Budget termination or scale-to-zero must not leave an unattended worker with assumed authority.

## Official current plan facts and caveats

These are public documentation observations, not this account's eligibility, enabled controls, SLA, bill or measured capacity. Recheck before provisioning. Provider plans change and legacy accounts differ.

| Provider | Verified public fact | Planning implication |
| --- | --- | --- |
| Google Cloud | Cloud Run supports **Preview** Cloud Billing spend caps; eligible caps pause Cloud Run workloads. Caps are scoped to eligible service/project; VPC connector VM costs are outside Cloud Run's resource cap | Ordinary budget email alerts are not hard caps. Do not claim the entire account, storage, networking or database costs are capped by a Run budget. [Run billing settings](https://docs.cloud.google.com/run/docs/configuring/billing-settings), [cap scope](https://docs.cloud.google.com/billing/docs/how-to/budgets-spend-caps) |
| AWS | New-account Free Plan credits are time-limited; the Free Plan expires after six months or exhaustion of credits, whichever comes first. Paid plan provides broader access and can incur charges | No perpetual free AWS recovery assumption or credit-funded production SLA. Account eligibility and required service access are unresolved. [Free Tier terms](https://aws.amazon.com/free/terms/), [FAQ](https://aws.amazon.com/free/free-tier-faqs/) |
| Cloudflare | Workers Free: 100,000 requests/day account-wide and 10 ms CPU/invocation. Routes can fail open (bypass Worker) or fail closed (1027) at quota exhaustion | Configure fail closed for security-critical routes and prove origin protection; count other account traffic. [Limits](https://developers.cloudflare.com/workers/platform/limits/), [pricing](https://developers.cloudflare.com/workers/platform/pricing/) |
| Oracle | Always Free compute is home-region constrained and idle compute can be reclaimed | Capacity/continuity are blockers to using it as the assumed production control plane. [Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm) |
| Neon | Current official announcement: Free per-project 1 GB storage, 100 CU-hours/month, six-hour instant restore window | A continuously running 0.25 CU for 720 h uses 180 CU-hours, above 100. Neither sleep nor short restore window is a qualified enterprise recovery policy. Direct pricing-page fetch returned unsupported Markdown content; use announcement and recheck account terms. [Official announcement](https://neon.com/blog/neon-free-plan-1-gb-per-project) |
| Upstash | Pricing card/FAQ: Free 250 MB, 500K commands/month, 10 GB bandwidth. A comparison field says 256 MB, so use conservative 250 MB. PAYG $0.20/100K commands; free allocation is not carried into paid plan. PAYG budget caps rate-limit; fixed-plan auto-upgrade can change charges | No automatic plan upgrade. Count actual commands including replication; paid budget must be deliberately configured and tested. Production SLA/HA features are not inferred from Free. [Pricing and budget semantics](https://upstash.com/pricing/redis) |
| Better Stack | Public uptime page offers 10 monitors, 10 heartbeats and a status page with three-minute checks | Three-minute polling does not meet a seconds-scale revocation SLO; incident/support/logging features require separate plan review. [Uptime](https://betterstack.com/uptime) |
| Deno Deploy | Free: 1M requests/month, 20 GiB egress, 10 h active CPU, 150 GiB-h memory; no reliability SLA. Free overages pause apps; Pro overages bill | Use only optional public surfaces unless separately qualified. Do not confuse Deploy with obsolete Classic or Subhosting limits. [Pricing](https://deno.com/deploy/pricing), [overage behavior](https://docs.deno.com/deploy/changelog/) |
| GitHub | Public repositories using standard GitHub-hosted runners have free Actions usage; larger runners and other billing/storage rules differ | Pin actions, scope artifacts, limit retention, and independently qualify production. Not an unlimited free larger-runner guarantee. [Actions billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions) |

## Workload model — explicit assumptions, not measured capacity

Assume 30 days/month, 20 API requests per active customer per day, all through one edge; eight billed Redis commands/request; average 50 KiB network response; one 2 KiB durable record/request. These are deliberately simple inputs, not performance evidence. Exclude public assets, retry traffic, monitoring, replication, backups, indexes, WAL, logs, external tool payloads and provider-specific billing rounding.

| Active customers | API/day | API/month | Redis commands/month | Raw response transfer/month | Raw new records/month |
| --- | ---: | ---: | ---: | ---: | ---: |
| 100 | 2,000 | 60,000 | 480,000 | 2.86 GiB | 0.114 GiB |
| 1,000 | 20,000 | 600,000 | 4,800,000 | 28.61 GiB | 1.144 GiB |
| 10,000 | 200,000 | 6,000,000 | 48,000,000 | 286.10 GiB | 11.444 GiB |

Derived limits: 100-customer Redis case uses 96% of the 500K free command allowance before excluded traffic; 1,000 customers exceed Redis free commands, Deno free transfer and Neon free storage even before overhead. 10,000 exceed Workers Free daily requests. Deno's optional public surface has its own traffic, so these comparisons are hypothetical only if it carries all modeled API responses; routing through Deno is not recommended merely to consume its free tier.

If deliberately selecting Upstash PAYG, commands alone would cost approximately $0.96 / $9.60 / $96 monthly at these volumes, **not** discounted by the free 500K allowance. Storage, transfer and replication are additional under current terms. For all-platform total use `compute + database + Redis + egress + recovery storage/operations + telemetry + CI/storage + taxes/support`; values for region, runtime utilization, retention, recovery objectives and contract terms remain unknown. **No defensible zero-dollar total or enterprise SLA can be produced from request counts.**

## Existing IaC inventory and actual offline evidence

The baseline has `infra/terraform/modules/cloudflare-edge`, `gcp-staging-optional`, and `whitepact-hetzner-foundation`, plus development/staging/production roots. Hetzner is legacy repository infrastructure, **outside the approved nine-platform proposal**; inventory/static checks do not authorize deploying it. No equivalent complete nine-provider deployment tree was found. The GCP module enables compute/storage/budget APIs and defines a versioned, uniform-access secondary backup bucket with `force_destroy=false`; it is not a Cloud Run compute or configured spend-cap module.

Fresh execution on 2026-10-13, Terraform 1.9.8 darwin_arm64:

| Command / scope | Result | Meaning |
| --- | --- | --- |
| `terraform fmt -check -recursive infra/terraform` | PASS, exit 0 | Formatting only; no writes, provider execution or security proof |
| `terraform validate -no-color`, cloudflare-edge | BLOCKED, exit 1 | Locked `cloudflare/cloudflare 4.52.9` package absent from `.terraform/providers` |
| Same, gcp-staging-optional | BLOCKED, exit 1 | Locked `hashicorp/google 5.45.2` package absent |
| Same, legacy Hetzner module | BLOCKED, exit 1 | Locked `hetznercloud/hcloud 1.69.0` package absent |
| `python -m pytest tests/test_cloud_staging_static.py tests/test_m4_cloud_origin_static.py tests/test_terraform_m4_validate.py::test_cloud_terraform_tree_present -q --no-cov` | **10 passed, 0 failed, 0 skipped**, exit 0, 5.53 s | Source-bound/static checks, not provider validation or live network evidence |

The two existing Terraform tests invoking `init -backend=false` were **not executed**: offline validation deliberately did not fetch providers or create initialization state. Their exclusion is explicit, not counted as passing/skipped. No claim of fresh provider/schema validation, drift detection, IAM enforcement, Terraform plan success or cloud CI success is made. Tooling exists; unavailable cached provider packages are the precise validation dependency. A later authorized validator should use disposable copies, read-only lockfiles and verified provider binaries, `init -backend=false -lockfile=readonly`, then `validate`; still no cloud credentials, remote state, plan/apply or live mutation.

## Recorded deployment hazards and coordination handoff

1. Existing Cloudflare `gate2.tf` auth/signup rules match `/api/(auth|login)` and `/api/(signup|register)`, while actual browser authentication lives under `/api/web/auth/...` (versioned alias also used by clients). Existing webhook rule matches `/api/webhooks/`, not Paddle `/api/billing/paddle/webhook`. General API handling may cover traffic but does not establish intended specialized limits. **Unqualified route-policy coverage:** coordinate an infrastructure-owned contract regression and reviewed route correction; do not claim protection from source presence. This agent did not edit shared security/IaC.
2. Worker fail-closed behavior is a required future deployment assertion, not established by the existing DNS/WAF Terraform. Verify quota exhaustion and direct-origin rejection with independent external tests before opening production.
3. Nine-provider IAM, regions, data residency, transfer tariffs, free-plan eligibility, egress restrictions, restore tests, logs retention, spend caps and consent to paid upgrade are unknown. Owner must explicitly approve these and future mutation authority.
4. Antigravity P0 containment/authority/revocation work remains a dependency for any consequence-producing hosting decision. Cloud Run request-based CPU allocation and Oracle reclamation cannot substitute for its continuous-enforcement proof.
5. Independent qualification must rerun static/provider validation, execute quota/outage/restore tests in an authorized isolated environment, and distinguish its evidence from these source-only results. No production opening, deployment or readiness claim follows from this document.

Acceptance for this workstream: scoped model and offline evidence **complete**; nine-platform deployment/security qualification **PARTIAL / BLOCKED by explicitly listed dependencies**. PR #198 is unchanged. Production remains **NO-GO**.
