# Final integration rehearsal

Disposable rehearsal. Do not merge this branch. Do not deploy it.

## Current main

`38f927229b4ea53d19a9107c78653307f5263629`

Merge base with the security stack: `cb7f479593706d841a698dafb5463f7adc744fca`

Since that base, main only adds Cursor Cloud bootstrap scripts:

- `.cursor/README.md`
- `.cursor/cloud-agent-install.sh`
- `.cursor/cloud-agent-start.sh`

## Security stack

| Step | Ref | SHA |
| --- | --- | --- |
| Agent 1 | Round 1 runtime assault commit | `4e64d01` |
| Agent 2 | `antigravity/whitepact-war8-agent2-egress-crosschallenge` | `3679891b96bde07db1218217f2ddbfb74aa23ced` |
| P2 remediation PR #152 | `cursor/whitepact-war8-p2-remediation` | `ac1df7f1810cbe7bdc7894f149e0d2bbd49951b3` |
| Agent 3 remediation PR #154 | `cursor/whitepact-war8-agent3-remediation-5eb0` | `2e0b12b96c453869f113b2d142b1396c048e0a60` |

PR #154 is the tip of that stack. This rehearsal merged that tip onto main with `git merge --no-ff`. Git reported no conflicts.

## Conflicts

Textual conflicts: none.

Files changed on both sides since the merge base: none.

New `/api/...` path strings added on both sides: none. The stack adds sovereign and audit routes. Main does not add routes in this range.

| Area | Result |
| --- | --- |
| Merge conflicts | None |
| Schema conflicts | No Alembic or `CREATE TABLE` additions on main in this range. Stack schema changes, if any, are unopposed by main. |
| Route conflicts | No shared new route paths |
| Test conflicts | No overlapping test files with main's delta |
| Workflow conflicts | `ci.yml` changes come only from the stack |
| Package conflicts | `pyproject.toml` is not in either side's delta since the merge base |
| SDK conflicts | No SDK file is in main's delta |
| Documentation conflicts | No overlapping docs with main's delta |
| Cloud conflicts | The WAR-8 stack does not contain PR #153. Cloud staging is a separate branch, `cursor/whitepact-cloud-staging-ssh-key-remediation-5eb0`. It was not merged here. |

## Safe resolution sequence

1. Leave PR #154 unchanged until Antigravity finishes the retest.
2. Leave PR #152 and PR #153 unmerged.
3. When the security retest passes, merge in this order onto the integration line, not by rewriting those PRs:
   - Agent 2 tip is already inside PR #152.
   - PR #152, then PR #154 (already stacked on #152).
   - Then current main. This rehearsal shows that order is textually clean.
4. Integrate PR #153 in a separate rehearsal against the result. Do not fold it into PR #154.

## Anticipated merge order

1. `antigravity/whitepact-war8-agent2-egress-crosschallenge` (already an ancestor of #152)
2. PR #152
3. PR #154
4. main's `.cursor` bootstrap (clean in this rehearsal)
5. PR #153 only after its own Gate 1 retest, onto the integrated tree

## Tests required after a real integration

- `tests/test_war8_runtime_assault_round1.py`
- `tests/test_war8_agent2_egress_crosschallenge.py`
- `tests/test_war8_p2_remediation.py`
- `tests/test_war8_agent3_remediation.py`
- Cloud targeted set on the cloud branch, not on this stack: `tests/test_cloud_staging_static.py`, `tests/test_m4_cloud_origin_static.py`, `tests/test_terraform_m4_validate.py`
- CI lint, mypy, and the full pytest workflow once the integrated branch targets `main`

## Requalification

- WAR-8 Agent 3 still requires the independent retest of PR #154. This rehearsal does not replace it.
- Gate 1 still requires its own retest of PR #153. This branch does not apply Terraform.
- Package identity is unchanged by the stack. A rename is a separate owner decision.
- Gate 2 (Cloudflare, DNS, R2) is not in this merge and is not authorized.
