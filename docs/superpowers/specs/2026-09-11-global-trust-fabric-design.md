# WhitePact Enterprise Phase 3: Global Trust Fabric & Principal Intelligence
## Technical Design Specification

- **Date:** 2026-09-11
- **Status:** Approved under Human Pre-Authorization
- **Author:** Principal Identity & Trust Infrastructure Architect
- **Target Branch:** `feature/global-trust-fabric-phase3`
- **Baseline SHA:** `93c8e88c89c373d24d35ff074a283d8c61e065e1`

---

## 1. Executive Summary & Product Mission

WhitePact Phase 3 transforms WhitePact from an execution gateway and local model evaluator into the **WhitePact Global Trust Fabric & Principal Intelligence**.

It provides a neutral, decentralized, cryptographically verifiable trust infrastructure capable of answering fundamental verification questions for:
1. **Humans** (Employees, signatories, executives, contractors, counterparty representatives)
2. **Organizations** (Enterprises, subsidiaries, partners, suppliers, government entities)
3. **AI Agents** (Autonomous agents, LLM tool callers, multi-agent delegates)
4. **Workloads** (Cloud jobs, pipelines, containers, serverless functions)
5. **Services** (Microservices, APIs, internal applications)
6. **Machines** (Hardware devices, cryptographic keyholders, gateways)

### Core Questions Answered:
- **Who or what is this principal?**
- **Who verified it, and via what method?**
- **What organization does it belong to?**
- **What relationships are currently active and valid?**
- **What specific authority does it actually hold?**
- **Who delegated that authority, and under what ceiling/scope?**
- **Is that authority and credential current or expired/revoked?**
- **What evidence supports the claim, and when was it last verified?**
- **Are independent sources in conflict?**
- **Can this exact proposed transaction or interaction legitimately proceed?**

---

## 2. Constitutional Invariants & Non-Goals

### 2.1 The Neutrality & Anti-Surveillance Doctrine
WhitePact does **NOT** determine whether a human is morally trustworthy or a "good person."
- **NO Universal Reputation Score:** WhitePact never outputs "John is 94/100 trustworthy."
- **NO Social Credit System:** Behavior, social media, political opinions, or personal habits are never ingested or scored.
- **NO Surveillance Dossiers:** Residential addresses, personal family data, medical records, religion, private phone books, or secret government trackers are strictly prohibited.
- **NO Speculative Profiling:** "Criminal-looking" inference or bias-based scoring is prohibited.
- **NO Data Selling:** Personal identity records are never packaged, sold, or shared for ad targeting.

### 2.2 Customer Sovereignty & Anti-Backdoor Doctrine
WhitePact may **ENFORCE** organizational authority, but WhitePact must **NEVER** silently become the customer organization's root authority.
```
HUMAN / ORGANIZATION (Customer Sovereignty)
        │
        ▼
LEGITIMATE TRUST BOOTSTRAP CEREMONY (Atomic, Single Winner, Proof of Control)
        │
        ▼
ORGANIZATION TRUST ROOT (Cryptographic Anchor)
        │
        ▼
PRINCIPAL / RELATIONSHIP / AUTHORITY GRAPH
        │
        ▼
WHITEPACT EVALUATION & JUDGMENT
        │
        ▼
INDEPENDENT EXECUTION ENFORCEMENT
```
- **Forbidden:** WhitePact operators possessing an undocumented or default master owner backdoor.
- **Forbidden:** Ambient software signing credentials acting as customer organization authority.

---

## 3. Principal Architecture & Lifecycle

### 3.1 Principal Types
Every entity in the fabric is represented by a canonical `Principal` model:
- `HUMAN`
- `ORGANIZATION`
- `AI_AGENT`
- `WORKLOAD`
- `SERVICE`
- `MACHINE`

### 3.2 Canonical Principal ID
Every principal is assigned an immutable, tenant-scoped, cryptographic canonical ID:
`wp_prin_<uuid4>`.
- An email, phone, domain, legal entity number, or username is an **Identifier OF a principal**, never the canonical identity itself.
- When an employee leaves a company and the email is recycled to a new hire, the new hire receives a **NEW** canonical `principal_id`. Historical authority and audit logs remain permanently attached to the predecessor.

### 3.3 Principal Lifecycle States
- `PENDING_VERIFICATION`: Registered, awaiting challenge or verification.
- `ACTIVE`: Legitimately verified and in good standing.
- `SUSPENDED`: Temporarily halted pending security review or challenge.
- `DISABLED`: Administratively shut down; cannot hold or exercise authority.
- `REVOKED`: Cryptographically revoked or invalid.
- `DELETED`: Tombstoned for security audit; identifier claims released but history preserved.
- `CONFLICTED`: Material contradictions detected across sources; decisions require review.

---

## 4. Global Identifier Model & Normalization

Principals possess one or more normalized identifiers:
- `EMAIL` (Normalized: lowercase, stripped spaces, canonical domain)
- `DOMAIN` (Normalized: lowercase, punycode/IDN decoded, stripped trailing dot)
- `PHONE` (Normalized: E.164 standard)
- `REGISTRATION_NUMBER` (Jurisdiction-prefixed, e.g., `US_DE:1234567`)
- `PUBLIC_KEY` (Hex/Base64 SPKI SHA-256 fingerprint)
- `CREDENTIAL_ID` (Verifiable Credential / X.509 serial)
- `AGENT_DEPLOYMENT_ID` (Unique container / cluster workload identifier)
- `EXTERNAL_DIRECTORY_ID` (Enterprise IdP / SCIM external ID)

### Identifier Protections:
- **Resurrection Defense:** Deleted principals release active identifier bindings, but historical audit binds to immutable `principal_id`. New bindings to the same string generate a fresh `principal_id`.
- **Cross-Tenant Collision Prevention:** Identifiers are strictly scoped to `org_id` unless globally unique and cryptographically proven (e.g., verified domains, public keys).

---

## 5. Source Hierarchy & Field-Level Provenance

### 5.1 The 6-Tier Source Taxonomy
Every verified attribute carries a source tier:
1. **TIER A — Cryptographic / Root Proof:**
   - Hardware key possession (WebAuthn, HSM), DNSSEC domain control, mutual TLS, signed assertion from an organization trust root.
2. **TIER B — Authoritative Legal / Government Registry:**
   - Official national company register (e.g., SEC EDGAR, UK Companies House, EU Business Registers).
3. **TIER C — Organization-Controlled Authoritative Source:**
   - Verified enterprise directory (IdP / Okta / Azure AD), enterprise HR system, domain-hosted security.txt.
4. **TIER D — Verified Third-Party Provider:**
   - Regulated financial identity provider, verified counterparty network.
5. **TIER E — Public Professional Source:**
   - Official public website, verified professional registry.
6. **TIER F — Self-Attestation:**
   - Unverified assertion made by the subject.

### Strict Trust Rule:
**Self-attestation (Tier F) NEVER equals Verified Authority or High Assurance.**

### 5.2 Field-Level Provenance Structure
Every significant attribute in the trust fabric carries:
- `value`: Attribute value.
- `source_id`: Reference to the registered `TrustSource`.
- `source_tier`: Tier A through F.
- `verification_method`: Exact protocol used (`DNS_TXT`, `OIDC_ID_TOKEN`, `CRYPTOGRAPHIC_SIGNATURE`, `LEGAL_REGISTRY_API`).
- `verified_at`: Timestamp of verification.
- `expires_at`: Validity deadline.
- `last_checked_at`: Freshness verification timestamp.
- `assurance_level`: `LOW`, `MEDIUM`, `HIGH`, `CRYPTOGRAPHIC`.
- `disclosure_class`: Privacy classification.
- `revoked_at`: Timestamp if invalidated.

---

## 6. Multi-Dimensional Assurance Model

Rather than a single opaque score, WhitePact outputs a 6-dimensional assurance vector:
```json
{
  "identity_assurance": "HIGH",
  "affiliation_assurance": "HIGH",
  "authority_assurance": "MEDIUM",
  "source_freshness": "CURRENT",
  "credential_state": "VALID",
  "conflict_state": "NONE"
}
```
This guarantees that **identity confidence** (knowing who someone is) is never confused with **authority** (knowing what they are permitted to do) or **moral trustworthiness**.

---

## 7. Organization Trust Bootstrap Ceremony

### Threat Model:
An attacker intercepts the setup link or races the legitimate administrator to claim the root `OWNER` of a new organization.

### The Atomic Bootstrap Protocol:
1. When an organization is created, an ephemeral single-use bootstrap nonce and cryptographically random challenge token are generated with a strict TTL (e.g., 15 minutes).
2. The bootstrap request requires:
   - `organization_id`
   - `bootstrap_token`
   - `root_principal_id` (the human claiming initial ownership)
   - `public_key` or authentication proof
3. **Atomic DB Constraint:** An atomic SQL conditional insert/update ensures that:
   - If an organization trust root already exists, bootstrap **FAILS CLOSED** (`OrganizationAlreadyBootstrappedError`).
   - If multiple requests race concurrently, exactly **ONE** transaction commits (`409 Conflict` / `IntegrityError` for all others).
4. The bootstrap token is instantly marked consumed (`consumed_at = NOW`). Replay attempts are immediately rejected.
5. WhitePact operators possess **zero** bypass methods to claim ownership.

---

## 8. Principal Relationships & Authority Graph

### 8.1 Principal Relationships
Directional edges linking principals within an organizational context:
- `EMPLOYED_BY` (Human -> Org)
- `DIRECTOR_OF` (Human -> Org)
- `OPERATED_BY` (AI Agent -> Human or Service)
- `OWNED_BY` (AI Agent / Workload -> Org)
- `CONTRACTOR_FOR` (Human / Org -> Org)
- `SUBSIDIARY_OF` (Org -> Org)

### 8.2 Authority Graph Edges
Explicit grants of authority:
- `grantor_principal_id`: Who authorized this?
- `grantee_principal_id`: Who holds the authority?
- `organization_id`: In what tenant context?
- `action_type`: Specific allowed action (e.g., `payment.transfer`, `contract.sign`).
- `resource_pattern`: Target resource (e.g., `account:supplier:*`).
- `ceiling_limit_usd`: Financial or volumetric cap (e.g., `250000.00`).
- `valid_from` / `expires_at`: Bounded time window.
- `delegation_depth`: Max hops (0 = non-delegable).
- `revoked_at`: Explicit revocation marker.

---

## 9. Trust Passport & Selective Disclosure

### 9.1 Trust Passport Formats
A cryptographically signed, verifiable assertion summary for a principal:
- **Human Passport:** Verified professional role, active affiliations, credential validity, authority ceilings, freshness, zero private residential or personal contact data.
- **Organization Passport:** Legal entity name, registration number, official verified domains, authorized representatives, trust-root status.
- **Agent Passport:** Agent identity, owning organization, responsible operator, runtime workload hash, delegated authorities, credential status.

### 9.2 Privacy & Selective Disclosure Classes
1. `PUBLIC`: Universally viewable (e.g., Organization legal name, primary verified domain).
2. `BUSINESS_PUBLIC`: Viewable by business counterparties (e.g., Director name, signing authority ceiling).
3. `TENANT_INTERNAL`: Viewable only within the same organization (e.g., Internal employee ID, department).
4. `SECURITY_RESTRICTED`: Viewable only by security administrators and audit logs (e.g., Audit event IDs, IP hashes).
5. `NEVER_PUBLIC`: Strictly unexportable secrets (e.g., Private keys, MFA seeds, internal passwords).

---

## 10. Trust Proofs & Challenge Protocol

### 10.1 Trust Proofs
Factual verification queries returning boolean/state judgments:
- `PROVE_EMPLOYMENT(principal, organization)`
- `PROVE_SIGNING_AUTHORITY(principal, organization, amount)`
- `PROVE_AGENT_OWNERSHIP(agent, organization)`
- `PROVE_DOMAIN_CONTROL(organization, domain)`
- `PROVE_CREDENTIAL_VALIDITY(principal, credential_id)`

Possible Truth Valuations:
- `PROVEN`
- `NOT_PROVEN`
- `CONFLICTED`
- `EXPIRED`
- `REVOKED`
- `UNKNOWN`
- `REQUIRES_REVIEW`

### 10.2 Trust Challenge Protocol
When an unknown principal or unverified claim is presented:
1. Status is immediately evaluated as `UNKNOWN` (Zero hallucination).
2. A cryptographic `TrustChallenge` is issued:
   - `CHALLENGE_DNS_TXT`: Write nonce to `_whitepact-challenge.<domain>`.
   - `CHALLENGE_KEY_POSSESSION`: Sign nonce with private key matching registered public key.
   - `CHALLENGE_EMAIL_OTP`: Provide single-use token sent to enterprise email.
   - `CHALLENGE_ORG_ASSERTION`: Require signed assertion from Organization Trust Root.
3. Upon successful challenge completion, state advances from `PENDING_VERIFICATION` to `ACTIVE`.

---

## 11. Trust Conflict Resolution Engine

When independent sources contradict each other (e.g., Registry says Alice is Director, HR directory says Alice is Terminated):
1. **Explicit Representation:** Record marked as `CONFLICTED`.
2. **Conflict Evaluation:**
   - Higher-tier sources supersede lower-tier sources (Tier B Legal Registry > Tier F Self-attestation).
   - Fresh authoritative sources supersede stale sources.
   - Equal-tier direct contradictions cannot be automatically resolved.
3. **Fail-Closed Governance:** Consequential decisions involving conflicted claims return `REQUIRES_REVIEW` or `DENY`. Under no circumstances does the system silently upgrade confidence.

---

## 12. Continuous Trust Monitor & Freshness Tracking

Trust is temporal. The monitor tracks:
- Credential expiration and key rotation.
- Employment termination events.
- Authority ceiling expirations.
- Revocation propagation.
- **Cache Discipline:** Cached trust decisions expire automatically with source TTL. If Redis or cache fails, decisions **fail closed** to canonical database evaluation. A stale cache entry **never** widens authority.

---

## 13. Trust Decision API

Enterprise endpoint for transaction gating and counterparty verification:
`POST /api/v1/trust/decision`

```json
{
  "requesting_org_id": "org_acme_corp",
  "subject_principal_id": "wp_prin_agent_8812",
  "target_org_id": "org_acme_corp",
  "requested_action": "payment.disburse",
  "context": {
    "amount_usd": 250000.00,
    "counterparty_org_id": "org_supplier_global"
  }
}
```

Response:
```json
{
  "decision": "DENY",
  "reason_code": "AUTHORITY_CEILING_EXCEEDED",
  "explanation": "Agent wp_prin_agent_8812 has valid delegated purchasing authority capped at $100,000.00 USD. Requested transaction of $250,000.00 USD exceeds the ceiling.",
  "assurance": {
    "identity": "HIGH",
    "affiliation": "HIGH",
    "authority": "CEILING_EXCEEDED",
    "freshness": "CURRENT",
    "conflict": "NONE"
  },
  "evidence_references": ["ev_chain_8849102"]
}
```

---

## 14. Enterprise Trust Mesh & Federated Assertions

Enables cross-organizational trust federation without leaking employee directories:
- **Federated Claim Assertion:** Signed cryptographic assertion from Organization A asserting that Principal P is an authorized representative with specific authority scope.
- **Bound Claims:** `issuer` (Org A Trust Root), `subject` (Principal P), `audience` (Org B), `scope`, `not_before`, `expires_at`, `nonce`, `key_id`, `signature`.
- **Validation:** Rejects issuer substitution, subject substitution, expired tokens, tampered signatures, and cross-tenant replays.

---

## 15. Database Schema & Migration Strategy (0043)

A dedicated Alembic migration `0043_global_trust_fabric.py` will introduce canonical relational tables:
1. `trust_fabric_principals`
2. `trust_fabric_identifiers`
3. `trust_fabric_sources`
4. `trust_fabric_assertions`
5. `trust_fabric_relationships`
6. `trust_fabric_authority_edges`
7. `trust_fabric_trust_roots`
8. `trust_fabric_bootstrap_records`
9. `trust_fabric_passports`
10. `trust_fabric_conflicts`
11. `trust_fabric_challenges`
12. `trust_fabric_federated_assertions`

Every table includes:
- Strict `org_id` referencing `organizations(id)` where tenant-scoped.
- Unique constraints preventing race conditions and duplicate claims.
- Foreign key constraints with proper `ON DELETE RESTRICT/CASCADE`.
- Indices on all lookup keys (`principal_id`, `normalized_value`, `org_id`, `expires_at`).
- Clean compatibility across PostgreSQL and SQLite.

---

## 16. Self-Review & Verification Criteria

- **Zero Overlap:** Does not touch Checkpoint 6, DNS transport, or Phase 2 runtime isolation.
- **Zero Backdoors:** Customer organizations hold root sovereignty.
- **Privacy Guaranteed:** Field-level disclosure classes prevent private dossier leakage.
- **Deterministic Adversarial Suites:** 40+ distinct red-team test scenarios covering races, replay, tampering, and trust inflation.
- **Production Integrity:** Ruff, Mypy, SPDX, Gitleaks, and PostgreSQL tests pass at 100%.
