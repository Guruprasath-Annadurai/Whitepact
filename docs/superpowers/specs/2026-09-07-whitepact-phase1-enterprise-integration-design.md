# WhitePact Phase 1 canonical enterprise integration

Status: implementation design; no enterprise production claim.

## Baseline and authority

Start at `6f030a3e0bcece0e68f9ec5f18c9b28a2a42904d` on
`integration/enterprise-phase1`. Preserve website routes, key rotation, Stripe
ledger, email adapter and OAuth from PR85. PR85 is already contained. Extract
individual invariants from PR55 `22b2c77543551057031e73e986c332c19243c57e`;
never merge it or independently apply PR50/54. Select supply-chain improvements
from PR79 and verification from PR84. PR51 supplies comparison evidence only.
No push, merge, database reset, revision stamping or customer-data deletion.

## Storage contract

Preserve migrations 0001–0032 byte-for-byte. Add 0033 crypto, 0034 legacy
consent/vault storage compatibility, 0035 root authority/consent, 0036 evidence
chain uniqueness, 0037 structured consent scope, 0038 revocation epochs, 0039
execution nonces and 0040 approval purpose. The legacy vault tables preserve the
explicit migration intent only: do not import neural runtime, adapters, devices,
attestation, decoders or BCI functionality. Further additive billing/deployment
schema must follow 0040 with unique revisions, never repurpose historical IDs.

Every new security record has an explicit tenant relationship. Root records and
consent require an organization; consent references its root within that same
organization. Missing action/target scope means no permission. Existing proof
scope is backfilled with empty arrays, never wildcards. Evidence uniqueness
preflight rejects null-tenant, orphaned, forked or duplicate history without
repairing/deleting evidence. Metadata and Alembic must agree.

Accepted upgrade paths: empty database, canonical 0029 and website 0032. A
database carrying legacy PR55 revision numbers cannot be assumed canonical based
on version strings. Inspect schema signatures before migration; reject mismatches
with a recovery explanation. No deployed PR55 database has been demonstrated.
A legacy bridge requires an inventoried real schema and explicit data-preserving
transformation; an unverified stamp is prohibited. Reject unversioned nonempty
databases rather than infer an arbitrary baseline.

## Canonical runtime contract

`GovernanceContext` normalizes trusted organization, authenticated subject,
membership, action, target, purpose, authority/consent references and evidence
trace. Transport input never overrides the authenticated tenant. Authentication,
membership, legitimacy and runtime authority remain distinct. Retain the existing
`GovernanceDecision` enum and `DecisionResult` contract; enrich the latter rather
than introduce a second incompatible decision type.

Use PR55 root/consent persistence and Heart primitives, but reject its permissive
fallbacks: missing consent cannot silently fall back to self-root authority;
empty targets cannot match arbitrary targets; absent purpose cannot bypass a
purpose-bound grant. Do not create a real-world authority root from a successful
login. Explicit customer-owned authority records remain prerequisites; provisioning
a new trust bootstrap or Principal Directory is outside Phase 1.

The existing gateway continues policy/risk evaluation. Bind execution permits to
decision ID, tenant, principal, digest of exact executed arguments, resolved
target fingerprint, purpose, policy/authority versions, consent, revocation epoch,
expiry and nonce. Persist pre-execution evidence before consuming/executing.
Re-read legitimacy, consent, authority, revocation and relevant policy on approval
resume and immediately before permit consumption. A DB unique nonce key enforces
one successful consumption across replicas. External side effects are not
advertised as exactly once. Record started/succeeded/failed/unknown distinctly;
timeouts/cancellation after dispatch can be unknown.

All consequential execution uses one guarded chokepoint. Internal tool and
upstream executors may differ only in target mechanics. Private Python functions
remain callable by an attacker controlling the process: Phase 2 isolation is
required, and Phase 1 must document this limit. REST, MCP, hosted MCP, dashboard
and existing worker paths normalize through the same context. Metadata listing
does not authorize calls. Keep OAuth PKCE, token replay defense, scope checks and
tenant/subject revalidation. Retain outbound URL/DNS checks and disable redirects.

## Evidence

Per-tenant chains use database uniqueness plus bounded retries, not a process
mutex alone. Chain serialization includes all reconstructive decision, authority,
consent, policy, execution and build/deployment references. Store fingerprints
and identifiers, not credential bytes. Reject pre-execution persistence failures.
Retain honest unknown outcomes and future external-anchor interfaces without
claiming immutable storage that has not been deployed.

## Deployment and authenticity

Modes: COMMUNITY_DEV, OFFICIAL_SELF_HOSTED, ENTERPRISE_PRIVATE, WHITEPACT_CLOUD.
Community works without activation and makes no official-authenticity claim.
Production requires PostgreSQL; Redis failure never broadens authorization.
Explicit migration jobs precede HA rollout. Preserve pinned minimal non-root
Docker, readonly runtime where practical, health/readiness, PDB, graceful rollout,
minimal service accounts, network policy and TLS ingress.

Deployment credentials are signed, expiring documents binding deployment public
key, organization, mode and environment to issuer/KID. Customer private key stays
local. Runtime trusts public verification keys only. Trust-service signing is a
separate explicitly configured issuer boundary. Account activation credentials
are not deployment identity. Support local verification and export/import for
air-gapped activation. Expired commercial credentials restrict managed services
without disabling protection. Software authenticity, deployment authenticity and
customer authority are separate roots. No vendor super-admin and no per-action
WhitePact Cloud dependency. Offline revocation freshness is bounded honestly.

## Commercial boundary

Introduce BillingProvider around existing Stripe operations and canonical
provider-scoped subscription/event state. Keep verified signatures and durable
idempotency; failed-event retries must acquire ownership atomically. Entitlements
represent commercial capabilities, never permission to execute. Missing payment,
expiry or downgrade must not turn DENY into ALLOW or remove enforcement. Paddle
remains an interface extension, not an implementation requirement.

## Release, documentation and acceptance

Keep main's reusable builder, signed-tag intent, exact-byte publish, SBOM,
attestation and reproducibility. Add compatible PR79 locks/CodeQL/policy checks
with immutable action pins and least privilege. Preserve Python 3.11/3.12,
frontend, accessibility, DCO, Gitleaks, dependency review, Helm and security gates.
Update public claims from actual evidence, not internal scores or PR prose.

Each checkpoint needs focused tests and diff review before the next dependent
checkpoint. Final verification covers real PostgreSQL upgrades/concurrency,
adversarial tenant/auth/execution/evidence cases, browser accessibility, Docker,
Helm, audits and release-control regressions. GitHub-only checks and external
activation/release signatures stay unverified until actually executed. Freeze a
local DCO candidate only when required gates pass. No Phase 2, SCIM, FDE,
Principal Directory, BCI, Network Fabric or certification implementation.

## Design self-review

Reviewed against all twelve directive sections. No unresolved placeholder is
treated as implementation permission. Material reconciliation decisions: preserve
website migration identity; deny ambiguous legacy schema; reject PR55 authority
fallbacks; preserve existing decision API; separate billing from security; keep
issuer secrets out of runtime; defer process isolation. Legacy customer migration
cannot be called verified without actual schema evidence.
