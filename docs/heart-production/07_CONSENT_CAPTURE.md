# Heart Phase H4 — Consent Capture REST API

> Continues the numbered series (`00`-`06`, this is `07`). Closes the
> gap `governance/consent_proof.py`'s own module docstring named since
> Heart Phase H4 shipped: "not built here: real wiring from an actual
> consent-capture UI/flow into a persisted `ConsentProof`, and any DB
> persistence layer for this type." Persistence landed in Gap 3 Phase 3
> (`ConsentProofRepository`); this phase is the actual capture flow.

## What this phase builds

Three REST endpoints in `dashboard/app.py`, mirroring the existing
Authority Passport endpoints' shape exactly (issue/get/revoke, same
role tiers, same "re-validate against the live source on every read"
discipline):

- **`POST /api/governance/consent-proofs`** (ADMIN+) — captures a real
  `ConsentProof`. The authenticated request **is** the consent act
  (`ConsentMethod.API_AUTHENTICATED_REQUEST`) — the caller is always
  the consenting party; `subject_id`/`consenting_root_id` are never
  accepted from the request body, only derived from the authenticated
  `OrgContext`. Get-or-creates the caller's own root of trust via the
  same `resolve_root_for_identity()` Heart Production Integration
  Phase 6 already built and uses for its live gate — a consent proof
  captured here shares its root with anything else that identity does
  through the governed path, no separate bootstrap.
- **`GET /api/governance/consent-proofs/{consent_id}`** (ANALYST+) —
  fetches the proof and re-validates it against its actual root chain
  in the same response, via `validate_root_chain()` +
  `validate_consent_proof()`. A proof is never trusted as legitimate
  just because it exists in storage.
- **`POST /api/governance/consent-proofs/{consent_id}/revoke`**
  (ADMIN+).

## The org-isolation fix this phase's own testing caught

`ConsentProof` (Heart Phase H4) has no `organization_id` field at all
— a deliberate Heart design choice (org-agnostic types at the Heart
layer, per `root_authority.py`'s own TCB-minimization discipline).
`RootAuthorityRecord` *does* carry `organization_id`. The first draft
of `GET`/`revoke` checked nothing beyond "does this `consent_id`
exist" — meaning an authenticated caller from **any** org could fetch
or revoke **any other org's** consent proof by ID, since
`ConsentProofRepository.get()` itself has no org scoping. Fixed by
resolving the proof's `consenting_root_id` and checking
`root.organization_id != _auth.org_id` before returning anything —
both a missing root and a cross-org root fail closed to the same `404`
a genuinely nonexistent proof returns, never distinguishing "exists
but isn't yours" from "doesn't exist." Caught by writing
`test_cross_org_consent_proof_not_visible` before considering the
endpoint done, not discovered after the fact.

## What this deliberately does not do

- **Does not wire captured `ConsentProof`s into the live legitimacy
  gate.** Phase 6's `resolve_authority_grant()` still only supplies
  `root`/`root_resolver`/`requested_action_types` to
  `sovereignty_kernel.evaluate()` — consent, purpose-binding, and
  delegation-legitimacy checks remain unrun on the live path, exactly
  as `06_PHASE6_LIVE_WIRING.md` named. This phase makes real
  `ConsentProof`s capturable and independently verifiable; actually
  consulting one during a live governed decision is separate,
  additional wiring (would need `resolve_authority_grant()` to accept
  a `ConsentProof` parameter and look one up for the acting identity)
  — a real, natural next step this phase unblocks but does not itself
  take.
- **Does not build a human-facing consent UI.** This dashboard's
  governance surface is REST-API-first (matching every other feature
  in this file — delegations, authority passports, intent contracts);
  there is no separate frontend to wire a consent-capture form into in
  this codebase today. `ConsentMethod.API_AUTHENTICATED_REQUEST` is
  the honest name for what this endpoint actually captures — not
  `EXPLICIT_UI_ACTION`, which would claim a UI interaction that
  doesn't exist.
- **Does not let a caller declare consent on another identity's
  behalf.** `subject_id` is always the authenticated caller's own
  `identity_id` — capturing consent for a *different* human/root
  requires that human's own authenticated request, not an admin
  asserting it on their behalf, which would defeat the entire premise
  of a root-backed consent record.

## Verification

- 10 new tests (`tests/test_governance_api.py::TestConsentProofEndpoints`),
  all passing: role enforcement (ADMIN can capture/revoke, ANALYST can
  only read), the request body cannot smuggle a different subject/root
  in, a static-API-key-captured proof reports immediately valid, an
  unknown `consent_id` is 404, revocation sets the right fields and
  flips validation to `REVOKED`/invalid, cross-org isolation on both
  `GET` and `revoke`, and that two captures by the same identity share
  one root (`resolve_root_for_identity()`'s get-or-create semantics).
- Full `test_governance_api.py` file re-run clean: 99 tests, no
  regressions.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 169 source files (no new source
  modules — additions to `dashboard/app.py` and export lists only).
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
