# First-staging operations: preparation, not provisioned infrastructure

WhitePact — AI Agents. Actions Under Authority.

Independent runtime authorization and enforcement for AI agents.

GLOBAL PRODUCTION NO-GO. M14 owns infrastructure qualification. This runbook
does not authorize an account, paid service, free-trial activation, Terraform
apply, DNS mutation, deployment, directory submission or public endpoint.

## Minimal topology and nine-provider inventory

First staging needs one application host, one authoritative PostgreSQL database,
the Redis dependency required by the chosen supported profile, TLS termination,
private secret injection and observability. Do not make nine providers mandatory
runtime dependencies. Redis, monitoring, edge caches and billing are not authority.

| Provider | Potential responsibility, not deployed | Eligibility/operational gate |
|---|---|---|
| Oracle Cloud | Alternative application host | Account/region capacity and shape quotas; boot/block volume, public IP and egress billing; no capacity promise |
| Neon | Alternative managed authoritative PostgreSQL | Verify connection, storage, compute-hour and restore retention limits for the actual account; pooled migration support and cold-start qualification |
| Cloudflare | DNS/TLS/edge after owner approval | No production zone edits; verify routes, Host/Origin, TLS, cache bypass for authenticated/API responses and rate-limit behavior |
| Google Cloud | Alternative compute / object-storage role | Confirm project budgets, region/service quotas, logging and egress charges; free credits are not perpetual zero-cost proof |
| AWS | Alternative compute/storage/witness role | Verify actual service eligibility, request/storage/egress charges and IAM; no auto-scaling spend or unapproved bucket creation |
| Upstash | Optional managed Redis role | Verify authentication/TLS, command limits, data retention, availability and overage; never authoritative permissions or durable execution truth |
| Deno Deploy | Optional supported stateless edge/client role | Do not assume Python runtime compatibility; contract/region/limit review required before assigning application hosting |
| Better Stack | Optional monitoring/incident delivery | Verify probe/log retention and ingestion limits, redaction and contact ownership; no SLA claim |
| GitHub | Source/review/CI/provenance | Pin actions, read-only tokens, isolate test secrets, budget minutes/storage and artifact retention; no package publication |

All nine zero-cost eligibility statuses are **NOT VERIFIED** for owner accounts.
No dollar estimate is presented as a current provider quote. Proposed first
staging capacity is deliberately a measurement exercise: one bounded application
instance, PostgreSQL connection pool, declared concurrency cap, storage/retention
budget and observed request/egress volume. Record actual measured demand before
selecting paid capacity. Establish hard budget alerts/approval, verify current
provider terms in the actual account, and stop if a service cannot guarantee the
approved spend boundary. Do not enter payment details or activate trials here.

## Private configuration and recovery

Inventory names only: WHITEPACT_ENV, WHITEPACT_DATABASE_URL,
WHITEPACT_REDIS_URL, WHITEPACT_API_KEYS, WHITEPACT_FIELD_ENCRYPTION_KEY,
WHITEPACT_WEB_PUBLIC_URL, WHITEPACT_ALLOWED_ORIGINS,
WHITEPACT_WEB_SESSION_SECURE, WHITEPACT_AUTH_ENABLED,
PHASE7A_DISPATCHER_ENABLED. Verify names against the selected runtime settings;
provider/account/contract-specific additions require owner review. Never paste
values into source, tickets, shell history or screenshots. No browser-side
server credentials. Production configuration is not established by this list.

- DB outage: reject new consequential requests; preserve UNKNOWN/existing
  evidence. Restore connectivity and inspect durable state before any action.
  Never retry external effects because a response was lost.
- Redis outage: report service availability accurately; do not manufacture
  authority or replace PostgreSQL truth with local memory.
- Session/identity provider failure: distinguish unavailable from signed out;
  safe GET retries only. Never grant access based on cached membership.
- Restore: validate encrypted backup access, schema head, tenant binding and
  evidence continuity in an isolated destination before a reviewed cutover.
  Local fixture restoration is not managed-provider disaster-recovery proof.
- Edge failure: require reviewed DNS/TLS/rollback ownership. No edits authorized
  by this runbook. Authenticated responses must not enter a public cache.
- Logging: collect status/latency/correlation IDs only where permitted; redact
  tokens, cookies, raw arguments and personal/billing data. Alert on error rate,
  queue age, DB pool exhaustion, uncertain outcomes and evidence-write failure.

External account quotas, price eligibility, live IAM, TLS, alerts, failover,
backup restoration and production performance remain UNQUALIFIED.
