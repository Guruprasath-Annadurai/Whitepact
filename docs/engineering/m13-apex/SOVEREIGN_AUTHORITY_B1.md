# A2 ratification and B1 development security contract

Founder directive: Operation Sovereign Authority (2026-10-18). A2 is RATIFIED:
verified mailbox, recent server-verified WebAuthn UV, active authenticated tenant
ownership, explicit scoped consent, root-key PoP and server enforcement. This
proves account/authenticator control, not legal/government identity. Existing
stricter enterprise SSO requirements and reusable-key IDENTITY_VERIFIED policy
remain. Caller assurance flags and legacy ceremony flags cannot bypass A2.

B1 authorization: architecture, isolated development prototype and qualification
only. PRODUCTION ACTIVATION IS NOT AUTHORIZED. Default feature gate is false;
the service and every endpoint reject non-development/process-production even
if configured true. Prototype tables are separate metadata, initialized only by
explicit gated development initialization; no Alembic migration or ordinary
startup enables B1. Production issuer/verification endpoints remain unavailable.

## Authentication protocol, not execution authority

Trusted issuer is the online WhitePact development authentication service,
`whitepact:dev-agent-auth:v1`; exact audience `whitepact:dev-agent-intent:v1`.
Credential is an opaque256-bit handle, stored only by SHA256 hash, bound in
authoritative PostgreSQL to a registered ACTIVE AI_AGENT, ACTIVE parent
APPLICATION, organization, qualified owner/delegator, A2 issuance session,
active root, exact delegation and consent references, current governance epoch,
agent Ed25519 public key and nonextendable120-second lifetime. Online database
verification is mandatory; this is not an offline/self-signed JWT issuer.

Possession of the handle is insufficient: the agent must sign a server-generated
single-use30-second challenge. Canonical challenge bytes bind protocol namespace,
operation, issuer, audience, credential hash, key, tenant/application/agent/owner,
root/delegation/consent references, epoch and exact method/path/body SHA256.
Issuance itself requires recent actual owner UV plus a separate agent-key PoP
challenge; the owner cannot register an unproven public-key binding. Challenge
consumption and credential write are transactional under the existing tenant
epoch lock. No client identity fields are accepted as verified facts.

Verification rechecks persisted credential, owner A2 session/lifecycle, tenant,
application/agent, referenced root/delegation/consent and epoch. This deliberately
short prototype also stops authenticating when its issuance session is revoked,
expired or logged out; unattended long-lived agent autonomy is not approved.
Authority resolver and policy kernel still decide each intent's actual action,
target, constraints, consent and delegation. B1 authenticates only. It never
constructs an ExecutionAuthorization, ExecutionGrant, approval or effect receipt.

The product adapter builds OrgContext from the verified agent principal with
authentication_method=agent_pop and uses existing apply_governance. Human
approval remains customer-session/tenant bound and canonical resume_approval
issues/consumes its own short-lived execution authorization. The authentication
handle and approval record are never substituted for an execution permit.
The established ExecutionAuthorization is a30-second internal permit; if a
separate Phase7A durable ExecutionGrant is required, report that distinction and
do not relabel a token or manufacture a grant row.

## Rotation, revocation and trust changes

One current live credential per agent. Concurrent ordinary issuance has one
winner; a rotation challenge binds the exact previous credential hash and new
key. Rotation transaction revokes old credential before installing the new one;
concurrent rotation against a stale predecessor fails. Old key/handle cannot
authenticate. Revocation is available only to qualified tenant owner and takes
effect immediately at online verification; it does not claim to cancel already
admitted effects. Existing runtime revocation/epoch and containment remain needed.
Prototype rotation/revocation conservatively bumps the existing tenant epoch,
invalidating pending approvals and all epoch-bound agent credentials; renewal
of other affected agents is explicit. This is deliberately broader than a future
per-agent epoch optimization and adds no new revocation engine.

Root key replacement, epoch change, root/delegation/consent expiry/revocation,
suspension, recovery or parent application disablement invalidates the credential
through referenced state and current checks. Fresh issuance requires qualified
owner and agent PoP again. No alternate shared issuer or reusable-key fallback.
Key compromise: revoke, bump authority epoch through supported mechanism if
required, contain existing effects, issue proven replacement only after review.

## Threat model and qualification gates

| Threat | Required defense / negative evidence |
|---|---|
|Stolen handle / forged agent|Ed25519 PoP over server challenge; never bearer-only execution|
|Wrong issuer/audience or protocol|Exact online pinned namespace/audience and stored row binding|
|Cross-tenant/application/agent substitution|Persisted binding comparisons, not payload labels|
|Replay / concurrent nonce use|Single-use atomic DB consume and tenant epoch serialization|
|Intent mutation|Exact method/path/canonical body digest in challenge|
|Expired/future or stale credential|Server time bounds,120s hard TTL, current epoch/state|
|Revoked owner/session/grant/root|Fresh persisted qualification each verification|
|Rotation race / stolen old key|Expected predecessor and single live credential transaction|
|DB outage / malformed stored data|No cache authority; deny, no intent reaches kernel|
|Resource exhaustion|Bounded fields/body, shared600/min unauthenticated bucket before lookup, durable per-owner/verified-credential limits, one live challenge per operation; no H6 load-test claim|
|Approval/grant replay|Existing canonical digest/policy/epoch/expiry/nonce mechanisms, independently tested|
|Production configuration mistake|False default plus unconditional environment/process-production refusal|

Before a development issuer is exposed beyond isolated qualification, independently
review this model and test positive issuance, stolen/forged proof, wrong audience,
cross-tenant, expiration, nonce replay, stale epoch, lifecycle/recovery revocation,
rotation/concurrent issuance, storage failure and default-disabled behavior.
In-process test authenticators and seeded negative corruption cases are component
evidence only; genuine browser/HTTP customer receipts remain separately labeled.

Production prerequisites: independent security acceptance; approved persistent
schema/migration and least-privilege role; issuer/key management and incident
process; threat/DoS/privacy review; backup/recovery and version fencing; full
real25-stage journey and mandatory CI/compliance gates; explicit separate founder
production-enablement authorization. None is implied by prototype qualification.

## Independent review disposition

Read-only implementation review found no P0/P1 authority bypass by inspection;
this is not executable acceptance or independent external security approval.
The review identified unbounded persistent rate counters for invalid handles.
The prototype now charges one fixed unauthenticated bucket before validation and
creates credential buckets only for existing, currently qualified credentials.
Actual PostgreSQL regression covers twelve distinct invalid handles and verifies
that only the shared counter exists. Its shared budget can cause availability
denials under sustained invalid traffic; deployment-level DoS qualification
remains a production prerequisite.

P2 OPEN: the existing ownership-transfer transaction locks membership before
organization; A2 and existing passkey enrollment lock organization before
membership. PostgreSQL can abort one concurrent operation for deadlock. This
fails closed but requires lock-order alignment and an actual concurrent transfer
regression before claiming complete concurrency qualification. It is not hidden
by the agent-issuance concurrency tests.

Local browser development qualification reached genuine agent judgment and
customer approval. Execution then failed closed on macOS because the isolation
backend requires POSIX ACLs for its unprivileged container user. Do not add a
world-readable or unisolated fallback. The dedicated Linux workflow installs
ACL support and runs the complete browser path with actual Docker isolation.
Its results must be inspected on the committed head before claiming stage19–24
success. Preserved historical DCO, Ruff, Gitleaks, migration and dead-worker
assertion conflicts remain release blockers unless independently dispositioned.
