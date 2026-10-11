# Decision paper: who may change policy, and how (register REC-25)

Status: **FOUNDER DECISION REQUIRED. The privileged-policy-change gate stays OPEN until one option is approved.**
This paper does not choose. It states what exists, what each option changes, and what each costs.

## What exists today (verified by reading the routes)

* Web console: `POST/DELETE /api/v1/web/policy/rules`, `POST /api/v1/web/policy/reorder`. Requires a session, CSRF, and
  role OWNER or ADMIN. Effective immediately.
* API key: `POST/DELETE /api/governance/policy/rules`, `POST /api/governance/policy/reorder`. Requires role ADMIN. Effective
  immediately.
* Every change is attributed and recoverable: `governance_policy_history` (migration `0062`), hash-chained, with the full
  rule set after each change; an admin read endpoint reports chain validity. A deleted or truncated history is detected
  against the policy-version counter. No external anchor exists.
* Policy changes bump the governance revocation epoch, so approvals and grants issued under the old policy cannot resume.
* **Not used by any route:** `governance/policy_lifecycle.py`: immutable revisions with change reason and optional
  `approval_id`, single-winner activation, rollback, and a `PrivilegedSurfaceGuard` that can require step-up and
  four-eyes. Its activation now also writes `governance_policy_history`, so wiring it later needs no schema change.
* No step-up authentication and no second approver on any policy change.

## The risk being decided

A single compromised or coerced ADMIN session (or ADMIN API key) can weaken policy in one request: delete a DENY, add a
broad ALLOW, reorder a rule under a broader one. It is attributed afterwards and the previous rules are recoverable from
history, but it is not prevented. Because policy decides what the isolated executor is asked to run, this is the
shortest path from one stolen admin credential to a governed side effect.

Tightening is different from loosening. Adding a DENY or REQUIRE_APPROVAL rule cannot create a new side effect;
removing one, adding an ALLOW, or moving a rule so a broader one matches first, can.

## Options

| | A. Documented single-admin model | B. Four-eyes for every policy change | C. Tiered: free to tighten, four-eyes to loosen |
| --- | --- | --- | --- |
| Who can change policy | OWNER/ADMIN alone | Proposer + a different approver, plus step-up | Tightening: ADMIN alone. Loosening: proposer + different approver + step-up |
| Prevents one stolen admin from weakening policy | No (detect + recover only) | Yes | Yes for loosening; tightening is harmless by construction |
| Work to implement | None beyond docs and warnings | Wire `policy_lifecycle` into web + API routes; approval UI; tests | B plus a classifier of "loosening" (effect, shadowing, ordering); more tests |
| Admin experience / journey impact | None | Every edit becomes a request; the CI customer journey and `tests/js/customer-journey.e2e.mjs` change | Only loosening edits wait for a second person |
| Small teams | Works | A one-person org cannot edit policy; needs a break-glass rule | One-person orgs can still tighten; loosening needs a second human or an explicit break-glass |
| Residual risk | Credential theft = policy weakening | Collusion of two admins; break-glass abuse | Classifier bugs (a loosening mis-classified as tightening) |
| What to say publicly | "Policy edits are attributed and reversible, not two-person controlled" | "Two-person policy control" (only after it is tested and independently reviewed) | "Loosening needs a second approver" (same condition) |

## Option C is built and switched off

`WHITEPACT_POLICY_GOVERNANCE_MODE` (`single_admin` by default, `tiered`) selects the model. With the default,
behaviour is exactly today's. With `tiered`:

* **Classifier** (`governance/policy_change.py`): conservative; anything not provably a tightening is a loosening
  (removing a DENY/REQUIRE_APPROVAL rule, adding an ALLOW, changing a rule in place, or a reorder that lets a less
  severe rule precede a more severe one). A brute-force test over all rule lists of three rules checks that no
  permitting edit is ever called a tightening.
* **Gate** (`governance/policy_change_gate.py`, `_gate_policy_change` in `dashboard/app.py`): tightening and neutral
  edits need one administrator. A loosening edit needs a verified TOTP step-up and an APPROVED four-eyes request that
  is bound to the organization, the exact before/after rule sets and the policy version, was requested by the same
  principal who now makes the edit, was approved by a different principal (who also passed step-up), has not expired
  and is spent atomically. The edit is applied only if the policy is still at the approved version.
* **Endpoints:** `POST /api/web/policy/changes/propose`, `POST /api/web/policy/changes/{id}/approve`; the edit is then
  made with header `X-Policy-Change-Approval`. API keys can tighten but can never loosen (an approval belongs to a human
  requester).
* **No bypass:** all six mutation routes (3 REST, 3 web) call the gate and pass `expected_version`; a structural test
  fails the build if another route or module mutates policy, or if `PolicyLifecycleManager` becomes reachable from a route
  without going through the gate (`tests/test_policy_mutation_routes_are_gated.py`).
* **Not built:** break-glass for a sole-owner organisation (under `tiered` a one-person org cannot loosen policy);
  step-up through OIDC or WebAuthn (only TOTP has a verifier); rollback through the lifecycle manager (it stays unwired).
  Activating `tiered` before a break-glass decision would lock a sole-owner org out of loosening edits.

Tests: `tests/test_policy_tiered_governance_http.py` (9, real HTTP), `test_policy_change_classifier.py` (19),
`test_policy_mutation_routes_are_gated.py` (5).

## What I can build without deciding

Already done: attribution, recoverable history, tamper detection, history read endpoint, lifecycle writes history.
Available on request, independent of the choice: a dry-run "what would this policy decide" endpoint and page; a revisions
and history view in the SPA; detection of out-of-band changes (`verify_history` already flags a counter bumped with no
history row); a configuration flag that records the founder's choice and refuses to start production without one.

## What I recommend, labelled as a recommendation

Option C, with an explicit, audited break-glass for a sole-owner organisation. It removes the dangerous case (silent
loosening by one credential) without making every tightening a ceremony. The decision is yours; this recommendation is
not approval and nothing in the code assumes it.

## Acceptance tests for whichever option is approved

Forged and replayed approvals; approver equal to proposer; approval after the proposer is revoked; approval followed by
a second edit; concurrent activations (single winner); rollback that cannot be used to restore a weaker policy without the
same approval; a loosening disguised as a reorder; out-of-band SQL change detected; the same checks over the REST and
web routes.
