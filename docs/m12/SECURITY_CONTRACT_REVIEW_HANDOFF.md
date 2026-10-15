# M12 security-owner contract review — not an enabled API

Antigravity owns issuance/security decisions. No endpoint, migration or browser
authority is introduced by this proposal. GLOBAL PRODUCTION NO-GO.

## Exact source boundary

Codex parent0204a06f/tree0c5dc6b; security reference8eb41911/tree5c209f07.
Common ancestor6d20545f. The security worktree has active delegation/egress
changes. That work and the named unpublished remote branch must be stabilized
and reviewed before integration. Never cherry-pick a security-owned change just
because Git can merge it. PR198–203 ancestry already carries shared SDK work.

Internal trust_fabric/bootstrap.py::TrustBootstrapManager owns a trust-fabric root
ceremony. Canonical governance records are persisted by
db/root_authority_repository.py::RootAuthorityRepository and
db/consent_proof_repository.py::ConsentProofRepository. AuthorityResolver consumes
the governance chain. No supported authenticated customer bridge between these
domains was located. Trust-fabric roots, sessions, API keys, paid subscriptions and
owner roles are not interchangeable with canonical root/consent authority.

## Decisions required before implementation

1. Define what legitimately validates the organization and its initial owner;
   identify supported assurance/step-up APIs and verifier responsibilities.
2. Define a server-generated, principal/tenant-bound ceremony with expiry,
   intent/purpose/scope binding, durable one-use admission, stable read-only
   status and explicit uncertainty recovery. No duplicate-issuance retry.
3. Define explicit consent presented/acknowledged by the verified principal;
   server—not browser—derives tenant, root and consent identities. Bind record
   digest, permitted action/target, version and revocation rules atomically.
4. Specify whether/how internal Trust Fabric legitimacy bridges to canonical
   governance root/consent. Reject raw browser root objects or role-as-proof.
5. Review delegation/recovery/revocation authorization and independent audit
   evidence, including two-human separation where required. Define nondisclosing
   cross-tenant errors and epoch changes in the same transaction.
6. Define application/agent domain ownership separately from credentials,
   identity and authority. Registration must never mint a grant. Define tenant-
   scoped durable registration, policy/credential references, archival and
   revocation semantics, audit, uniqueness/concurrency and safe mutation contract.

## Required reviewed acceptance

Fresh DB → supported signup/organization APIs → verified owner → explicit consent
→ canonical authority → registered application/agent → narrow delegation →
allowed action plus denied action → distinct-human approval → exactly one
synthetic effect → evidence → revoked authority → further denial. Auth/CSRF and
tenancy remain enforced. No direct SQL seed or fixture hidden as provisioning.

Until those contracts are approved, G2/G3/G4 remain BLOCKED. Codex can consume a
reviewed contract but cannot choose the missing root-of-trust decision, invent
an authority API, enable fake controls or issue a shadow authorization token.

## Supply-chain findings for independent review

GitHub default-branch alerts24(source-map-js),23(Mako),22(multidict),2(nltk) are
not automatically candidate exposures. Candidate source-map-js1.2.2 is fixed;
uv.lock is absent in this lineage. Tested local Mako1.4.3 is above fixed1.4.2;
multidict/nltk were not installed in that environment. Optional sentiment extra
still permits NLTK affected byGHSA-8mgp-746c-j5xp; no patched version reported.
Its model-path sandbox bypass requires untrusted model paths. Current scoring
uses fixed VADER and never downloads at runtime; source pyproject comments about
a hardcoded nltk.download call are stale. This is not independent mitigation
acceptance and does not clear default-branch advisories. Review affected deployment
profiles and reject affected optional installations until approved mitigation.
