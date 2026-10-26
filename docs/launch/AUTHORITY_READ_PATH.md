# Authority read path (Option B) — design, evidence and Antigravity audit request

Status: **implemented for development; NOT approved for public deployment.** Founder decision 3
approved development and testing only. Antigravity must audit this path independently before it is
accepted. The tool list must not be expanded.

## What exists

Four tools, advertised only on a hosted, tenant-scoped connection whose governance services are
wired (`advertised_tool_defs(hosted=True, authority=True)`); stdio and ungoverned hosted
connections never see them.

| Tool | Allowed roles | Limit / min / org | Returns | Never returns |
|---|---|---|---|---|
| `whitepact_policy_status` | OWNER, ADMIN, SECURITY_ADMIN, ANALYST | 30 | policy version, rule count, count per effect, history-chain validity | rule ids, reason codes, targets, rule bodies |
| `whitepact_simulate_policy` | OWNER, ADMIN, SECURITY_ADMIN, ANALYST | 60 | policy-only effect + reason code for one `(action_type, target[, risk_tier])`, plus an explicit list of what was **not** evaluated | an authorization, a grant, any record of the probe |
| `whitepact_list_pending_approvals` | OWNER, ADMIN, SECURITY_ADMIN, APPROVER | 30 | id, action type, risk tier, reason codes, requested/expires, required approvals; page ≤ 50, cursor ≤ 150 | targets, arguments, requester identity, digests |
| `whitepact_verify_evidence` | OWNER, ADMIN, SECURITY_ADMIN, ANALYST, AUDITOR | 6 | VALID / INVALID / INCOMPLETE / UNKNOWN, head sequence + hash, optional match against a head the caller recorded earlier | evidence payloads or entries |

Code: `src/responsibleai/mcp/authority_tools.py`; integration: `_call_authority_tool` and the
`AUTHORITY_TOOL_NAMES` branch in `_call_tool` (`mcp/server.py`).

## How each founder requirement is met

| Requirement | Mechanism | Test |
|---|---|---|
| Authenticate every request | The tools sit behind the same hosted credential verification as every tool; no handler runs without an `OrgContext`. | `test_legacy_and_unscoped_credentials_are_refused` |
| Org from trusted credentials | The tenant is `ctx.org_id`. No schema has an org/tenant argument; extra arguments are rejected (`additionalProperties:false` **and** server-side). | `test_exactly_four_tools_…`, `test_invalid_or_tenant_override_arguments_are_rejected` |
| Roles / entitlements | Explicit per-tool allow-lists; any role not named (including future ones) is refused. Plan and monthly quota are enforced before the branch, exactly as for every tool. | `test_role_matrix_is_explicit_default_deny` |
| Tenant-only data | Every repository call is keyed by `ctx.org_id`. | `test_policy_tools_see_only_the_callers_tenant`, `test_pending_approvals_are_tenant_scoped…`, `test_evidence_verification_…` |
| Minimal disclosure / no unrestricted policy enumeration | `policy_status` returns counts only; `simulate` returns one effect + reason code per probe and is rate limited (60/min). Rule ids and bodies are never returned. | same tests; `flat` assertions |
| No sensitive approval args / evidence payloads | Output is an explicit allow-list of fields; asserted by exact key set. | `test_pending_approvals_…` |
| Canonical evaluator | `Policy.evaluate` and `classify_action_risk`; no second implementation. | `test_simulation_matches_the_canonical_evaluator` |
| Policy-only vs full authorization | Every simulation response says `is_authorization:false`, `execution_grant_issued:false`, `recorded:false` and lists the layers not evaluated. | `test_simulation_is_labelled_policy_only…` |
| Internal vs external integrity | `externally_anchored:false`, `scope:"internal_chain_consistency"`, and a limitation sentence in every verification response. | `test_evidence_verification_reports_scope…`, `test_a_tampered_chain_is_reported_invalid` |
| Read-only DB interface | Proven against Postgres by running all four tools as a role holding only `SELECT` on six tables (+ `SELECT, INSERT, UPDATE` on `identity_rate_counters` for the shared limiter) and showing writes to authority tables raise `permission denied`. | `test_tools_run_as_a_role_that_can_only_select_authority_tables` |
| Execution subsystem untouched | The branch returns before `apply_governance`; no gateway, nonce, epoch, executor or dispatch import (static AST guard); authority tables byte-identical before/after; zero nonces. | `test_module_references_no_state_changing…`, `test_the_four_tools_change_no_authority_state` |
| Rate limiting, bounded pagination | Durable shared limiter per org+tool, fail-closed when its storage is down; page ≤ 50, cursor ≤ 150. | `test_rate_limit_is_per_org_and_tool_and_fails_closed` |
| No driver leakage | Any exception becomes `authority_read_unavailable`. | `test_storage_failure_does_not_leak_driver_detail` |
| MCP conformance | Real client over Streamable HTTP: advertised only with governance, annotations all `readOnlyHint:true`, viewer refused and the refusal metered. | `test_tools_are_advertised_and_callable_over_real_mcp`, `test_viewer_is_refused_…`, `test_without_governance_…` |

Result on this tree: 42 passed (`tests/test_mcp_authority_tools.py`), plus the existing
MCP/protocol/directory/OAuth/server.json suites green.

## Recommended production database role (design — not provisioned)

A dedicated login role for the control-plane read service, separate from the execution role:

```sql
CREATE ROLE wp_authority_read LOGIN;                 -- credential from the secret manager
GRANT USAGE ON SCHEMA public TO wp_authority_read;
GRANT SELECT ON governance_policies, governance_policy_versions, governance_policy_history,
               governance_approvals, governance_evidence, governance_evidence_chain_heads
  TO wp_authority_read;
GRANT SELECT, INSERT, UPDATE ON identity_rate_counters TO wp_authority_read;
```

**Wired (this revision).** `WHITEPACT_AUTHORITY_READ_DATABASE_URL` selects a dedicated engine/role for the read path
(`select_authority_read_backend` in `mcp/server.py`). Behaviour:

| Situation | Result |
|---|---|
| URL set | tools use their own engine and the limiter lives on it too; the only supported production mode |
| Production, URL not set | **tools are not advertised and refuse to run** (`authority_tools_unavailable`); the read path never borrows the application's full-privilege role; a warning is logged |
| Development, URL not set | falls back to the main engine (local testing only) |

Verified on Postgres through the real hosted app (`tests/test_authority_read_path_wiring.py`, 8): the role appears in
`pg_stat_activity`; unauthenticated/forged keys get 401; viewer role refused; two tenants never see each other and a
smuggled `org_id` is refused; the 7th evidence verification in a minute is rate limited; row counts of approvals,
policies, evidence and execution nonces are unchanged after the calls. **Startup verification (new):** when a dedicated URL is set, the app asks PostgreSQL which public tables the role can
INSERT/UPDATE/DELETE/TRUNCATE (`write_privilege_violations`); anything other than the limiter's counters, or a result that
cannot be obtained (not PostgreSQL, probe failed), disables the tools and logs `authority_tools_disabled`. Tested with
deliberate mis-grants (`tests/test_authority_read_path_wiring.py`, 12 tests). A superuser or table owner is flagged, as it
should be. **Not done:** the role itself is not provisioned anywhere (no production database); the check runs at startup
only (a later GRANT is not noticed until restart); credential rotation for this role is not documented.

## Known limitations (honest)

1. **Same-process execution isolation is not changed.** The read path shares the MCP process with
   the execution path; the separation is by code path and (when wired) by database role, not by
   process. A compromise of the process is a compromise of both.
2. **Role is the credential's role.** An OAuth reviewer principal inherits whatever role the
   credential carries; there is no per-tool OAuth scope yet (`whitepact:review` covers all tools).
3. **`verify_evidence` is O(chain length)**; the 6/min limit bounds cost but a very large tenant
   chain could still make each call slow. Incremental verification from a checkpoint is future work.
4. **Simulation can be used to probe a policy** one `(action, target)` at a time. It is
   rate-limited and returns only effect + reason code, but a determined ANALYST can still map
   behaviour. That is the same information the dashboard gives the same role.
5. **Count assertions:** `server.json`'s `tool_count: 30` describes the always-on production set;
   the four authority tools appear in addition only when governance is wired. Directory submission
   text must say so.

## Antigravity audit request (independent)

Please attempt to break, not to confirm:

1. Obtain any data from another tenant through any of the four tools (argument smuggling, cursor
   manipulation, `expected_head_hash`, risk-tier override, unicode/long inputs).
2. Reach a state change: a nonce, an approval resolution, a policy edit, an evidence row, an epoch
   bump — via these tools or via error paths.
3. Bypass the role matrix or the rate limit (concurrent bursts; limiter outage behaviour).
4. Confirm the advertised descriptors are truthful (annotations, descriptions, "not an
   authorization") and that stdio / ungoverned hosted never expose them.
5. Review the Postgres privilege model above for any table the service reads that is not listed.

Candidate for audit: branch `claude/whitepact-isolation-failclosed-linux-recovery`; the exact
commit and tree SHA are recorded in the issue register entry REC-35.
