# M13-P4 independent security acceptance handoff

Status: **BLOCKED — GLOBAL PRODUCTION NO-GO**. This document prepares acceptance; it does not execute adversarial reproductions, qualify security contracts, or enable privileged workflows.

Reviewed security reference: `57c69344961196fd89b40e8ffec65c06a1898fce`, tree `b6f3cec8666da0a9960ee2ec2a725ef81a4eb7d4`, branch `security/whitepact-m13r3-security`, draft PR #206. Product starting point: `bb87d76841c1aef7a22e53b20728c646f94c85a5`, tree `f087989a4ee36e7841624bb891241271b64415da`. The final unified candidate must be pinned after the product checkpoint; these starting hashes are not final-candidate acceptance evidence.

No M13-S4 artifact was initially present in this product checkout. Remote coordination subsequently obtained `origin/security/whitepact-m13s4-security` at commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`, tree `06f9add5d47fe5af1a7a6c45f8955da5d9b57e9a`. Its verdict, P0/P1/P2 register and Codex handoff were read with `git show`; no checkout, merge or security implementation integration occurred. The reviewed product baseline remains the specified M13-R3 reference. This candidate drift requires one explicitly reviewed unified commit before acceptance.

The S4 owner reports P0-A through P0-E closed/proven (WebAuthn concurrency, durable containment, dynamic quorum, dual-path binding and distributed tracking) and unchanged reproducers passing on PostgreSQL17. These are owner assertions, **not independent acceptance evidence**. Read-only `git diff --quiet` confirmed the S4 original-reproducer directory matches the M13-R3 reference; no S4 security tests were executed by this product preparation.

Preserved S4 remaining dispositions:

| ID | Owner disposition | Product acceptance treatment |
| --- | --- | --- |
| P1-01 | 300-second Path B lifetime flagged for founder policy decision | Pending; no product policy change |
| P1-02 | Native Linux host qualification OPEN / environment gate | BLOCKED until native Linux evidence |
| P1-03 | Linear SHA256 chain vs. Merkle terminology reconciled in docs | Preserve truthful linear-chain limitation; no invented Merkle proof |
| P2-01 | Pytest coverage overhead mitigated in CLI | Preserve existing CI coverage requirements |
| P2-02 | Recovery/containment frontend synchronization handed to Codex | UI readiness cannot enable privileged actions before qualification |

S4 explicitly retains production NO-GO and mandatory independent Codex review, founder ticket-policy ratification and native Linux isolation evidence. Its published API contracts do not independently qualify those endpoints. Security-owned claims in `docs/security/m13r3/` and the S4 branch remain claims awaiting independent verification. Preserve every open defect and the original `tests/independent_m13r2/` files.

## Separate acceptance manifest (not executed)

The executable read-only preparer is `scripts/engineering/m13p4_security_acceptance.py`:

```sh
python scripts/engineering/m13p4_security_acceptance.py --repo /absolute/clean/candidate --candidate FULL_40_CHARACTER_REVIEWED_COMMIT_SHA
```

It requires the exact current HEAD, canonical origin, clean tracked/untracked state (Git-ignored dependencies are allowed), all eight pinned original reproducer blobs and the planned R3/root-hardening files. It emits exact HEAD/tree and a planned combined pytest command on that candidate. Exit 0 means preflight passed only: acceptance stays **BLOCKED**, execution **NOT EXECUTED**. Exit 2 refuses a mismatched or dirty candidate. Its only subprocesses are bounded read-only Git inspection commands. It never executes the printed pytest command, changes security source, activates features or qualifies privileged workflows. Recheck identity and cleanliness immediately before and after any independently authorized future execution; preflight cannot prevent later filesystem changes.

Focused tests in `tests/test_m13p4_acceptance_preflight.py` cover a valid blocked plan, wrong HEAD, tracked/untracked changes, changed original blob, noncanonical origin and abbreviated SHA rejection. Mocked subprocess inspection proves no pytest/security process is launched. The current shared engineering checkout is intentionally dirty during implementation and will be refused until committed and clean.

Validation: `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_m13p4_acceptance_preflight.py -q --no-cov` passed **7 tests in 4.19s**; Ruff checks passed for the test and isolated script scope. A real read-only invocation supplying the earlier product SHA `bb87d76841c1aef7a22e53b20728c646f94c85a5` returned exit 2, `REFUSED`, because actual HEAD had advanced during checkpointing. Final clean exact-candidate execution must be recorded separately; no acceptance tests were launched.

The independent reviewer must create an isolated checkout of one reviewed unified candidate and record:

```sh
git rev-parse HEAD HEAD^{tree}
git status --porcelain=v1
git remote -v
git diff --exit-code 57c69344961196fd89b40e8ffec65c06a1898fce -- tests/independent_m13r2
git ls-tree -r HEAD tests/independent_m13r2
```

Require a clean checkout and retain the output with the candidate SHA. Compare the preserved reproducer blobs against this manifest:

| Original file under `tests/independent_m13r2/` | Git blob |
| --- | --- |
| `test_additional_readonly_probes.py` | `971e085e798854c292fac12775a7b203c88737da` |
| `test_concurrent_assertion_probe.py` | `36f566dde633a627a5cf84fbf2f1fd5593c1f43e` |
| `test_cross_worker_tracking_probe.py` | `bd44917c84faf797569befa6ac2d64604442817e` |
| `test_durable_crash_probe.py` | `8f290ff7288b6a56c73ca7370176f9205a03d34d` |
| `test_m13p_postgres_schema.py` | `a0b0953ab261079b28e516760921b5892aa71c63` |
| `test_m13p_security_contract_acceptance.py` | `99cd279b17c53f01a1f876480a4435b0504ca2e1` |
| `test_m13r_migration_roundtrip.py` | `f4d5731e9b2792b18a69e1fcfd475164ee4f0898` |
| `test_m13r_verified_containment.py` | `4d0d984d2a84e53cd503696e2e3b9d3a19ef2ede` |

The product preparation check found no difference in that directory against the security reference. This proves preservation only.

Independent acceptance must use disposable PostgreSQL and explicit security-review authorization. Follow the original fixture/environment requirements, preserve all assertions, and capture full logs, dependencies, database version, migrations, collection counts, skips, return codes, timings, and exact candidate HEAD/tree. Never run the crash/concurrency probes against a customer database or treat skipped tests as passing.

Required evidence groups remain **BLOCKED**:

| Group | Required independent evidence |
| --- | --- |
| Concurrency and replay | Original assertion-consumption reproducer; one valid winner and no replay |
| Crash durability | Original durable-crash reproducer; durable state after restart |
| Quorum | Unchanged acceptance assertions, persisted distinct approvals and anti-self-approval |
| WebAuthn | Original acceptance/replay assertions against real verification paths |
| Containment | Original cross-worker and verified-containment reproducers; durable acknowledgements |
| PostgreSQL | Original schema/migration roundtrip and lineage assertions |
| M13-R3 regressions | `tests/test_m13r3_security_regression.py` on the same candidate |
| M13-S4 | Exact independent findings and their unresolved dispositions |

All groups must independently pass on the same reviewed commit before any security qualification. Product SDK/unit/HTTP-fixture success and GitHub CI do not substitute for these groups. No product preparer sign-off is supplied here; privileged activation and milestone acceptance remain prohibited.
