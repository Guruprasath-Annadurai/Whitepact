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
