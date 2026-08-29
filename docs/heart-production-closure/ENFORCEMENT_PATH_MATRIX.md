# WhitePact — Heart Enforcement Chokepoint Closure — Phase E0

## Complete Execution-Path Audit

**No code was modified to produce this document.** Every claim below is
grounded in a specific file:line read during this audit, not inferred or
assumed. Where a claim needed a call-site grep to confirm ("is this actually
wired anywhere"), the grep is described so it can be independently
re-run.

---

## Headline finding (read this first)

**Gap A's consent-backed legitimacy (`authority_resolver.py`'s
`consent_repo` parameter, closed in the prior Heart Production Closure
initiative) has ZERO live call sites.** Both places in production code that
call `resolve_authority_grant()` — `mcp/governance_integration.py:229` and
`mcp/upstream_dispatch.py:128` — call it without a `consent_repo` argument.
Grep used to confirm this is exhaustive:

```bash
grep -rn "resolve_authority_grant(" src/responsibleai/ | grep -v tests
# -> only 3 hits: the function's own definition, governance_integration.py,
#    upstream_dispatch.py. Neither call site passes consent_repo.
```

This means: in production today, even with `enterprise_mode=true` and
`mcp_governance_enabled=true` (i.e. every gate the prior initiative's Gap C
added satisfied), Heart legitimacy resolution only ever checks **root
authority** — consent is never consulted on any live path. All 15 of Gap
A's own tests exercise `resolve_authority_grant(..., consent_repo=...)`
directly; none of them exercise it through `apply_governance()` or
`apply_upstream_governance()`, so this gap produced no test failures and was
not visible from the test suite alone. This is not one of the four bypasses
this initiative's directive named — it is a fifth, more fundamental
finding: the wiring gap is one level higher than "does Heart run," it's
"does Heart consult everything the previous phase built." **Recommendation
for E1+ (not implemented here):** thread `consent_repo` through both
`GovernanceServices` (`governance_integration.py`) and
`apply_upstream_governance()`'s signature, mirroring how `root_authority_repo`
already flows.

---

## Complete inventory of execution-reaching paths

Searched: `dispatch_tool`, `apply_governance`, `apply_upstream_governance`,
`resolve_authority_grant`, `InternalToolExecutor`, `resume_approval`,
`UpstreamMCPExecutor`, plus every `@app.post`/`@app.get` in `dashboard/app.py`
under `/api/governance/*`, plus `[project.scripts]` in `pyproject.toml`,
plus every package `__init__.py` for re-exports.

### Path 1 — MCP stdio transport

```
ENTRYPOINT:              mcp/server.py `main()` -> stdio_server() -> server.run()
                          -> @server.call_tool() `_call_tool()` (mcp/server.py:180)
AUTHENTICATION:           None. `_current_org.get()` returns None (ContextVar
                          never set on this transport) -- `ctx is None` branch,
                          server.py:253.
HEART CHECK:              NONE when enterprise_mode=false (default).
                          When enterprise_mode=true: NOT a Heart/legitimacy
                          check -- a static RiskTier allowlist
                          (classify_action_risk() must return MINIMAL or LOW,
                          server.py:257-271). No root, no consent, no
                          revocation check of any kind.
POLICY CHECK:             None.
EXECUTION AUTHORIZATION:  None -- no ExecutionAuthorization object is ever
                          constructed on this path.
FINAL EXECUTOR:           dispatch_tool() called directly (server.py:273).
BYPASS POSSIBLE?:         YES, always, by design -- module docstring calls
                          this "full unrestricted tool access." This is a
                          declared capability, not an accidental hole, but it
                          is still a bypass relative to "governed action."
PRODUCTION REACHABLE?:    YES -- this is the default, free, self-hosted
                          transport; no configuration is required to reach
                          it. `enterprise_mode=true` narrows it to
                          MINIMAL/LOW-risk tools only, but does not close it.
```

### Path 2 — Streamable HTTP MCP (`/mcp`), governed

```
ENTRYPOINT:              mcp/server.py `_StreamableHttpEndpoint.__call__()`
                          (server.py:788) -> same `_call_tool()` as Path 1.
AUTHENTICATION:           `_authenticate_or_error()` (server.py:717) --
                          Bearer token, tried in order: OIDC JWT, VC-JWT,
                          then `_org_repo.authenticate(raw_key)` (static
                          per-org API key). Rate-limited by `auth_limiter`.
HEART CHECK:              Only when ALL of: ctx.org_id is set (excludes
                          legacy flat keys, Path 4 below), AND
                          `mcp_governance_enabled=true` (governance !=
                          None), AND `enterprise_mode=true` (checked inside
                          `_heart_legitimacy_denied_reason()`). When all
                          three hold: ROOT-ONLY (see headline finding --
                          consent is never consulted here).
POLICY CHECK:             Only under the same three conditions --
                          `WhitePactRuntimeGateway.evaluate()` via
                          `apply_governance()` (governance_integration.py:247).
EXECUTION AUTHORIZATION:  Only under the same three conditions --
                          `authorize_execution()` +
                          `InternalToolExecutor.execute()`
                          (governance_integration.py:563, execution.py:269).
FINAL EXECUTOR:           `InternalToolExecutor.execute()` when governed;
                          falls through to bare `dispatch_tool()`
                          (server.py:273) when `mcp_governance_enabled=false`
                          -- the default.
BYPASS POSSIBLE?:         YES if `mcp_governance_enabled=false` (default) --
                          full governance skip, same as Path 1 but over an
                          authenticated, org-scoped connection. YES if
                          `mcp_governance_enabled=true` but
                          `enterprise_mode=false` -- policy/quarantine/
                          evidence still run, but Heart legitimacy is never
                          checked (root or consent).
PRODUCTION REACHABLE?:    YES -- this is the documented "preferred hosted
                          transport."
```

### Path 3 — HTTP+SSE MCP (`/sse` + `/messages/`, legacy), governed

```
ENTRYPOINT:              mcp/server.py `handle_sse()` (server.py:755) ->
                          same `_call_tool()`.
AUTHENTICATION:           Identical to Path 2 -- same
                          `_authenticate_or_error()` call.
HEART CHECK / POLICY /
EXECUTION AUTHORIZATION /
FINAL EXECUTOR:           Identical to Path 2 -- both hosted transports
                          converge on the same `_call_tool()`, the same
                          `_current_governance` ContextVar, the same
                          `apply_governance()`. This is already, today, a
                          single chokepoint for policy/root-Heart/execution
                          binding across both hosted transports (see Phase
                          E1 below -- less new work is needed here than the
                          directive's framing implies).
BYPASS POSSIBLE?:         Same as Path 2.
PRODUCTION REACHABLE?:    YES -- "kept running, unmodified, for existing
                          clients," no removal date.
```

### Path 4 — Hosted MCP transport, legacy/demo authentication

**Correction, added after this document was first written**: sub-case
(b) below ("a legacy flat key matched by `_org_repo.authenticate()`
... org_id=None") was a factual error in the original audit.
Re-reading `OrgRepository.authenticate()` (`db/org_repository.py:207`)
directly: on a match it always returns `is_legacy=False` and
`org_id=row.org_id` (a real org, never `None`) -- there is no
DB-backed "legacy key with no org" case on this path at all; a
non-matching key returns `None` from `_authenticate()` and gets a 401
before `_call_tool()` is ever reached. Sub-case (a), the demo flag, was
accurate and is now closed by Phase E4 (`heart_production_gate.py`
refuses startup when `enterprise_mode=true` and
`mcp_http_allow_unauthenticated_demo=true`). **With that fix in place,
Path 4 is fully closed for the hosted MCP transports** -- the only
`org_id=None` case reachable through `_call_tool()`'s governance branch
condition no longer exists once demo-mode can't coexist with
enterprise_mode at startup. No further E3-style code change was needed
here; the "legacy-key bypass" the closure directive named turned out,
on this specific transport, to already not exist once the demo flag
(which this audit conflated with it) is closed. The original
paragraph is left below unedited, struck through in spirit, for an
honest record of what was first claimed:

```
ENTRYPOINT:              Same `_authenticate()` (server.py:684) feeding
                          Paths 2/3.
AUTHENTICATION:           TWO sub-cases, both producing an OrgContext with
                          `org_id=None`:
                          (a) `mcp_http_allow_unauthenticated_demo=true` --
                              zero credentials required at all
                              (server.py:685-699). Role forced to VIEWER,
                              but org_id is still None.
                          (b) A legacy flat key matched by
                              `_org_repo.authenticate()` -- `is_legacy=True`,
                              `org_id=None` (this is the DB-backed legacy
                              path, distinct from dashboard's separate
                              RAI_API_KEYS env-var path, Path 6 below).
HEART CHECK:              NONE -- `_call_tool()`'s governance branch
                          requires `ctx.org_id` truthy (server.py:226); None
                          org_id means this condition is always False.
POLICY CHECK:             NONE, same reason.
EXECUTION AUTHORIZATION:  NONE.
FINAL EXECUTOR:           `ctx is not None` (a real OrgContext exists, just
                          with no org) so the STDIO FALLBACK RISK-TIER GATE
                          (Path 1's enterprise_mode check) is NEVER REACHED
                          EITHER -- that gate is specifically inside
                          `if ctx is None:` (server.py:253). Falls straight
                          to bare `dispatch_tool()` (server.py:273) with NO
                          restriction of any kind, not even Path 1's
                          MINIMAL/LOW risk-tier allowlist.
BYPASS POSSIBLE?:         YES -- and structurally WORSE than stdio: an
                          authenticated-but-orgless hosted connection gets
                          LESS restriction than the "fully open" stdio
                          transport does under enterprise_mode, because it
                          skips the risk-tier check stdio's `ctx is None`
                          branch applies. This is a genuine asymmetry worth
                          fixing in E3/E4, not just closing the flag.
PRODUCTION REACHABLE?:    `mcp_http_allow_unauthenticated_demo` defaults to
                          false (config.py) -- reachable only if explicitly
                          enabled. The DB-backed legacy-key case's
                          reachability depends on whether any legacy keys
                          exist in a given deployment's `org_repository`
                          table; the code path itself is always present.
```

### Path 5 — Dashboard REST: upstream tool call (`/api/governance/upstream/servers/{id}/call`)

```
ENTRYPOINT:              dashboard/app.py:4131 `upstream_call_tool()`.
AUTHENTICATION:           `Depends(require_role(Role.ANALYST))` ->
                          `get_org_context()` (app.py:776) -- see Path 6/7
                          for its own three sub-cases.
HEART CHECK:              Explicitly rejects legacy/orgless keys first
                          (`if not _auth.org_id: raise HTTPException(400)`,
                          app.py:4144) -- fails closed for Path 6/7's
                          legacy cases specifically for THIS endpoint. For
                          an org-scoped key: same three-condition gate as
                          Path 2 (`root_authority_repo` wired +
                          `enterprise_mode=true`) inside
                          `apply_upstream_governance()`
                          (upstream_dispatch.py:122). ROOT-ONLY, same
                          headline finding -- consent_repo is not passed
                          here either (upstream_dispatch.py:128).
POLICY CHECK:             `WhitePactRuntimeGateway.evaluate()` via
                          `apply_upstream_governance()`, always runs for an
                          org-scoped key (not gated behind
                          `mcp_governance_enabled` -- this REST endpoint has
                          no separate opt-in flag; it is governed
                          unconditionally once reached).
EXECUTION AUTHORIZATION:  `authorize_execution()` +
                          `UpstreamMCPExecutor.execute()`
                          (upstream_executor.py -- same
                          `_validate_authorization()` shared helper
                          `InternalToolExecutor` uses).
FINAL EXECUTOR:           `UpstreamMCPExecutor.execute()`.
BYPASS POSSIBLE?:         Only the same "enterprise_mode off -> Heart
                          root-check skipped" gap every other path has;
                          this endpoint is otherwise the MOST consistently
                          governed path found in this audit (unconditional
                          policy/evidence, explicit legacy-key rejection).
PRODUCTION REACHABLE?:    YES.
```

### Path 6 — Dashboard REST: approval-resume (`/api/governance/approvals/{id}/execute`)

```
ENTRYPOINT:              dashboard/app.py:3253 `governance_execute_approval()`
                          -> `resume_approval()` (governance_integration.py:638).
AUTHENTICATION:           `Depends(require_role(Role.ADMIN))`, rejects
                          legacy/orgless keys (app.py:3266).
HEART CHECK:              NONE at resume time. `resume_approval()` does not
                          call `resolve_authority_grant()` at all --
                          confirmed by grep (`resolve_authority_grant` does
                          not appear in governance_integration.py's
                          `resume_approval()`/`build_resume_action()`
                          region). Heart's root check ran once, at the
                          ORIGINAL decision time that produced the
                          REQUIRE_APPROVAL outcome -- an arbitrary,
                          human-approval-latency amount of time before this
                          endpoint executes.
POLICY CHECK:             NONE at resume time either -- the original
                          Policy/Gateway decision is not re-evaluated.
EXECUTION AUTHORIZATION:  `ApprovalRepository.consume()` (single-use,
                          mutation/replay-protected) stands in for a fresh
                          `ExecutionAuthorization` -- structurally sound for
                          replay/mutation, but carries no Heart-legitimacy
                          binding.
FINAL EXECUTOR:           `InternalToolExecutor` or `UpstreamMCPExecutor`
                          depending on the approval's original action_type.
BYPASS POSSIBLE?:         YES, specifically for REVOCATION: if the
                          principal's root/consent/delegation is revoked
                          AFTER a REQUIRE_APPROVAL decision is queued but
                          BEFORE a human approves and this endpoint resumes
                          it, the action still executes. This is exactly
                          the property Phase E6 names ("if Heart authority
                          is revoked: DENY") and it is currently open on
                          this specific path. Not one of the four
                          originally-named bypasses -- a sixth, distinct
                          finding.
PRODUCTION REACHABLE?:    YES -- this is the only way a REQUIRE_APPROVAL
                          decision ever actually executes.
```

### Path 7 — Dashboard REST: general auth (dev mode / legacy flat key)

```
ENTRYPOINT:              dashboard/app.py:776 `get_org_context()`, the
                          shared FastAPI dependency for every
                          `/api/governance/*` route above.
AUTHENTICATION:           Two bypass-relevant branches:
                          (a) `settings.auth_enabled=false` (dev mode) ->
                              OrgContext(key_id="anon", role=OWNER,
                              is_legacy=True, org_id=None) with NO
                              credential presented at all (app.py:787).
                          (b) token in `settings.api_keys` (flat
                              RAI_API_KEYS env var, distinct from Path 4b's
                              DB-backed legacy keys) -> OrgContext(
                              key_id="legacy", role=OWNER, is_legacy=True,
                              org_id=None) (app.py:799).
HEART CHECK / POLICY /
EXECUTION AUTHORIZATION:  Both branches yield `org_id=None`, which Path 5
                          and every other org-scoped governance endpoint
                          explicitly rejects with a 400. So for the
                          ACTION-EXECUTING endpoints specifically (Path 5,
                          Path 6), this is NOT an execution bypass -- it is
                          rejected before reaching Heart/policy at all.
                          However, `Role.OWNER` under either branch DOES
                          grant full read/write access to every OTHER
                          `/api/governance/*` endpoint that does not require
                          `org_id` (e.g. reading org-wide audit logs,
                          modifying policy rules that a later org-scoped
                          call would be evaluated against -- app.py:4367,
                          5098 explicitly special-case `is_legacy=True` for
                          cross-org visibility). This is a data/config
                          exposure concern more than a direct
                          execution-bypass, but policy/ceiling/workflow-rule
                          MUTATION through this path could indirectly
                          change what a LATER, properly-org-scoped
                          execution is permitted to do.
FINAL EXECUTOR:           N/A directly (this dependency gates entry, not
                          execution) -- but note for E9: nothing in the
                          current `heart_production_gate.py` (prior
                          initiative's Gap C) checks `auth_enabled=true`.
                          A deployment could set `enterprise_mode=true` +
                          `mcp_governance_enabled=true` (satisfying every
                          existing startup check) while leaving
                          `auth_enabled=false`, which is a nonsensical but
                          currently UNBLOCKED combination for "production
                          authority-enforced mode."
BYPASS POSSIBLE?:         Not a direct execution bypass (see above), but a
                          configuration-adjacent risk worth an E9 startup
                          check: `enterprise_mode=true` should probably
                          also require `auth_enabled=true`.
PRODUCTION REACHABLE?:    `auth_enabled` defaults to `true` (config.py:90-93,
                          "Set to false to disable auth (development
                          only)") -- branch (a) requires an explicit opt-out,
                          not a default. Branch (b) (flat RAI_API_KEYS) is
                          reachable whenever that env var is set, which is a
                          documented, intentional self-hosted feature (see
                          login.html's own help text), not an accidental
                          default.
```

### Path 8 — Direct Python import of `dispatch_tool()`

```
ENTRYPOINT:              `from responsibleai.mcp.tools import dispatch_tool`
                          -- any Python code in the same process/venv.
AUTHENTICATION:           N/A -- no identity concept at this layer at all.
HEART CHECK / POLICY /
EXECUTION AUTHORIZATION:  NONE -- `dispatch_tool()` is the raw,
                          unwrapped implementation every governed path
                          above eventually calls (via `InternalToolExecutor`
                          or the stdio fallback). It has no caller-identity
                          parameter and cannot structurally distinguish a
                          governed caller from an ungoverned one.
FINAL EXECUTOR:           Itself.
BYPASS POSSIBLE?:         YES, always, by construction -- not a bug, a
                          structural property: `dispatch_tool` is not
                          exported from any package `__init__.py`
                          (confirmed: `mcp/__init__.py` has no eager
                          imports at all, by its own docstring), so it
                          requires a direct module import
                          (`responsibleai.mcp.tools`), not a top-level SDK
                          import -- some friction, not a real barrier for
                          anyone with repo access.
PRODUCTION REACHABLE?:    YES for any code running inside the same process
                          -- this is not reachable from outside the process
                          (no network/RPC surface), so its real-world blast
                          radius is "a compromised or careless in-process
                          Python caller," not "an external attacker."
```

### Path 9 — CLI (`biasbuster` / `responsibleai` / `whitepact` console scripts)

```
ENTRYPOINT:              `biasbuster.cli:main` (pyproject.toml:163-168).
FINDING:                 Does NOT touch `dispatch_tool`, `apply_governance`,
                          or any MCP/governance code at all -- confirmed by
                          grep (`dispatch_tool|apply_governance|governance`
                          does not appear in src/biasbuster/cli.py except
                          the word "governance" nowhere). This CLI is for
                          RAI scanning/benchmarking, unrelated to tool
                          dispatch.
PRODUCTION REACHABLE?:    N/A -- not a governed-execution path at all. Not
                          a bypass because there is nothing here to bypass.
```

### Path 10 — Background jobs / workers

```
FINDING:                 No scheduler, worker, or background-job module
                          calls `dispatch_tool`, `apply_governance`,
                          `apply_upstream_governance`, `InternalToolExecutor`,
                          or `resume_approval` anywhere in the codebase.
                          Confirmed by grep across every file that imports
                          any of those five names (10 files total, listed
                          in this audit's own working notes) -- all 10 are
                          either the definitions themselves, `mcp/server.py`,
                          `mcp/governance_integration.py`,
                          `mcp/upstream_dispatch.py`, `dashboard/app.py`, or
                          test files.
PRODUCTION REACHABLE?:    N/A -- no such path exists today.
```

### Path 11 — Examples / demo scripts, test helpers exported into production modules

```
FINDING:                 No `examples/` directory calling dispatch_tool
                          found. `mcp_http_allow_unauthenticated_demo`
                          (Path 4a) is the one demo-labeled *production*
                          feature flag; it is covered there, not here. No
                          test helper was found imported by a non-test
                          production module (all dispatch/governance
                          imports in test files import FROM production
                          modules, never the reverse -- confirmed by the
                          same 10-file list from Path 10's grep).
PRODUCTION REACHABLE?:    N/A.
```

---

## Summary table

| # | Path | Heart check | Policy check | Exec. authorization | Bypass? | Prod reachable? |
|---|------|:---:|:---:|:---:|:---:|:---:|
| 1 | stdio | risk-tier only (enterprise_mode) | none | none | YES (by design) | YES (default) |
| 2 | Streamable HTTP, governed | root-only, opt-in×2 | opt-in | opt-in | YES if either flag off | YES |
| 3 | HTTP+SSE, governed | same as #2 | same as #2 | same as #2 | same as #2 | YES |
| 4 | Hosted MCP, legacy/demo auth | none | none | none | YES, worse than stdio | flag-gated / data-dependent |
| 5 | Dashboard upstream call | root-only, opt-in | unconditional | yes | enterprise_mode off only | YES |
| 6 | Dashboard approval-resume | **none at resume time** | **none at resume time** | replay-protected only | YES (post-approval revocation) | YES |
| 7 | Dashboard general auth (dev/legacy) | N/A (rejected downstream for #5/#6) | N/A | N/A | config-exposure, not direct exec | opt-in only (auth_enabled defaults true) |
| 8 | Direct `dispatch_tool()` import | none | none | none | YES (structural) | in-process only |
| 9 | CLI | N/A | N/A | N/A | not applicable | N/A |
| 10 | Background jobs | N/A | N/A | N/A | none exist | N/A |
| 11 | Examples/test helpers | N/A | N/A | N/A | none found | N/A |

**Six real bypasses found, not four:**
1. stdio (declared capability, not accidental)
2. `mcp_governance_enabled=false` (governance entirely skipped on hosted transports)
3. `enterprise_mode=false` (Heart root-check skipped even when governance is on)
4. Legacy/demo hosted-MCP auth (Path 4) — worse than stdio, not just "also open"
5. **Consent never consulted on any live path (headline finding)** — not a bypass of Heart, but of half of what Heart was built to check
6. **Approval-resume does not re-check Heart at execution time** — a revocation between approval and resume is not honored

---

## Post-E0 status (updated as fixes land — this section, not the table
above, is the current source of truth)

| Finding | Status |
|---|---|
| Headline: consent never consulted live | **FIXED** — `consent_repo` wired into both call sites, regression test through the real HTTP dispatch path (`test_heart_wiring_phase6.py::TestConsentBackedLegitimacyReachableThroughLiveDispatch`) |
| 1. stdio (declared capability) | **FIXED** — `enterprise_mode=true` now blocks stdio entirely, not just non-MINIMAL/LOW (Phase E2) |
| 2. `mcp_governance_enabled=false` | Unchanged — still requires the deployment to opt in; `heart_production_gate.py` refuses `enterprise_mode=true` without it |
| 3. `enterprise_mode=false` | Unchanged by design — this is the documented dev/self-hosted default |
| 4. Legacy/demo hosted-MCP auth | **CORRECTED, then FIXED**: the "legacy DB-backed key" half of this finding was a factual error in the original audit (see the correction inline above) — no such path exists. The demo-flag half was real and is now closed (Phase E4). **Also found and fixed while implementing E4**: `verify_heart_production_enforcement()` (Gap C) was never actually called from this process (`mcp/server.py`'s `_build_http_app()`) at all — only from `dashboard/app.py`'s separate process. Now wired into both. |
| 6. Approval-resume doesn't re-check Heart | Not yet fixed — tracked as Phase E6 |
| Path 5 (dashboard upstream call) | Improved incidentally — now also gets `consent_repo` |

No code was modified during Phase E0 itself (the audit). Everything in
this status table reflects work done afterward, in separate commits,
each with its own tests.

## What Phase E0 deliberately does not do

No code was changed **during E0 itself**. The next
phase (E1 — canonical execution chokepoint design) should read this matrix
and decide, with the repository owner, which of the six findings above to
prioritize and in what order — this document does not make that call.
