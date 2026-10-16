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
