# M13 integrated engineering qualification — continuation receipt

## Recommendation

**BLOCKED — ENGINEERING OR SECURITY GATES REMAIN.**

M13 is not closed, independently qualified or production-ready. This receipt
records completed corrections and remaining failures; it is not the completed
mandatory integrated acceptance matrix. GLOBAL PRODUCTION NO-GO. No M14.

## Implementation provenance

- Integration branch: `codex/whitepact-m13-final-convergence`, PR223 OPEN/DRAFT.
- Local HEAD: `8944845a8fc42e5b8c17827c02e28334b1db5dbe`.
- Committed tree: `2e02e123971b22d2d700339a84de7f5e5edb897a`.
- Parent: `f4f7482c01edef7f737b915194abead0326f0ea4`.
- Starting remote: `ed1eb7705b69bef30fbbacb3717219ea995f41a6`, tree
  `a576376ddbc46843f7cd90cba6ac057cc7d1a823`.
- PR224 freshly verified OPEN/DRAFT at
  `f9ea4c90a0023c83bc33e0296e10670051e550e5`, base
  `39461fec883aeb18a14f486ba9d65a2c02b20d06`.
- PR223 base: `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`.

No full cherry-pick, merge, rebase or history rewrite. The two new local commits
have current sign-offs; they do not resolve historical commit39619c4b's missing
attestation. Neither new commit was pushed during this continuation.

Clean detached verification checkout:
`/private/tmp/whitepact-m13-f4f7482-retest` (the directory name is historical;
its verified HEAD is the full 8944845a SHA above). Its tracked tree is clean.
The integration checkout remains dirty with explicitly excluded, unfinished
work; its filesystem must not be described as the committed candidate.

## Confirmed corrections

### Early production isolation rejection — committed f4f7482c

`InternalToolExecutor.execute` rejects a missing broker in production before
restore inspection or permit admission. Existing later isolation and recovery
guards remain. No authority, grant validation, revocation, production synthetic
fixture exception or successful execution path is introduced.

Unchanged environment/default-isolation tests on clean starting source:
255 PASS / 7 FAIL. All seven failures returned restore quarantine before the
required isolation-configuration error. Integrated counterpart: 262 PASS on
Python3.11 and 3.12. Added denial-only regression verifies no admission call,
no dispatch and no permit consumption. With the existing WS2 production-denial
case: 264 PASS per interpreter. The f4f7482c committed clean checkout reproduced
264 PASS on each interpreter (5.04s / 5.12s).

### Mock tracking isolation — committed 8944845a

`tests/test_final_coverage_batch12.py` mocked-container cases reused org-1 and
the shared temporary tracking directory. Two-case reproduction failed because
existing uncertainty correctly denied registration before the timeout path.
No causal flakiness claim is needed: the observed result was revocation denial,
not a missed clock deadline. Production tracking files were not removed.

A fixture isolates only four mocked-container tests, restoring the previous
singleton afterward. Original assertions remain; timeout additionally requires
UNRESOLVED. A new regression verifies outside corrupt tracking and the original
singleton survive fixture setup/teardown. No global security fixture changes.

Before the extra preservation test was added, the full original76-case module
passed on both interpreters: 76 PASS / 15 warnings (103.24s / 88.90s). The new
preservation case passed separately on both (within a three-case run on3.11,
one-case run on3.12). Clean final-commit combined replay is recorded below.

### Receipt retry cleanup — working-tree only

The prior unfinished immutable-CID/late-receipt fix was preserved. Its five
new regressions fail5/5 on clean ed1eb770 and pass on the pending source.
A further deterministic regression reproduced private receipt storage remaining
after a successful same-worker containment retry. The callback now disposes
receipt storage only after positive cleanup; disposal is idempotent if execute's
finally subsequently runs. Uncertain outcomes retain private receipt association.

Combined component contracts: 16 PASS on3.11 and3.12 (5.74s / 4.78s). These
are controlled process/cleanup seams, not native Docker receipts. The source
and tests remain uncommitted pending broader conflict review. No claim that
the committed 8944845a tree contains this runtime fix.

### NLTK documentation accuracy — working-tree only

The pyproject comment incorrectly claimed scoring called nltk.download and
could not reach data-loading APIs. `_get_vader` actually uses a provisioned
analyzer and does not download during scoring. The comment now states that
mitigation narrowly and does not imply advisory risk acceptance or complete
package unreachability. Optional dependency declarations are unchanged.
Scoring/gender tests: 62 PASS on3.11 (2.87s). NLTK is absent from the tested
default interpreter; this does not qualify the optional installed extra or
resolve GHSA-8mgp-746c-j5xp. Current advisory/installed-extra assessment remains
open. No dependency was removed or scan exclusion introduced.

## PR224 hunk disposition

| Change | Disposition |
| --- | --- |
| Final Python3.11 syntax | No syntax hunk needed in the final compared source; don't import an earlier broken intermediate commit |
| Early production same-process denial | Narrow semantic port in f4f7482c; no production synthetic-host exemption |
| Cached RECONCILED sync admission | REJECT: unchanged late-marker counterexample fails on PR224; retain live asynchronous DB authority |
| Extra sync guard after async verification | Not imported: depends on rejected cached-authority semantics |
| Filename-based foreign-record suppression | REJECT: invalid foreign-looking legacy/v2 records are ignored on PR224 |
| Container callback extra inspect | Not imported: requires immutable-identity and authoritative-error qualification, not mutable-name/status acceptance |
| Dead-worker retention comment | Already implemented in baseline; original unlink assertion remains a documented conflict |
| Unicode assertion reversal | Not imported; preserve original security evidence and obtain explicit disposition |
| JSON-only H1 file count | Not imported pending protected-test review |
| PostgreSQL reproducer registry isolation | Not imported into the protected original; separately reproduce and review fixture changes |
| Owner reports | Reference evidence only, never independently executed acceptance |

PR224's unchanged owner-review test module independently returned3 PASS/1 FAIL
on the previous continuation; the added corrupt-name probes returned1 PASS/2 FAIL.
The primary worktree's preserved PR224 contracts plus late-cleanup and original
review tests passed13/13 before the new retry regression. The 16-case replay
above includes its correction. No owner branch or protected original was edited.

## Authoritative full-suite baseline

Downloaded actual shard JUnit, plan and aggregate artifacts from
[39297637229](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297637229).
All16 plans match ed1eb770 and its tree; shard indexes0–7 exist per interpreter.

| Interpreter | PASS | FAIL | ERROR | SKIP | Total | Branch |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|3.11|7961|84|0|34|8079|80.787671%|
|3.12|7962|83|0|34|8079|81.061644%|

`M13_BASELINE_FAILURE_LEDGER.json` retains118 unique nonpassing test identities,
stable IDs, interpreter outcomes, JUnit SHA256 and diagnostic hashes. Raw
diagnostics stay in downloaded artifacts to avoid redistributing credentials.
All unresolved records default OPEN_NO_WAIVER; first-bad commits and unreviewed
root causes are not invented. Artifacts are under
`/private/tmp/whitepact-m13-closure-ci-39297637229`.

These are predecessor CI results, not a fresh full matrix for8944845a. Do not
subtract focused fixes to manufacture a new full-suite pass/fail count.

## Runtime, recovery and migration

Original unchanged runtime cohort locally: **52 PASS / 3 FAIL**,21.00s.

1. Callback-plugin test still fails. It replaces `_remove_containers` with a
   successful no-op, thereby bypassing the actual inspect/error checker; retain
   the original and obtain reviewed disposition rather than claim it passes.
2. ESRCH original expects deletion of dead-worker tracking; preserving possible
   surviving workload evidence is mandatory. No unlink relaxation was made.
3. PostgreSQL nonce case cannot connect in this sandbox (PermissionError on
   localhost sockets; no private socket instance). Record BLOCKED, not pass.

Broader pending runtime slice:34 PASS/4 FAIL. The four originals expect early
receipt deletion or two-element CID-plus-name cleanup. They remain unchanged
and unwaived; the safer counterpart tests do not erase those failures.

Native Linux/Docker, cold restart after all metadata loss, PostgreSQL16 recovery,
root/WebAuthn and old-binary operational fencing were NOT freshly qualified in
this continuation. Local socket-test escalation was previously rejected by
auto-review; no workaround or indirect executor was used to bypass it.

Clean committed8944845a `alembic heads` reports **0065 (head)**. This is graph
verification, not a successful PostgreSQL upgrade. The unfinished0066 journal,
new containment repository and engine metadata remain excluded from commits.
They require integration, concurrency, classification and real-PG review.

## Customer journey and other qualification

Strict-default17 PASS/1 BLOCKED/7 NOT_EXECUTED and development25 PASS are
historical receipts only. No new customer-journey success is asserted. Declared
account/authenticator qualification is not legal identity proofing. The default
reusable-credential assurance gate must not be weakened to reach stage17.
Real provider evidence and founder acceptance scope remain unresolved.

SDK/MCP/product totals from earlier continuations are not transferred to this
new commit. New exact-head SDK/Go/TypeScript/package/framework/browser/axe/full
coverage/native and CI qualification remains required.

## Static checks and exact-head CI

- Focused Ruff check/format: PASS on five changed/new source/test files.
- Mypy execution.py + container_backend.py: PASS,2 files, follow-imports=silent;
  not a fresh whole-project mypy proof.
- Pinned Actions check: PASS. Tracked first-party license header check: PASS.
- git diff --check: PASS. No global lint rule/coverage/test-discovery exclusions.
- Whole-tree inherited Ruff debt remains open; no blanket format or exclusion.

Fresh GitHub inspection of ed1eb770:

| Workflow | Result | Run |
| --- | --- | --- |
|CodeQL|PASS|39297638898|
|Security Scan|PASS|39297636709|
|Gitleaks|PASS|39297636735|
|SDK/Package|PASS|39297637319|
|Product|PASS|39297611098|
|Sovereign Development|PASS|39297610803|
|Full Python matrix|FAIL|39297637229|
|Runtime Review|FAIL|39297610672|
|Independent Integration|FAIL|39297610725|
|Targeted Diagnosis|FAIL|39297605013|

Run URLs use
`https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/<run>`.
No GitHub Actions result exists for the two unpushed commits. No green result
above is represented as successor CI or independent Antigravity qualification.

## Human decisions and remaining engineering

- Genuine contributor attestation for39619c4b; no forged retroactive signoff.
- Protected dead-worker/Unicode/migration/receipt/callback test dispositions;
  preserve original blobs and substantive security assertions.
- Legal retention/export/erasure/hold classifications for committed tables:
  authority_containment_records, authority_recovery_requests,
  authority_recovery_votes, authority_step_up_challenges. All carry sensitive
  authority/actor/audit associations; classification requires approved policy,
  not a unilateral retention or deletion rule. The proposed runtime journal
  adds a fifth classification requirement only if it is integrated.
- Default customer acceptance scope versus separate identity-provider proof;
  BASIC_VERIFIED must not silently become IDENTITY_VERIFIED.
- Old-binary operational compatibility disposition and actual environment role
  inventory/retirement proof, not just downgrade refusal.
- Optional NLTK exposure assessment and authorized residual-risk decision.
- Complete per-failure reproduction/classification, remaining implementation
  corrections, real native/recovery qualification and full successor CI.
- Antigravity independent review on the eventual exact frozen source: PENDING.

No final freeze is claimed. Existing work is preserved. No main merge,
deployment, public restore activation, package publication, paid infrastructure,
DNS/cloud mutation, force-push or M14 execution occurred.

## Clean successor replay

Verified clean8944845a: **341 PASS / zero FAIL / zero ERROR / zero SKIP** on
Python3.11.15 (75.77s) and Python3.12.14 (80.13s),15 retained deprecation
warnings per run. These are the same341 unique cases on two interpreters, not
682 different product features or tests. Tracked status remained clean.

```sh
PYTHONPATH=src:. <python> -m pytest tests/test_production_environment_resolution.py tests/test_isolation_fail_closed_default.py tests/test_m13_closure_production_denial.py tests/test_ws2_isolation_child_admission.py::test_production_internal_executor_refuses_without_broker tests/test_final_coverage_batch12.py -q -o addopts='' --tb=short
```

Interpreters: `/Users/ag/Whitepact/.venv/bin/python` and
`/private/tmp/whitepact-m13-closure-py312/bin/python`.
The latter was created independently after the old consumer-only environment
failed collection without FastAPI. An offline dependency attempt was unavailable;
normal reviewed dependency installation populated the new environment. No shared
consumer environment or dependency floor was altered. The initial collection
ERROR is retained as setup failure, not product evidence or a skipped case.

No full-platform acceptance is implied by this focused cohort.

## Convergence II — superseding execution record

The preceding sections are the preserved earlier receipt, not the current
publication state. Original commits f4f7482c and8944845a remain ancestors.
New regression commit: `4b705e05998434fdd9f4316efd76478081da7a20`, tree
`f5aabbf151bc41907746cbda1815017959b31f33`.
Sentiment-comment correction: `a4cd2dfbb865e69155270eab1ca255b0917696d2`.
It changes comments only; the optional dependency and security requirements stay.

Remote refresh found PR224 advanced from f9ea4c90 to
`cf225f87f40a466c563381149c8be0558924c2bc`. Its delta is one report and two
new reproducer files; production code is unchanged. Fresh five-case replay on
that exact owner source: **3 FAIL / 2 PASS in3.42s**. The failures are the cached
sync gate and two corrupt-filename suppressions. These are not newly discovered
defects in the retained PR223 source: the safe integration rejects those unsafe
owner hunks, keeps live verification and commits the additive counterexamples.
The integrated13-case scope passed on both interpreters (14.82s / 6.96s before
the final source-only replay;3.11 final replay5.22s). Original tests remain intact.

The cached-readiness test now challenges both sync and async admission after a
committed marker and requires FAILED state. The Unicode counterpart requires
two exact tenant identities and two distinct records, without changing the old
NFC-equivalence assertion or silently waiving its conflict.

The unfinished0066 journal, receipt experiments, associated tests and original
migration report are preserved in Git stash
`12b87ea5f182ea5a0466131571a702316451d8f1`. This is a recoverable source snapshot,
not deletion of runtime tracking or security evidence. Its files are deliberately
excluded from the reviewable0065 candidate. The verified sentiment comment was
separately reapplied and committed; the stash remains intact. No branch restart.

PR224's new report is not accepted as final qualification. It cites unavailable
corrective/base hashes that differ from the actual Git objects, identifies
docker_backend.py instead of the actual container_backend.py, and describes
total-metadata recovery using an explicitly forced restore-mode gate. That test
does not prove automatic detection of an arbitrary restart with lost metadata
and an otherwise READY authority store. Its Docker cases construct tracking
fixtures and use an unpinned general Python image, not an approved customer
authorization-to-isolated-execution journey. These limitations require corrected
independent evidence, not silent adoption of QUALIFIED language or a new claim
that source tests were executed by Codex.

Final candidate commit/tree/parent are recorded by exact-head CI plans and the
publication receipt, because a committed report cannot contain its own future
Git hash. All uncompleted mandatory gates remain OPEN. The draft push and CI
execution must not be described as milestone acceptance. Detailed publication,
command and remaining-work handoff: `M13_FINAL_CORRECTIVE_EXECUTION_HANDOFF.md`.

### Additional correction: Sovereign CLI database lifecycle

Commit `147733cca0185fde631757d30474ade3be66f602`, tree
`3f1bb0dd2891bb2f6b179587c46d8103429f6cb6`, closes CLI-owned SQLite engines on
all exits. The354-case3.12 run exposed four worker-thread/event-loop warnings.
Five lifecycle reproducers failed before the fix and passed after it. All16
commands use the same context-managed factory; their operation bodies are
AST-equivalent apart from ownership. Existing CLI plus regression scope:19 PASS.
Expanded359-case scope:359 PASS/15 deprecation warnings/0 skips on each of
Python3.11.15 (109.70s) and3.12.14 (110.73s). The thread warnings did not recur.
These local working-tree receipts are not a substitute for final exact-head CI.

Python SDK327 PASS; TypeScript SDK build PASS; frontend lint,315 Vitest, TypeScript
and production build PASS. Local browser/native/realTCP/PG tests remain blocked
where permissions prevent them; hosted authorized workflows must execute them.
Scoped CLI Ruff/format/mypy, action pins and tracked-source license checks PASS.
Alembic single head0065. Whole-tree Ruff remains FAIL (141 diagnostics).
Redacted full-directory Gitleaks remains OPEN (seven findings, six unchanged
baseline files); engineering-delta scan PASS (five commits, no findings).
No security finding has been hidden by an allowlist or a narrow scan label.
