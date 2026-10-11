# Current issue register — by founder category

Candidate: branch `claude/whitepact-isolation-failclosed-linux-recovery` (PR #180, draft). The exact commit
and tree are recorded in section 7 and updated on every push. Item numbers refer to
`ENTERPRISE_RECOVERY_ISSUE_REGISTER.md`. **No production launch, release, marketplace submission, DNS change
or spending is authorized or has occurred.** A result is "verified" only if the qualifying test ran on the
stated SHA; old CI never qualifies a new SHA.

## 1. Completed and verified
Verified by a CI run on a named earlier SHA, or by a direct measurement recorded in the register. **Nothing in
this list is claimed for the current head until its CI results are recorded in the final report.**

| Item | Evidence |
|---|---|
| REC-02 isolation fix | CI verified on `d8db970` (earlier SHA) |
| REC-01 isolation (earlier `0o444` form) | CI verified; the ACL form that replaced it is in section 2 |
| Release provenance for v1.2.6 | `gh attestation verify` run and recorded (supply-chain evidence doc) |
| Plan-limiter / route-limiter outage behaviour characterised | measured `[500,500,500]` before REC-38 |

## 2. Implemented, awaiting CI on the current head
REC-01 (ACL form), 11, 12, 13, 14, 17, 18, 19, 20, 21, 22, 23, 24, 26, 27, 30, 31, 32, 33, 34,
**28 (plan-scaled route limits)**, **37 (billing webhook retry)**, **38 (Redis outage degradation)**,
**35 (authority tools, development only)**. Each has local tests; each test that guards a fix was shown to
fail with the fix removed where the register says so (REC-28, 37, 38, 30).

## 3. Awaiting independent audit
| Item | What Antigravity must do |
|---|---|
| **REC-35 authority read path** | Required before acceptance (founder decision 3). Attack plan in `AUTHORITY_READ_PATH.md`. |
| REC-12 host-side fixture exception | Disclosed, not independently reviewed. |
| REC-30 step-up (TOTP-only) | Independent review pending. |
| REC-31 policy-history verification | Independent review pending. |
| REC-28 ENTERPRISE ceiling (1,200/min/route) | Confirm the number is acceptable; it is a proposal. |
| REC-37 billing retry | Review the compare-and-swap and the Paddle conflict path. |
| REC-38 degraded limiter | Review the weaker-while-degraded trade-off. |
| PR #183 reconciliation | Still conflicts with this branch in `db/policy_repository.py` and `tests/test_policy_history.py` (re-checked with `git merge-tree` against `85a992aa`). PR #183 is Antigravity-owned; not rewritten. |

## 4. Failed
| Item | Detail |
|---|---|
| **DCO check on `2b3e1811` and `3fb095fc`** | My two commits lacked `Signed-off-by`. Fixing needs a history rewrite of those two commits and a force-push, which the permission classifier refused; **awaiting the founder's decision** (see section 5). Later commits are signed. |
| `CodeQL` (code-scanning aggregate) | Fails only because alerts 134/135 are open (REC-36). All three `CodeQL analysis` jobs pass. |
| Python 3.11/3.12 CI on the current head | **Not failed — pending.** Listed here only so it is not forgotten. |

## 5. Requiring founder action
1. **DCO**: allow `git rebase --exec 'git commit --amend --no-edit -s'` on `2b3e1811` and `3fb095fc` plus
   `git push --force-with-lease` to this review branch — or approve an exact-SHA DCO exception (the workflow
   supports one; it is not a sign-off).
2. **CodeQL 134/135** (REC-36): 134 dismissible; 135 stays open pending the v2 opaque witness reference.
3. **Branch protection**: make CodeQL, dependency review and the reproducible build required; decide on a
   required reviewer (`POLICY_ADOPTION_CHECKLIST.md`).
4. **Policy adoption** of the four drafts after reading the corrections; confirm response targets.
5. **REC-25** policy-governance activation (tiered option C is built but off).
6. **`mcp.whitepact.com`**: every step in `MCP_HOSTNAME_RUNBOOK.md` marked FOUNDER GO; infrastructure spend.
7. **Directories**: identity verification, paid-plan activation, privacy policy/terms, verified contact, accepting
   vendor terms, the submission itself (`DIRECTORY_REQUIREMENTS_AND_REVIEWER_TENANT.md`).
8. **Second human reviewer** (`SECOND_MAINTAINER_PROPOSAL.md`); no administrator access for Scorecard.
9. **Claude/Grok OAuth callbacks**: approve extending dynamic client registration after the exact vendor values
   are verified.
10. **ENTERPRISE route ceiling** value; **key-rotation cadence**; **support-window** commitment.

## 6. Blocked by infrastructure
| Item | Blocker |
|---|---|
| Real ChatGPT / Claude / Grok compatibility tests | no endpoint on an owned domain; no test access |
| REC-29 1,000-concurrency capacity | needs a production-shaped environment and load source; local single-process figures only |
| External evidence anchoring (REC-13) | no object store / immutable log provisioned |
| Go SDK validation | no Go toolchain in the build environment |
| Live Stripe / Paddle sandbox | no sandbox credentials or public webhook URL |
| Hosted-service availability claims | no staging deployment |

## 7. Unimplemented (known)
OIDC and WebAuthn step-up (explicitly refused, not faked) · witness record v2 with opaque tenant reference ·
per-tool OAuth scopes · production read-only database role wiring for the authority tools · cancellation of
in-flight tool executions on revocation (revocation stops new admissions only) · Stripe out-of-order event
handling · alerting on `degraded_events` · fuzzing in CI · container-image scanning in CI · npm audit in CI ·
Smithery/Glama listing review · website identity work (Codex-owned handoff) · enterprise procurement pack refresh ·
required-check hardening.

## 8. Candidate identity (updated at each push)
See the final report for the exact commit and tree SHA, and the CI table for that SHA.
