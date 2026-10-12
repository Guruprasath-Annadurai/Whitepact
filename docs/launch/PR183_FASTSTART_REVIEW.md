# Review of PR #183 (FastStart V1) — integration concerns

Reviewer: Claude (backend/security). Reviewed head: `5e4e7feb138304fc93d1427699654d0fa8fc3fbc`. Antigravity owns the PR;
nothing here changes it. Findings are stated so the owner can fold them into the remediation. Measurements are mine,
on one Apple M4 over a home connection, and are not a substitute for Antigravity's own runs.

## Measured (Target A–E script from the PR, run unmodified, uv 0.x, `--no-cache` cold)

| Target | Threshold | Python 3.12.13 | Python 3.11.15 |
| --- | --- | --- | --- |
| A cold core install | ≤ 10.0 s | **14.59 s — FAIL** | **11.72 s — FAIL** |
| B warm core install | ≤ 2.0 s | 0.55 s | 0.40 s |
| C cold `[dashboard]` | ≤ 30.0 s | 12.19 s | 11.25 s |
| C warm `[dashboard]` | ≤ 30.0 s | 0.28 s | 0.29 s |
| D `faststart --json` | ≤ 60 s | 0.74 s | 0.87 s |
| E venv + install + faststart | ≤ 300 s | 1.52 s | 1.66 s |

The script printed `Target A … -> FAIL` and then ended with **"All targets passed rigorously and demonstrably."**,
exit code 0. A failed target must fail the run. Cold install is network-bound; the number varies by connection and
mirror, but it is a measurement of the target as written and it fails twice. Do not redefine A after the fact.
`pip` was not measured at all (the directive asks for pip and uv), and each interpreter must be measured on its own.

## Findings

| ID | Severity | Finding | Where |
| --- | --- | --- | --- |
| FS-01 | P1 (claim) | The benchmark reports success unconditionally and exits 0 when a target fails. | `scripts/benchmark_faststart_targets.py`, final `print` |
| FS-02 | P1 (claim) | The "approval" step is a hard-coded string: `execution_grant_id = "grant-faststart-human-approved-101"`, `decision="APPROVED"`, note "Human supervisor signed off". No human, no approval record, no grant issued, no nonce. The step is named `APPROVE_AND_EXECUTE` but nothing executes. | `faststart.py`, "Step 4" |
| FS-03 | P1 (claim) | "REVOKE" is a second `evaluate()` call with an empty `AuthorityContext` passed in by the caller. No revocation state, epoch or credential is involved. It shows that an empty authority denies, which is true and useful, but it is not revocation. | `faststart.py`, "Step 5" |
| FS-04 | P1 (claim) | "VERIFY_EVIDENCE" builds one record locally, hashes it, checks `len(hash) == 64`, and the report sets `verified=True` unconditionally. Nothing is stored, chained, recomputed or checked by an independent verifier. The decision label is `SEALED`. | `faststart.py`, "Step 6"; `FastStartReport.verified` |
| FS-05 | P1 (claim) | The module docstring says "fully isolated, zero-network, cryptographically verifiable". It runs in-process, with no container and no tool executed; "isolated" is false and "cryptographically verifiable" is not shown. | `faststart.py` docstring |
| FS-06 | P2 | Target D is titled "First Genuinely Protected Agent Action", and Target E lists "APPROVE -> EXECUTE". Both measure the simulation above. | benchmark script |
| FS-07 | P2 | Only `sys.executable` is benchmarked; Python 3.11 and 3.12 need separate, labelled runs. | benchmark script |

## What is sound

The ALLOW / DENY (policy) / DENY (not granted) / REQUIRE_APPROVAL decisions come from the real
`WhitePactRuntimeGateway.evaluate()` with a real `Policy` and `AuthorityContext`; those four steps are genuine policy
decisions, in-process, in about a millisecond. That is a legitimate "first local policy decision" measurement.

## Recommended labelling (no behaviour change needed to be honest)

1. Rename steps to what they show: `ALLOW`, `DENY_BY_POLICY`, `DENY_NOT_GRANTED`, `REQUIRE_APPROVAL`,
   `SIMULATED_APPROVAL`, `EMPTY_AUTHORITY_DENIES`, `EVIDENCE_HASH_COMPUTED`.
2. Mark the report `simulation: true`, drop `verified`, and add `executed_tool: false`, `isolated: false`.
3. Say "no tool was executed and no container was used" in the CLI output.
4. Make the benchmark exit non-zero when any target fails and print only what failed.
5. If a real protected-execution quick demonstration is wanted, it needs Docker and the `Dockerfile.isolation` image
   (`tests/test_isolation_real_tool_e2e.py` shows the call); it cannot meet a 60-second cold-install-plus-run target
   without a pre-pulled image, and should be a separate, clearly named command.

## Integration note

Both branches edit `tests/test_policy_history.py`. #183 carries deterministic tamper mutations; this branch has since
changed one assertion (an org whose only history row was deleted is now reported invalid) and added tests. Expect a
one-hunk conflict; keep this branch's assertion.
