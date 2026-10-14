# Invite-only enterprise evaluation: controlled plan, not activation evidence

Status: **PREPARATION ONLY; GLOBAL PRODUCTION NO-GO**. Prepared from
`01cc0d9b815d7ce27f41cc42fb4853b845003d75`. No invitation, organization, account,
public registration deployment, provider resource or paid plan was activated by
this work. A planning document does not enforce application quotas.

## Envelope and ownership

The owner-approved envelope is **at most three organizations, at most three
evaluators per organization, fourteen calendar days**. Count the owner/member
who performs evaluation as an evaluator; there is no implied extra free slot.
For each actual organization, record the owner-approved UTC start and end
(`end = start + fourteen calendar days`), evaluator count and consent separately
in the private evaluation register. Do not store evaluator email addresses,
credentials or tenant payloads in this public repository. An extension, fourth
organization or fourth evaluator needs new owner authorization, not a UI trick.

These limits are operational admission conditions, **not newly implemented
server entitlements, runtime authority or a promise that public signup is
disabled**. Release owner must verify actual invite-only deployment controls
before any real external evaluation. No invites/deployment are authorized here.

Codex owns the new local benchmark, its safety/calculation tests and these
materials only. Antigravity owns core P0 authority/revocation/containment work.
Do not change shared authentication, billing, runtime, security or IaC to make
the evaluation appear ready. SDK/framework/CI/frontend owners retain their
exclusive surfaces.

## Supported journey and evidence gates

| Stage | Existing surface / evidence | Acceptance condition | Current limitation |
| --- | --- | --- | --- |
| Account | `/api/v1/web/auth/register`, verify and login (versioned web aliases) | Real delivery, verified user, authenticated session, correct CSRF | Test development verification tokens are not real email delivery proof |
| Organization | `/api/v1/web/onboarding`, session organization context | Organization comes from authenticated server session; plan preference is not entitlement | Internal fixture organization creation is not customer onboarding proof |
| Membership | `/api/v1/web/invitations`, accept, members; role changes/removal | Distinct authorized users, pending invitations, revoked invitation cannot be reused; at most three evaluation participants | Human private register and deployment admission controls need owner verification; this document does not add a server cap |
| API key | Existing create/rotate/revoke console | One-time secret handling, least privilege, no redisplay or logging; revoked key rejected | API key and organizational role are identity/scope, not runtime authority |
| Governed request | `/api/v1/governance/tools/call` | Missing authority denies; client cannot create root/consent/grant; uncertainty never becomes success | Successful external execution requires the canonical authority provisioning gate below |
| Approval | Existing pending/resolve/execute and web quorum routes | Separate approvers, fresh checks at resume, zero dispatch after revocation, replay rejected | In-memory or directly seeded test authority is not hosted customer authorization |
| Evidence | Tenant-scoped list and attestation, existing web detail surface | Correct tenant, no cross-tenant disclosure, UNKNOWN visible, no blind mutation replay | Attestation must not be advertised as an unsupported signature or standalone bearer detail API |
| Billing | Paddle-first existing browser server-plan checkout/portal | Verified webhook governs commercial entitlement; no arbitrary client org/customer/price authority | Live commercial qualification remains its own gate; no real billing operation is part of this preparation |
| Exit | Existing invitation/key/session revocation surfaces | Revoke access at the approved end; preserve records according to reviewed retention | This preparation performs no destructive org/data cleanup and promises no automatic fourteen-day deletion |

Existing test references include `tests/test_customer_real_approval_journey.py`,
`tests/test_developer_sdk_live_api.py`, and `tests/test_v1_customer_journey.py`.
Their local fixture evidence must be identified independently from real
delivery, provider, production or evaluator evidence. Never substitute mocked
Paddle, signed development IDV fixtures or repository database seeding for
real provider qualification.

## Precise authority-provisioning dependency for Antigravity

At this baseline, the HTTP surface exposes delegation create/chain/revoke
(`/api/governance/delegations...`). It does **not** expose a verified customer
HTTP path for initial legitimate root and explicit consent issuance. The
governance call requires this independent chain. The successful development
journeys use `seed_runtime_authority` in `tests/conftest.py`, which writes
`RootAuthorityRepository`, `ConsentProofRepository` and delegation records
directly with `explicit-test-fixture` evidence. That is intentionally a local
test fixture, not a supported external customer workflow.

**BLOCKED: real consequence-producing evaluator onboarding** until the core
owner supplies and independently qualifies a legitimate provisioning path
binding tenant, responsible root/principal, explicit consent, bounded
actions/targets/purpose, validity/revocation/version state and durable evidence.
An ADMIN role, paid subscription, API key or delegation endpoint alone cannot
fill this gap. No SQL/bootstrap-root workaround, browser authority calculator,
test-fixture import into a customer runtime or universally allowing policy is
permitted. Continue safe denial-only/read-only UX and SDK qualification while
this dependency remains open.

Required core handoff: exact source SHA, actual supported provisioning
interface, protected caller/CSRF semantics if browser-compatible, root/consent
evidence fields, revocation procedure and independently executed negative
cases. Once received, the frontend/SDK owner integrates the contract without
inventing one. Antigravity reports defects to the implementation owner rather
than silently changing production code during qualification.

## Evaluator script, after explicit release-owner activation

1. Confirm approved organization identity and end date privately; do not expose
   credentials in screenshots, tickets, logs or public qualification artifacts.
2. Complete real signup/verification/login and onboarding, then invite no more
   than the approved remaining participant slots through the existing console.
3. Create a least-privilege key and demonstrate missing-authority denial first.
4. If the canonical provisioning dependency is still open, **stop only the
   consequence-producing scenario**. Continue documentation, installation,
   tenant-scoped read-only navigation and negative API behavior.
5. Only with qualified authority: run the approved synthetic zero-cost action,
   approvals with distinct humans, revocation/replay negatives and evidence
   review. Do not run arbitrary network or filesystem effects for convenience.
6. Observe UNKNOWN as unresolved; no automatic retry. Record only actual
   identifiers returned, inspect evidence and request operator reconciliation.
7. At evaluation end revoke access through authorized supported controls and
   record disposition. Do not delete persistent billing/evidence records or
   provision a replacement account without authorization.

Exit criteria are binary and evidence-backed: real identity delivery, correct
tenant isolation, supported authority provisioning, one-shot effects, honest
outcomes, revocation continuity, clear evidence, accessible console and approved
operational resource/cost limits. Neither local benchmark success nor a document
opens production. External feedback must distinguish a usability observation
from security qualification.

## Provider evidence checklist — no provider changes

Use `docs/engineering/WAVE1_NINE_PLATFORM_MODEL.md` for the proposed boundaries
and source-based plan facts. Before any later approved deployment, collect:

| Provider | Required independent evidence |
| --- | --- |
| Google Cloud | Project/region/IAM and actual budget-cap scope; workload interruption, readiness and background enforcement continuity; no claim that a Run cap covers all costs |
| AWS | Account eligibility/plan expiry, approved retention/object-storage permissions, measured restore and transfer costs; no automatic credit-based availability claim |
| Cloudflare | Actual fail-closed Worker quota exhaustion, direct-origin rejection, current auth/webhook route coverage, TLS certificate and Host/Origin validation |
| Oracle | Region capacity/reclamation behavior, tested restore/containment; no assumed always-free high availability |
| Neon | Real transaction/locking/replay/epoch semantics, database outage behavior, region/pooling limits and independent restore evidence |
| Upstash | Command/TTL compatibility, queue duplication/loss reconciliation, quota/budget behavior; Redis cannot become authority |
| Better Stack | Sanitized health monitors, actual alert delivery and telemetry privacy; availability monitor cannot prove effect outcome |
| Deno Deploy | Current product/plan limits, no fixture-as-live fallback, quota pause behavior and optional public-only role |
| GitHub | Exact-head CI and artifacts, scoped permissions, action pins and independent reproduction; CI does not self-qualify production |

No account setup, provider secret inspection, Terraform apply, DNS action,
invitation, cloud provisioning, package publication or deployment was performed.
