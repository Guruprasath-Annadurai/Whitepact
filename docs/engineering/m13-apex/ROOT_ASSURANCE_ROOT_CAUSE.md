# APEX-ROOT-01 — root assurance contract mismatch

Status: BLOCKED; corrective security implementation owned by TITAN-1.
Independent implementation reviewed/tested:40e43440489eebde6886af014943ea18ed228b68,
tree c6b106db0974838f084e391ca8f8b2f084c45882. No root trust changes by Codex.

## Exact path

1. `src/responsibleai/db/web_identity_repository.py::verify_email` consumes the
   verification token and updates `email_verified_at`; it does not update
   `verification_status`.
2. `src/responsibleai/enterprise/verification.py::get_human_status` projects
   `UNVERIFIED` + verified email as `BASIC_VERIFIED`, without persisting it.
3. `src/responsibleai/enterprise/authority/service.py::initiate_root_bootstrap`
   with `require_identity_assurance=true` reads the durable verification status
   and accepts VERIFIED/IDENTITY_VERIFIED/BASIC_VERIFIED. It does not use the
   public projection. Owner/tenant validation occurs first.
4. Password and genuine WebAuthn UV establish session authentication assurance;
   they do not establish separate provider-backed identity proofing.
5. `VerificationService.start_human_verification` creates REVIEW_REQUIRED and
   returns the reference HMAC adapter's session. That adapter has no real hosted
   proofing flow (`hosted_url` is empty without a supplied return URL).
   Signed provider events update durable status, but self-signing a local
   reference event would be fixture evidence, not independent customer proofing.

## Actual reproduction

Separate25-stage APEX harness: real fresh PostgreSQL16.15, HTTP, local verification
mail and Chromium virtual WebAuthn. Same owner/org/session lineage. The added
GET `/api/enterprise/identity/verification` returned BASIC_VERIFIED,
email_verified=true, no provider, no assurance record. Root POST with both
required assurance and passkey stepup returned403 IDENTITY_ASSURANCE_REQUIRED.
Eight phases PASS, two BLOCKED, fifteen NOT_EXECUTED. Logout and original-cookie
invalidation verified; no authority was seeded. Receipt:
`/private/tmp/apex-closure-root-contract.json`. Harness working-tree provenance
was dirty at this run; do not relabel it committed-head validation.

## Required owner contract

TITAN-1 must decide and independently qualify whether durable BASIC_VERIFIED is
sufficient for root, or whether separate identity proofing is mandatory, and
make the status/read/qualification semantics consistent. Codex must not persist
an elevated state merely to match the projection. A real external trust authority
is required if the intended contract demands provider proofing; none is verified
by this run. Frontend must not label BASIC_VERIFIED as root authorization.

Unverified/non-owner/revoked/recovered/expired/replayed/cross-tenant/stale/forged
qualification and unauthorized-admin cases, plus PoP mismatch, remain mandatory
qualification gates. Existing independent suites cover some paths; this report
does not claim the complete requested root-assurance matrix was executed.

The original24-stage reproducer remains in commit8170a5fd. The new harness adds
the explicit identity qualification and post-revocation execution-attempt stages,
and validates exact phase identity/order. No skipped privileged phase is success.

## New owner checkpoint e1a9f123 — identity initiation advanced, root still FAIL

Independent detached candidate e1a9f1235d6b46b7423c21815ff27ebebf6887c6,
tree cd74e5efe91c61ec2d871525d244d39268bead9e. Email verification now persists
BASIC_VERIFIED only from UNVERIFIED, preserving suspended/rejected states.
The real customer status and root initiation now agree. This is basic email
assurance, not external identity proofing.

Actual fresh customer root completion with required identity assurance and
required genuine WebAuthn returns500. Backend IntegrityError is specifically
ForeignKeyViolationError on `trust_fabric_trust_roots_root_principal_id_fkey`.
Read-only diagnostic confirms user_exists=true and canonical_principal_count=0.
No principal was inserted by the harness. The service writes
root_principal_id=actor.user_id, but real signup/onboarding never creates that
canonical binding. APEX-ROOT-02 is P0, owned by TITAN-1. Do not seed an ACTIVE
principal or disable passkey/FK checks to advance the journey.

Owner-authored15 tests independently PASS,271.39seconds; original assertions
35PASS/1 known revision-head FAIL,177.21seconds. The owner full-chain test inserts
an ACTIVE HUMAN principal fixture and later initiates with required passkey=false.
Those scoped tests do not qualify this missing real customer contract.
Evidence `/private/tmp/apex-e1a9-principal-diagnostic.json`;
handoff https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6216956340.

The initial new-candidate receipt was invalidated by an overly linear harness
validator, not a product trust defect. Corrected checks follow actual contract
dependencies: root initiation precedes consent persistence, while root activation
requires persisted consent. Six receipt-integrity tests PASS. Original receipts
remain preserved; no invalid receipt was counted as customer acceptance.
