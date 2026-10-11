# Antigravity handoff — Option B authority tools and the follow-on hardening

From: Claude (Principal Engineering Lead). To: Antigravity (independent auditor). You are an AI auditor; your
review does not replace a human reviewer and does not satisfy OSPS-QA-07.01. Do not merge #180–#183. Do not
rewrite this branch.

Branch: `claude/whitepact-isolation-failclosed-linux-recovery`. Exact SHAs for the candidate are in the final
report; verify `git rev-parse HEAD^{tree}` equals the tree stated there before you start.

## Audit first (required by the founder before acceptance)
**REC-35 — four read-only authority tools.** Read `docs/launch/AUTHORITY_READ_PATH.md` (requirements table,
limitations, your attack plan). Code: `src/responsibleai/mcp/authority_tools.py`, the `AUTHORITY_TOOL_NAMES` branch in
`_call_tool` and `_call_authority_tool` in `mcp/server.py`, `advertised_tool_defs(authority=)`. Tests:
`tests/test_mcp_authority_tools.py` (42; the Postgres test needs `scripts/test-postgres.sh`).
Tell us: any cross-tenant read, any state change, any role/rate-limit bypass, any false claim in a descriptor, any
table the service reads that the documented grant list omits. Do not expand the tool list.

## Then audit
| Item | Where | Ask |
|---|---|---|
| REC-28 plan-scaled route limits | `dashboard/plan_rate_limiter.py` (`scaled_route_limit`, `OrgPlanDirectory`), `_plan_scaled` in `dashboard/app.py`; `tests/test_plan_scaled_route_limits.py` | Is `max(base, plan budget)` safe? Can a downgraded org keep a scaled limit (directory is refreshed per request)? Is 1,200/min a defensible ceiling? NB: in-process ASGI tests share `request.state` and never evaluate the route limit after the first call; the test uses real uvicorn. |
| REC-37 billing retry | `db/billing_repository.py` (`is_reclaimable`, `_reclaim`), `db/paddle_billing_repository.py` | Race, replay and tenant-reassignment: can a reclaimed Paddle event bypass the cross-tenant checks? |
| REC-38 Redis outage | `plan_rate_limiter.py`, `_build_limiter` | Is per-replica degradation acceptable for the authentication path? |
| REC-36 witness disclosure | `docs/launch/WITNESS_DISCLOSURE_RECOMMENDATION.md` | Challenge the analysis (`chain_sequence` as activity count; non-exposure finding). |
| Policy drafts | `docs/assurance/POLICY_ADOPTION_CHECKLIST.md` | Re-verify each claim against GitHub config and workflows. |
| Hostname and directory prep | `docs/distribution/MCP_HOSTNAME_RUNBOOK.md`, `DIRECTORY_REQUIREMENTS_AND_REVIEWER_TENANT.md` | Check the runbook's claims against code (registration allow-list is ChatGPT-only). |

## Known open items you should not "discover" as new
Listed in `docs/launch/STATUS_BY_CATEGORY.md` sections 4–7. In particular: DCO failure on two of my commits
(awaiting founder), CodeQL 134/135 open, PR #183 conflicts in `policy_repository.py` and `test_policy_history.py`,
OIDC/WebAuthn step-up unsupported, no external evidence anchor, authority tools not yet on a dedicated DB role.

## What would change the verdict
Anything in the first table that you can reproduce moves REC-35 to FAILED. Please state what you ran, on which SHA,
and what you did not test.
