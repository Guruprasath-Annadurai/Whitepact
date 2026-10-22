# M13 Convergence II corrective execution handoff

**BLOCKED — ENGINEERING OR SECURITY GATES REMAIN.**
GLOBAL PRODUCTION NO-GO. M13 OPEN. No M14, merge, deployment or package release.

## Source and review boundary

Existing branch and draft PR223 are retained. No new engineering branch.
Initial commits preserved:

- `f4f7482c01edef7f737b915194abead0326f0ea4`: early unsafe production executor denial.
- `8944845a8fc42e5b8c17827c02e28334b1db5dbe`: isolated mock tracking, stronger uncertainty assertion.

New corrections:

- `4b705e05998434fdd9f4316efd76478081da7a20`: five PR224 regression/positive/Unicode cases.
- `a4cd2dfbb865e69155270eab1ca255b0917696d2`: truthful optional-sentiment mitigation comment.
- `147733cca0185fde631757d30474ade3be66f602`: CLI engine ownership on success,
  invalid input, denied read, initialization error and cancellation; five new tests.

The publication/CI transport HEAD is the commit containing this handoff. Its
exact hash/tree/parent must be taken from GitHub and CI source manifests, not
inferred from earlier receipts. No successor CI result is claimed before it runs.

Current compared owner source: PR224 cf225f87f40a466c563381149c8be0558924c2bc;
its actual direct parent is f9ea4c90a0023c83bc33e0296e10670051e550e5. Independent
report references do not override Git. No owner source is merged wholesale.

## Three-regression disposition

| Case | Owner source cf225f87 | Retained integrated source | Status |
| --- | --- | --- | --- |
| Cached sync RECONCILED after new marker | FAIL | PASS; sync denies, async refresh denies and sets FAILED | FIXED — VERIFIED by exclusion of unsafe owner hunk |
| Invalid foreign-looking legacy tracking name | FAIL | PASS; uncertainty remains and record persists | FIXED — VERIFIED by exclusion of unsafe owner hunk |
| Invalid foreign-looking v2 tracking name | FAIL | PASS; uncertainty remains and record persists | FIXED — VERIFIED by exclusion of unsafe owner hunk |
| Valid foreign registration | PASS | PASS; no unrelated tenant quarantine | Positive counterpart |
| Distinct Unicode identities | PASS | PASS; two records, no NFC alias | Negative collision counterpart |

Original protected files are unchanged. New green counterparts do not waive the
old ESRCH unlink, Unicode, schema-version, receipt-deletion or callback tests.
The actual cleanup helper rejects inconclusive inspect/plugin/daemon errors;
the callback reproducer that mocks that helper away is retained pending reviewed
test disposition. No production denial or unresolved evidence was weakened.

## Verification commands and accounting

Previously committed8944845a:341 PASS on3.11.15 and3.12.14,15 warnings each.
Convergence II runs the same341 cases plus13 related cases (354 total per
interpreter), with no exclusions or timeout changes:

```sh
PYTHONPATH=src:. <python> -m pytest tests/test_production_environment_resolution.py tests/test_isolation_fail_closed_default.py tests/test_m13_closure_production_denial.py tests/test_ws2_isolation_child_admission.py::test_production_internal_executor_refuses_without_broker tests/test_final_coverage_batch12.py tests/test_m13_closure_pr224_contracts.py scripts/engineering/reproducers/test_m13_final_owner_review.py scripts/engineering/reproducers/test_m13_convergence_tracking.py -q -o addopts='' --junitxml=<receipt> --tb=short
```

Interpreters: `/Users/ag/Whitepact/.venv/bin/python` and
`/private/tmp/whitepact-m13-closure-py312/bin/python`. Receipts:
`/private/tmp/m13-convergence2-4b705e05-py311.xml` and
`/private/tmp/m13-convergence2-4b705e05-py312.xml`. The filename identifies the
implementation test commit; later comment/report changes are not silently
relabeled as that earlier run. Final whole-source CI is required.

### CLI lifecycle correction and latest local results

The first354-case runs passed on both interpreters, but3.12 emitted19 warnings,
including four SQLite worker-thread exceptions after the event loop closed.
Investigation found that the CLI service factory initialized an in-memory
DatabaseEngine and never closed it. All16 consumers now own it with an async
context manager; a finally block closes it after normal and exceptional exits.
AST comparison established that the16 command bodies otherwise remain identical.
No authority decision or CLI result classification changed.

The five new lifecycle cases failed before the fix (close awaited zero times)
and passed after it. Existing Sovereign CLI tests plus these cases:19 PASS on3.11.
Add `tests/test_m13_cli_engine_lifecycle.py` to the command above for the latest
359-case cohort: **359 PASS,15 deprecation warnings,0 skipped on each interpreter**
(3.11:109.70s;3.12:110.73s). The earlier four thread warnings did not recur.
Receipts: `/private/tmp/m13-convergence2-cli-py311.xml` and
`/private/tmp/m13-convergence2-cli-py312.xml`. These runs tested the working-tree
source subsequently committed as147733cc; hosted exact-head proof remains separate.

Additional local results: Python SDK327 PASS on3.12; TypeScript SDK build PASS;
frontend ESLint PASS; Vitest315 PASS across35 files; TypeScript and production
Vite build PASS. No rendered browser/axe, live PostgreSQL, real TCP SDK/MCP or
native Linux execution is inferred from those results. Local socket restrictions
remain recorded, not bypassed. CLI scoped Ruff/format/mypy pass. Pinned-action
and tracked-source license checks pass. Alembic reports one head0065.

Whole-tree Ruff still fails141 diagnostics (105 F401,10 F811,8 I001,7 B017,
7 F841,2 F821,2 UP012); they have not been excluded or claimed resolved.
Directory Gitleaks with redaction reports seven findings across six unchanged
baseline files; no credential text is reproduced. Their validity remains OPEN
pending triage. The exact five-commit engineering delta scan passes with no
findings; that narrow pass does not supersede the directory result.

The downloaded ed1eb770 full-matrix baseline remains7961/84/34 on3.11 and
7962/83/34 on3.12 (PASS/FAIL/SKIP). It is not new candidate qualification.
`M13_BASELINE_FAILURE_LEDGER.json` preserves118 unique failed/skipped identities,
exact artifact/diagnostic hashes and OPEN dispositions; raw credentials are not
redistributed. New full-suite results must update, not erase, this baseline.

## Mandatory gates still open

- Full candidate3.11/3.12 matrix, all skips,80% branch coverage and exact CI artifacts.
- Real Linux authorized Docker journey, abrupt owner death, complete metadata
  loss, correct tenant ownership and safe recovery/continued quarantine. Forcing
  RESTORE_MODE proves that mode's denial, not automatic cold-restart discovery.
- PostgreSQL16 live-marker, Store A/B, cross-tenant, rollback/tombstone/revocation
  qualification and actual old-binary operational fencing. Head0065 remains;
  proposed0066 is excluded, not claimed implemented or qualified.
- Existing original runtime/recovery failures and protected-test dispositions.
- Strict-default customer17 PASS/1 BLOCKED/7 NOT_EXECUTED remains historical;
  development25 PASS is separate. Neither is current production qualification.
- MCP/SDK/Go/TypeScript/framework/browser/a11y/package exact-head checks.
- DCO39619c4b genuine author attestation, inherited Ruff debt, four authority-table
  retention/export/erasure/hold classifications, legal identity/customer scope,
  optional NLTK risk and independent Antigravity acceptance.

Local socket permission denial and the rejected escalation remain recorded;
there is no local proxy/alternate-executor bypass. Required hosted CI uses the
repository's normal, explicitly authorized test workflow, never production.
If any mandatory workflow fails, retain its actual failure, keep PR223 draft
and continue scoped corrections; a successful push is not qualification.

## Independent-review request payload

Antigravity must verify the eventual published HEAD/tree/parent itself, review
the original and new tests, reproduce the three regressions on owner source and
their absence in the integrated source, and execute the missing native/PG/root
qualification on that exact target. Do not reuse PR224's report as a final verdict.
Preserve temporary mutations and revert them; never fix production source inside
independent qualification. Return defects to Codex. No independent request is
described as delivered merely because this handoff file exists.
