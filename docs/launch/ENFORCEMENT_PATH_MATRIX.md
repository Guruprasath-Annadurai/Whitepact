# Enforcement path matrix

Which routes to a side effect are **enforced** by WhitePact, which are **advisory**, and which are **not
covered**. "Enforced" means the side effect cannot occur without valid, independent authorization inside
WhitePact's declared boundary. Evidence is the test file that exercises the behavior; a path with no test
named here is NOT TESTED in this pass, whatever the code appears to do. Nothing here is independently
verified; read it as the claim Antigravity should try to break.

| Path | Status | What stops an unauthorized effect | Evidence (tests) |
| --- | --- | --- | --- |
| Hosted MCP, Streamable HTTP, tenant-scoped | Enforced | `_call_tool` refuses with `governance_unavailable` when governance, tenant context or an org id is missing, or the credential is legacy; otherwise `apply_governance` -> `ExecutionAuthorization` -> `InternalToolExecutor`. | `test_mcp_server_gating`, `test_mcp_governance_dispatch`, `test_phase1_release_gate`, `test_mcp_ws2_authority_matrix` |
| Hosted MCP, governance disabled in production | Fail closed | Production hosted MCP requires `mcp_governance_enabled=true`. | `test_mcp_server_gating` |
| REST `/api/v1/governance/tools/call` | Enforced | `apply_governance` in the dashboard app; approval-required actions queue instead of running. | `test_v1_exactly_one_effect`, customer-journey CI job |
| Upstream MCP proxy | Enforced | `apply_upstream_governance`; target fingerprint drift check; same single-use grant. | `test_mcp_ws2_upstream_reconciliation` |
| Approval resume | Enforced | `resume_approval` re-validates and consumes a grant; a request with no requester is refused. | `test_launch_gate_resume_identity` |
| Internal tool execution (`InternalToolExecutor`) | Enforced | Validates and consumes the grant first; durable nonce prevents replay; **runs in a container** unless the explicit non-production switches below. | `test_executor_bypass_invariant`, `test_isolation_fail_closed_default`, `test_isolation_real_tool_e2e` |
| Container execution | Enforced (Linux) | No network, read-only root, dropped capabilities, unprivileged UID, trusted immutable runner. | real-container tests; macOS records a `QUALIFICATION_SKIP`, which is not a pass |
| Host-side fixture `test.counter.increment` | Narrow exception | Exact tool-name match, its own switch, refused if any production marker is set; real tools unaffected. **Needs Antigravity review.** | `test_isolation_real_tool_e2e::TestHostSideFixtureCannotBeReachedByUntrustedInput` |
| Local community stdio MCP (`whitepact-mcp`) | **Not enforced, by design** | Calls `dispatch_tool` directly: there is no organization identity to govern. Prints an `UNGOVERNED LOCAL MODE` banner; the enterprise trust domain refuses to start stdio. | `test_mcp_enterprise_trust_domain`; `docs/launch/LOCAL_STDIO_MCP_SCOPE.md` |
| Python/TypeScript/Go SDK decision calls | Advisory | An SDK returns a *decision*. It does not stop code that ignores it. Enforcement happens only when the call goes through a governed server route above. | NOT TESTED as an enforcement claim |
| Background workers, scheduled actions, multi-agent delegation, administrative operations | NOT TESTED | Not exercised in this pass. | none |
| Actions WhitePact does not mediate (an agent calling an API directly) | Out of scope | Cannot be intercepted; do not claim otherwise. | n/a |

## Environment that changes the route

| Setting | Effect | Production |
| --- | --- | --- |
| Any of `WHITEPACT_ENV`, `WHITEPACT_ENVIRONMENT`, `RAI_ENV`, `RAI_ENVIRONMENT`, `ENVIRONMENT`, `ENV` (or `.env`) set to `production`/`prod`/`prd`/`live` | Disables every unisolated route. Conflicting values, or a name that is neither a production alias nor a known non-production name, also count as production and Settings refuses to start (`responsibleai/environment.py`). | the safe state |
| `WHITEPACT_ALLOW_UNISOLATED_EXECUTION=1` | Lets any internal tool run in-process. Local development only. | ignored |
| `WHITEPACT_ALLOW_SYNTHETIC_HOST_TOOL=1` | Lets only the test fixture run host-side. | ignored |
| `WHITEPACT_ISOLATION_IMAGE` | Selects the container image. Deployment configuration, never request input. | set to an approved digest |

An unset environment no longer disables isolation: the default is to require it. A deployment that sets
neither opt-in and has no Docker daemon refuses to start the executor.

## Attack list from the master directive: what was tested here

Tested in this pass (see the register): forged/expired/revoked credentials, a read-only key, revocation while an approval is pending, and cross-tenant approval access at the REST transport against real PostgreSQL, plus forged/expired/revoked and mid-session revoked keys over hosted MCP Streamable HTTP; capacity reservation races against a live Redis; replayed and mismatched grants against the executor, lookalike and
smuggled tool names, tenant spoofing through arguments, missing production configuration, container runtime
unavailable (executor refuses), fallback to in-process execution (removed), PyJWT-dependent identity paths on
the patched version. NOT tested in this pass: wrong audience beyond scope and tenant,
failing identity provider or policy engine, revocation during a running container, multi-host Redis failover.
