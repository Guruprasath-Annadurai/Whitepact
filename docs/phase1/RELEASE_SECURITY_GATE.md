# Phase 1 release security gate — partial checkpoint

Date: 2026-09-08. Canonical baseline: `d84dfbf8c700ef461ab36acc87c4999b5ff8a6d8`.
That SHA is **withdrawn as a production candidate** by the Product Manager.
Its website work remains accepted and unchanged. No push, merge, deployment,
Antigravity cherry-pick, new production candidate or checkpoint-complete claim.

## Implemented slice

- `mcp/server.py`: hosted requests without initialized governance, a tenant, or
  a non-legacy identity now return `governance_unavailable`, without dispatch.
  Both HTTP and SSE carry an independent hosted-mode ContextVar, reset in finally,
  so a missing identity cannot silently become local stdio. Local Community
  stdio remains available; it is not claimed as officially governed production.
  Discovery and protocol initialization remain accessible under existing auth.
- `governance/execution.py`: the shared validator rejects DENY, QUARANTINE and
  REQUIRE_APPROVAL permits, not just the permit-construction helper.
- `governance/upstream_executor.py`: validation is repeated after asynchronous
  registry/audit work, immediately before the consumed flag changes, with no
  intervening await. This closes competing calls sharing one in-memory permit.
  That initial slice did **not** close copied-permit, restart or cross-process
  replay. The continuation below adds database admission to the live constructors.

The setting remains default-off for initialization, but default-off hosted calls
are now refused. Operators must not mistake turning it on for completing the
canonical authority work below. Billing unit tests explicitly isolate governance;
real governed MCP tests separately prove allow/deny and actual transport behavior.
The positive upstream integration test now enables governance at the receiving
WhitePact HTTP service instead of relying on its old ungoverned fallback.

## Reproduction and verification

- Before patching: five new negative tests failed because missing-governance calls
  dispatched and non-executable permits were accepted.
- Deterministic upstream race: two registry reads synchronized with an Event and
  audit awaits produced two outbound sink calls for one permit. After revalidation,
  one dispatch succeeds and one raises AuthorizationAlreadyConsumedError.
- Affected MCP/executor/transport suites: 105 passed. Initial expanded run had
  104 passes and one expected integration-contract failure from the ungoverned
  receiving service; corrected its setup without removing the success assertion.
- Authority, approval, JIT and envelope suites: 78 passed. These are compatibility
  checks, **not proof that stale approval or canonical integration is fixed**.
- MCP server plus nonce foundation: 64 passed, one PostgreSQL environment skip.
- Final combined invocation of all thirteen affected suites: **248 passed,
  one PostgreSQL environment skip** in 18.33 seconds.
- Scoped Ruff and mypy (three execution/server source files) passed.
- Website source and compiled assets compare identical to the accepted baseline.

Independent read-only investigation completed and agreed on the core gaps.
The separate patch-review agent was initially stopped by an account usage limit.
After the reset time it completed review and found one concrete metering regression:
the new governance refusal occurred after allowed-usage accounting. Corrected by
recording refused requests as blocked and moving allowed accounting below the
guard; added a regression assertion. The final combined result above includes this
fix. The reviewer found no additional bypass in the bounded changes; this is not
approval of the still-incomplete canonical execution architecture.

## Open independent findings

| Finding | Evidence | Status |
|---|---|---|
| Missing/disabled hosted governance fallback | Failing baseline tests; real HTTP negative test and zero sink calls after patch | Locally closed slice |
| Hosted canonical authority | apply_governance still constructs broad legacy AuthorityContext, without canonical resolver/consent; durable admission now wired | OPEN P0 |
| Upstream canonical authorization | Structural binding and durable admission are wired, but upstream_dispatch does not invoke canonical authority resolver | OPEN P0 |
| Stale approval resume | Real SQLite approval persisted, tenant governance epoch bumped to 1, separate human then approved; resume dispatched once | REPRODUCED, OPEN P0 |
| DNS validation-to-use | Synthetic resolver returned public address to validation and loopback to actual httpx transport; local listener received one request, HTTP 200, two lookups | REPRODUCED, OPEN P1 release blocker |
| JIT/legitimacy SHA-256 allegation | JIT has no SHA signature field; it wraps an in-process standing credential. Legitimacy canonical_digest is an exported fingerprint; no external-envelope authentication acceptance path found | NOT A VULNERABILITY as reported in inspected path |

DNS probe used only an ephemeral loopback listener and synthetic payload, no
production endpoint or metadata service. The shared validator returns no pinned
address. Webhook delivery, upstream calls and upstream discovery use hostnames
again at connection time. Redirect rejection does not fix DNS rebinding. A future
fix must preserve TLS SNI/hostname verification and cover all these callers.

Legitimacy digests must never be promoted to issuer authentication. Adding HMAC
or Ed25519 to in-process objects would not fix missing authority resolution.
Wrong-key signature tests are not applicable to a fingerprint-only mechanism;
they become mandatory if an authenticated external envelope is introduced.

## Remaining checkpoint 4 work

Bind canonical context, authority/consent versions, policy, principal, action,
target and purpose to permits; coordinate revocation mutations and durable
admission across every live executor. Approval resume must freshly resolve these
inputs before consumption and evidence/dispatch, instead of synthesizing ALLOW.
Current live REST resume does not pass an upstream registry: upstream approval
resume is rejected there, not evidence of an externally reachable upstream-resume
bypass. Direct helper callers still require proper fresh authorization.

The disposable PostgreSQL verification blocker is CLOSED. After narrow explicit
authorization, the fixture password was used only in memory, never printed or
saved. Authentication passed. `tests/test_phase1_execution.py`: **7 passed,
0 failed, 0 skipped**. This is the fresh result confirmed by the Product Manager
for this checkpoint. The continuation did not read the password again. It is
repository admission proof, not proof of deployed executors or canonical authority.

## Checkpoint 4 continuation — live durable admission

`admit_execution()` is shared by internal and upstream executors. Hosted MCP,
the dashboard upstream route and the dashboard approval-resume route now inject
the real nonce repository; request orchestration snapshots the tenant epoch before
evaluation/resume consumption and includes it in the permit. Missing epochs,
database failure and epoch-bound permits sent to database-free executors fail
closed. Expiry/action/principal binding is rechecked after the admission await.
Upstream dispatch snapshots admitted arguments and URL before later audit awaits.

The new executor tests use two independent SQLite engines and copied permits:
16 consumers yield one sink invocation and 15 replay refusals. Closing both engines
and reopening preserves replay rejection. A stale epoch produces zero additional
dispatches; a fresh permit still works. Database failure, expiry during admission,
argument mutation during admission, missing epoch and downgrade all refuse before
the sink. A real authenticated hosted HTTP test confirms one durable ledger row.
These are executor tests with mocked side-effect sinks, not deployed replica tests.

A further regression first failed: mutation during upstream credential-audit
persistence changed the dispatched arguments after admission. Snapshotting the
admitted payload fixes that representation gap; its regression is retained.

Independent investigation identified canonical/approval gaps before edits. The
separate patch reviewer identified the post-admission await gap, but its run was
blocked by the review service before completion. The parent reproduced the gap
with a failing test and corrected it. **Independent review remains incomplete**;
this report does not label the entire checkpoint or security fix verified/closed.

Final local validation for this continuation:

- `pytest tests/test_phase1_live_admission.py -q --no-cov --tb=short`:
  **13 passed**. The post-admission mutation regression first failed before the
  snapshot change, then passed.
- Expanded invocation: **286 passed, 1 skipped**, 129.78 seconds. Suites:
  `test_phase1_live_admission`, `test_phase1_release_gate`, `test_mcp_server_gating`,
  `test_mcp_governance_dispatch`, `test_mcp_http_transport`,
  `test_executor_bypass_invariant`, `test_upstream_gateway`, `test_jit_credential`,
  `test_legitimacy_envelope`, `test_phase1_authority`, `test_resume_after_approval`,
  `test_approval_execution_binding`, `test_phase1_execution`, `test_mcp_server`,
  `test_tool_trust`; all under `tests/`, with `-q --no-cov --tb=short`.
  The skip is the PostgreSQL environment absent from this invocation, not a
  replacement for the separately confirmed 7/0/0 PostgreSQL result above.
- Ruff on the six changed runtime files and the two changed/new admission test
  files passed. Mypy on execution, upstream_executor, governance_integration,
  upstream_dispatch and mcp/server passed (five source files).
- SPDX and documentation consistency scripts passed. `git diff HEAD --check`
  passed. Gitleaks stdin scans of the tracked diff and new test diff found no leaks.
- Website source/static comparison to the accepted baseline is unchanged.
- Changes remain local and uncommitted; baseline HEAD remains `d84dfbf8c700ef461ab36acc87c4999b5ff8a6d8`.

This slice does not make a newly sampled resume epoch equivalent to the epoch
when approval was requested. Approvals still lack persisted authority/epoch
snapshots and fresh authority/policy/principal re-resolution. Delegation, policy,
credential and other relevant mutation paths still need transactional epoch
wiring. Authentication-derived synthetic authority remains the two live-path
P0s above. Durable consumption cannot compensate for those missing checks.

## Direct-call audit — scoped inventory, not a completed all-sinks audit

| Call site | Classification | Boundary |
|---|---|---|
| `mcp/server.py::_call_tool` direct `dispatch_tool` | COMMUNITY-LOCAL-EXPLICIT | Hosted marker and tenant/governance refusal prevent HTTP/SSE fallback |
| `governance/execution.py::InternalToolExecutor.execute` | GUARDED | Structural permit plus durable admission when production constructor supplies repository; canonical caller authority still open |
| `governance/upstream_executor.py::_call_upstream_tool` SDK `session.call_tool` | GUARDED | Reached through upstream executor; structural binding and durable admission, not canonical closure |
| `mcp/governance_integration.py::apply_governance` | BYPASS | Canonical authority/consent resolution still bypassed by synthetic legacy authority |
| `mcp/upstream_dispatch.py::apply_upstream_governance` | BYPASS | Same canonical-resolution gap despite durable execution guard |
| `mcp/governance_integration.py::resume_approval` | BYPASS | Approval consumption is not fresh authority/consent/policy authorization |
| `governance/upstream_discovery.py` initialize/list_tools | NON-CONSEQUENTIAL | Protocol discovery, no tool execution; DNS P1 still applies |
| `mcp/server.py` server.run/list_resources/read_resource | NON-CONSEQUENTIAL | Protocol plumbing/static resource reads, not action dispatch |

Search covered tool dispatch, SDK call_tool and executor call sites, plus adjacent
integration/network paths. It does not establish that every dashboard mutation,
webhook, framework adapter or side-effect sink has been fully classified. The
remaining inventory and the explicit canonical BYPASS rows prevent closure.

The corrected Antigravity tenant fix and other critical fixes remain outside the
canonical branch pending Product Manager approval. Their additional P0 count is
not yet validated here. Confirmed open categories in this pass: three P0, one P1;
this is a scoped ledger, not a whole-repository vulnerability total.

Checkpoint 4: PARTIAL. New production candidate: NONE.
