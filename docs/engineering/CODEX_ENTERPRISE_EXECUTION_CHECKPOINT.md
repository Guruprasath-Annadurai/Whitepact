# Codex enterprise execution checkpoint

GLOBAL PRODUCTION NO-GO. Development/testing only; ₹0 additional cloud spend.

## Resume identity

- Active worktree: `/Users/ag/whitepact-v2-integration`
- Active branch: `codex/whitepact-v2-acceptance`
- Snapshot HEAD before V2 fixes: `f6432685b271858cd06387f1afde6170de6e8d4d`
- Snapshot TREE: `96ac46f368bd1da2dfe39463207640eed70f0d2e`
- Current discovered review base: `47551f78dc84665319dd393f3661dac8abdd03f7`
- PR195 is now merged by the owner into PR185's review branch, NOT main.
- PR196/197 remain separate open drafts, combined here with history-preserving merges.
- Owner-approved independent qualification base designation was requested; this is an engineering test branch, not a production-approved base.
- Preserved SDK parent: `9c100b2d7e0c725cb6db9d55bdae12f143e5bad1` (PR195)
- Preserved latest discovered Antigravity parent: `33454ea9c926136f5f4538a165817009be3f3b06` (PR185)
- This file records pre-batch provenance; obtain the current committed HEAD/TREE using the commands below. A file cannot embed its own final commit hash.

## Completed, do not restart

PR195 SDK/API engineering candidate has exact-head focused CI success at
`9c100b2d7e0c725cb6db9d55bdae12f143e5bad1`: Python202/version, TypeScript47/job,
package builds and real TCP/PostgreSQL journey1/version.
[CI38170022573](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38170022573).
This is not SaaS or production qualification.

PR191 includes PR192 version truth. PR193 adds actual API journey and supported
evidence listing/attestation. PR194 fixes Python configured-credential transport
exception disclosure. All remain draft; no main merge.

## Current batch

`tests/test_customer_real_approval_journey.py` adds true browser-session approval
resume over real localhost TCP and disposable migrated PostgreSQL. Policy is NOT
removed. Real user registration/login/onboarding, invited distinct admin, persisted
pending approval, missing-CSRF rejection, duplicate-human vote rejection, early
execution rejection, successful resume, one-shot replay rejection, evidence,
denial and another tenant's evidence/approval rejection are exercised.

Both scenarios passed locally: 2 passed, 0 failed, 0 skipped in18.88s.
The second scenario proves credential revocation while approval is pending,
followed by a second-human approval, yields409 and zero persisted counter effects.
CI wiring includes both new and prior live journeys. First exact-head success:
`e1bb0a116fe59f18f4f01d5be6c502af06a07597`, CI38290425643, all four jobs PASS
(Python202/version, TS47/job, actual PostgreSQL/TCP journey3/version).
This checkpoint update creates a successor; do not reuse the old run for its head.

Test-authoring failures disclosed: assumed `result` envelope corrected to actual
`execution_status`; developer key ADMIN mutation correctly rejected403; web key
revocation contract is200+`revoked`, not204; counter function is `snapshot`, not
`counter_snapshot`. These are fixture/contract corrections, not backend fixes.

## Ownership

Codex exclusive current write set: new customer journey test, dedicated
`.github/workflows/sdk-integration.yml` wiring, this checkpoint and SDK developer
documentation. No Antigravity-owned backend source edited.

Antigravity owns authority/approval enforcement, isolation, distributed revocation,
billing concurrency, core PR185 and security gates. Any failing backend invariant
requires a minimal failing test/handoff, not an uncoordinated patch.

Coordination delivered on PR185 before testing:
[6113244201](https://github.com/Guruprasath-Annadurai/Whitepact/pull/185#issuecomment-6113244201).
Delivered coordination is not an owner acknowledgment or independent approval.

## Open defects / missing contracts

1. P0 verification: true approval after credential revocation now has local proof;
   fresh exact-head CI and independent adversarial reproduction remain required.
2. P0 product gap: supported browser admin delegation/root/consent provisioning
   is not established. Journey uses explicit development root/consent/delegation
   fixtures; do not present this as complete production onboarding. Developer
   keys correctly lack ADMIN delegation-revocation permission.
3. P1 evidence detail: legacy SDK standalone bearer detail route absent. Existing
   bounded listing/attestation work. Backend contract decision remains with owner.
4. P1 Go SDK: PR197 credential fix has exact-head green CI38290712278.
   V2 fixes negative deadlines, scan/hallucination paths, malformed scan decisions
   and credential-bearing URLs. Three new regressions failed before correction.
   Real Go SDK calls against the authenticated TCP/PostgreSQL application pass,
   including missing/incorrect/revoked credentials. New successor CI remains required.

## Parallel Go lane

- Worktree `/Users/ag/whitepact-go-sdk-contract-hardening`
- Branch `codex/whitepact-go-sdk-contract-hardening`, base `cee457d8...`.
- Go worker hit a usage limit before edits; tree was checked clean.
- Native Go unavailable; Docker exists. Use a scoped official Go toolchain container
  to test only disposable local fixtures; no production or customer credentials.
- Worker made no edits before its limit; parent then took ownership, fixed only
  error-body configured-key disclosure and added dedicated Go CI. No simultaneous
  writers. PR197 is draft; other Go defects remain next-priority work.

## Exact next commands

```sh
cd /Users/ag/whitepact-real-approval-journey
git status --short --branch
git rev-parse HEAD 'HEAD^{tree}'
gh pr view 185 --repo Guruprasath-Annadurai/Whitepact --json headRefOid,state,isDraft
PYTHONPATH=src:. /private/tmp/wp-sdk-live-clean-install/bin/python -m pytest \
  tests/test_customer_real_approval_journey.py -q --no-cov --tb=short
/private/tmp/wp-sdk-integration-venv/bin/ruff check tests/test_customer_real_approval_journey.py
/private/tmp/wp-sdk-integration-venv/bin/ruff format --check tests/test_customer_real_approval_journey.py
git diff --check
```

Local TCP/PG tests require localhost permission. If a core invariant fails,
preserve failing reproduction and report to Antigravity; do not weaken it or hide
with xfail. After a safe batch, signed-off focused commit, normal branch push,
draft PR and fresh exact-head CI are authorized. No force push or main merge.

## Remaining priority / proof boundaries

Highest priority: true resumed approval and revocation/adversarial journey, then
supported evidence-detail contract and Go SDK defects. Expired approval, large
history bounds, browser workflow gaps, MCP, recovery injection, benchmark harness,
upgrade qualification and offline evaluation kit remain incomplete.

V2 fresh combined run:227 passed,0 failed,0 skipped for SDK/customer/developer API,
in-flight revocation and PostgreSQL billing regressions. TypeScript47 passed.
New customer/Go actual API file:3 passed. Go race/vet/build rerun required after
final edits. Runtime termination/revocation implementation was not changed.

P0 V2: Linux descendant/PID-race containment and real storage-outage continuity
remain PARTIAL/unqualified. Retry backoff is not proof of a bounded authority lease.
Do not promote ledger claims to independent qualification. CodeQL134/135 risk
acceptance remains BLOCKED, no alerts dismissed. Cloud spend-cap preview differs
from ordinary budget alerts; provider docs must be checked before any deployment.

Synthetic counter is NOT process-isolation proof. Local dev identity verification
and root/consent fixtures are NOT external IAM certification. No skipped test is
a pass; no SDK CI success is production clearance. Independent review remains open.

No merge, deploy, package publication, paid provisioning, Terraform, DNS/cloud
mutation, external evaluator invitation or production action. No background work
is promised after the execution session ends.
