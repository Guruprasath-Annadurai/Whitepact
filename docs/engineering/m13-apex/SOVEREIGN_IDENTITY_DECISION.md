# Founder Decision Record A — precise decision required, NOT RATIFIED

Status: proposed options only. No assurance or credential policy changed.
M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Existing contracts

`enterprise/issuance.py` is the canonical reusable human/service API-credential
gate: IDENTITY_VERIFIED is required. Verified mailbox BASIC_VERIFIED does not
satisfy it. The actual customer403 at stage17 is an enforced requirement, not
an invitation to set a verification flag. No configured legitimate external
identity-proofing receipt has been supplied for the browser customer.

Root bootstrap, explicit consent and bounded delegation establish authority.
Application/agent inventory does not issue an authentication credential. Passkey
UV proves control of an authenticator for a session, not a person's legal identity
or control of an organization's legal registration. The agent also needs its own
authenticated principal binding; a copied human cookie is inappropriate.

The customer approval GET/resolve/execute routes and governance approval execution
routes already use canonical `resume_approval`. `/api/governance/tools/call`
explicitly does not mint an ExecutionGrant. MCP OAuth authorization starts with
an existing API credential; it cannot bootstrap a customer out of the identity
issuance prerequisite. Existing judgment, approval, grant, runtime, evidence and
revocation primitives must remain the only authority path.

## A. Self-service root assurance alternatives

| Option | Meaning | Consequence |
|---|---|---|
|A1|Independently established IDENTITY_VERIFIED before self-service root|Requires legitimate approved proofing integration; excludes mailbox-only onboarding|
|A2 — recommendation, unapproved|Verified email plus recent server-verified WebAuthn UV for self-service root; enterprise can demand stronger proofing|Proves account/authenticator control, not legal identity; requires explicit policy, freshness, tenant binding and lifecycle qualification|
|A3|Mailbox/password alone|Insufficient recommended control for consequential self-service root; do not adopt implicitly|

Minimum defensible account-control recommendation is A2, with server-enforced
UV/freshness and no silent optional-client-flag bypass of the selected policy.
It is not a universal legal-identity assurance claim. Founder must select the
product's actual assurance promise. Existing test behavior does not ratify A2.

## B. Agent authentication alternatives — independent decision

| Option | Authentication contract | Implementation status |
|---|---|---|
|B0|Keep reusable credential requirement; legitimately proof customer identity through an approved provider and then use existing canonical issuance|Current gate retained; provider and proofing onboarding unavailable|
|B1|Explicit new short-lived, proof-of-possession agent authentication contract under a qualified owner/root|Policy-dependent; NOT implemented or enabled|

A2 does not itself authorize B1 or weaken reusable-key issuance. If B1 is chosen,
the smallest candidate is an authority-bound authentication credential: issuer
qualified by the selected policy; agent key possession verified; tenant,
application, agent, root/delegation reference, audience, expiry and revocation
epoch bound and independently validated. Issuance must require recent actual
owner UV and current membership/root authority, not a client assurance claim.
Such a credential authenticates an agent; it is never an execution grant.
Canonical judgment still checks current delegation, consent, ceilings and policy;
approval still binds the exact intent/policy/epoch; only the kernel grants
short-lived, single-use, effect-scoped execution authority.

## Threats and trust separation

- Credential/key theft: short lifetimes, exact audience, per-agent keys, no human
  cookie reuse; possession binding with replay-resistant server challenges.
- Replay/stale authority: single-use challenges; canonical epoch checks at issuance,
  judgment, approval resume and execution; nonce consumption before effect.
- Tenant/application confusion: verify every binding against persisted authority;
  reject a valid credential for the wrong audience, tenant, agent or application.
- Founder/platform impersonation: operators cannot fabricate customer consent,
  legal identity or root PoP. Authenticator UV is not an identity-provider assertion.
- Approval confusion: tenant, principal, agent, action, intent digest, policy
  version, epoch and time window must all match; approval is not executable authority.
- Evidence: bind real execution receipt to grant/intent/policy/identity; local
  storage alone is not independently witnessed evidence. Do not claim witness
  qualification from local receipt assertions.

## Migration and compatibility consequences

Any chosen policy needs explicit policy version, persisted assurance provenance,
new-credential audience/version compatibility, revocation semantics and supported
rollback. Existing BASIC roots cannot be silently relabeled legally verified.
Do not silently grandfather unsupported credentials or let old binaries ignore
new issuer/assurance fields. Fence historical DB credentials before incompatible
semantics become active. Product eligibility must distinguish root assurance,
human proofing and agent authentication. No live state migration is authorized here.

## Required adversarial acceptance before enabling B1

Real owner UV and agent PoP; replayed/expired challenges; stolen bearer without
agent key; wrong issuer/audience; future/stale tokens; suspended/disabled owner;
membership and organization revocation; cross-tenant/application/agent substitution;
root/delegation revocation; grant/approval policy and epoch drift; concurrent
issuance and single-use execution; restart; actual failure before effect;
old credential/schema compatibility; genuine full25-stage fresh-PG journey.
Use no fabricated IDENTITY_VERIFIED state or approval/grant/evidence fixture to
claim customer acceptance. Separate component tests remain separately labeled.

## Exact founder decision

1. Ratify A1 or A2 for self-service root and specify required proofing promises,
   enterprise override and freshness/recovery requirements.
2. Choose B0 with an approved legitimate provider/onboarding contract, or explicitly
   authorize design/qualification of B1 with issuer, audience, lifetime, key
   possession, revocation and assurance requirements. Neither is implied by A2.
3. Approve migration/compatibility handling before enabling policy-dependent APIs.

Until then: reusable key gate unchanged, stage17 BLOCKED, stages18–24
NOT_EXECUTED. Existing17 genuine stages preserved. No request for production
deployment, protected merge, package publication or M14 authorization.
