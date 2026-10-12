# Codex enterprise execution checkpoint

GLOBAL PRODUCTION NO-GO. Development/testing only; ₹0 additional cloud spend.

## Resume identity

- Active worktree: `/Users/ag/whitepact-real-approval-journey`
- Active branch: `codex/whitepact-real-approval-journey`
- Snapshot HEAD before this test/checkpoint batch: `cee457d8ea7460881d88221ac0df4f29ccfb93ff`
- Snapshot TREE: `bdbb050681c6586d5bc0cdf0dc9791735202f018`
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
CI wiring includes both new and prior live journeys; fresh CI remains pending
until actually completed on the new commit.

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
4. P1 confirmed Go SDK: reflected credential HTTP-error disclosure; Scan and
   hallucination helper paths do not match actual backend; null/empty successful
   responses falsely yield safe zero-value scan; negative timeout disables deadline.
   Read-only findings, NOT fixed or runtime-tested yet.

## Parallel Go lane

- Worktree `/Users/ag/whitepact-go-sdk-contract-hardening`
- Branch `codex/whitepact-go-sdk-contract-hardening`, base `cee457d8...`.
- Go worker hit a usage limit before edits; tree was checked clean.
- Native Go unavailable; Docker exists. Use a scoped official Go toolchain container
  to test only disposable local fixtures; no production or customer credentials.
- Worker owns only sdk/go; do not allow concurrent writers to its worktree.

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

Synthetic counter is NOT process-isolation proof. Local dev identity verification
and root/consent fixtures are NOT external IAM certification. No skipped test is
a pass; no SDK CI success is production clearance. Independent review remains open.

No merge, deploy, package publication, paid provisioning, Terraform, DNS/cloud
mutation, external evaluator invitation or production action. No background work
is promised after the execution session ends.
