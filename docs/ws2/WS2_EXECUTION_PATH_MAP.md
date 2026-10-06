# WS-2 — Execution path map (runtime authority)

**Branch:** `cursor/whitepact-ws2-runtime-authority-f7a9`  
**Purpose:** Map every repository route capable of reaching consequential execution and document where the canonical authority kernel binds.

Legend: **Y** = enforced on this path in current tree; **P** = partial / environment-gated; **N** = intentionally ungoverned (documented); **R** = relies on separate gate (isolation broker subprocess only after `admit_execution`).

| Path | Entry | Identity / tenant | Intent / action | Policy + authority | Approval | Grant + nonce + epoch | Dispatch | Evidence |
|------|--------|-------------------|-----------------|------------------|----------|------------------------|----------|----------|
| Hosted MCP Streamable HTTP | `mcp/server.py` `_build_http_app` → `_call_tool` | Org-scoped API key / OIDC via HTTP auth middleware | `ActionRequest` in `apply_governance` | `AuthorityResolver` + `WhitePactRuntimeGateway` | `REQUIRE_APPROVAL` → `ApprovalRepository` | `authorize_execution` + `ExecutionNonceRepository.consume` when repos wired | `InternalToolExecutor` → `dispatch_tool` (non-prod) or `IsolationBroker` (prod) | Mandatory write before ALLOW; fail-closed on error |
| Hosted MCP SSE | Same ASGI app, SSE transport | Same | Same | Same | Same | Same | Same | Same |
| Community stdio MCP | `trust_domain.entrypoint_main_stdio` → `_run_stdio` → `_call_tool` | No org context on stdio | Ungoverned tool args | **N** — no `apply_governance` | **N** | **N** | Direct `dispatch_tool` when not `_current_hosted` | Optional / not on ALLOW path |
| Enterprise stdio | Console / `python -m` / `main()` | — | — | **Refused** (`SystemExit(2)`) | — | — | **Never starts** | — |
| Upstream MCP (hosted tool surface) | `upstream_dispatch.apply_upstream_governance` | Org-scoped `OrgContext` | `ACTION_TYPE` + target fingerprint | Same gateway stack + registry pre-check | Same | Same + fingerprint | `UpstreamMCPExecutor` → `_call_upstream_tool` | Fail-closed evidence |
| REST governed internal tool | `dashboard/app.py` `governance_call_tool` | Bearer org key | `apply_governance` | Y | Y | Y | Y | Y |
| REST upstream proxy | `dashboard/app.py` `upstream_call_tool` | Bearer org key | `apply_upstream_governance` | Y | Y | Y | Y | Y |
| Resume after approval | `governance_integration.resume_approval` (+ REST execute endpoint) | Reconstructed from approval | `build_resume_action` | Re-resolve + epoch/policy version compare | `approval_repo.consume` | Fresh `authorize_execution` at **current** epoch | Internal or upstream executor | Y; denies on security drift |
| Isolation subprocess runner | `isolation/subprocess_backend.py` | Passed in isolated payload | Pre-admitted off-box | **R** — parent must call `admit_execution` first | — | Parent holds permit | Child `dispatch_tool` | Parent evidence |
| Isolation container runner | `isolation/container_backend.py` | Same | Same | **R** | — | Same | Child `dispatch_tool` | Parent evidence |
| Phase 7A dispatcher | `runtime/dispatcher.py` | Gated by `phase7a_dispatcher_enabled` | Authority kernel CAS | **P** — production refused via `gate.py` | Worker tickets | Epoch + nonce in kernel tests | Worker execution | Gauntlet registry links tests |
| LangChain / middleware | `langchain_middleware` | Agent identity | Tool mapping | Gateway evaluate | Per tests | Executor binding tests | Blocked by default | Per tests |
| SDK / CLI consequential | CLI lazy paths; no direct `dispatch_tool` in CLI | — | — | Must use HTTP/MCP governed surfaces | — | — | No casual CLI bypass located | — |

## Call-site inventory (consequential dispatch)

| Symbol | Allowlisted module | Notes |
|--------|-------------------|--------|
| `dispatch_tool()` | `mcp/tools.py` (def), `governance/execution.py`, `mcp/server.py` (community/hosted fallback only when governance off or unhosted), `isolation/*_backend.py` (post-admission child) | CI: `tests/test_ws2_execution_boundary_invariant.py` |
| `executor.execute(authorization, …)` | `governance_integration.py`, `upstream_dispatch.py`, `governance/execution.py`, `upstream_executor.py` | CI: same invariant |

## Paths still requiring Antigravity M1 proof

- Every production configuration with `IsolationBroker` + Docker unavailable (fail-closed vs fallback) under real deploy env.
- Full worker queue / retry / resume matrix under multi-replica Redis (Phase 7A) when enabled in non-production.
- PostgreSQL-only race behaviors (optional CI: `WHITEPACT_TEST_POSTGRES_EXECUTION`).

## Related tests

- `tests/test_mcp_governance_dispatch.py` — live HTTP MCP + governance
- `tests/test_mcp_ws2_authority_matrix.py` — WS-2 adversarial matrix
- `tests/test_executor_bypass_invariant.py` — permit tampering
- `tests/test_upstream_gateway.py` — upstream SSRF + binding
- `tests/test_phase1_execution.py` / `tests/test_phase1_live_admission.py` — durable nonce concurrency
- `tests/test_resume_after_approval.py` — approval resume pipeline
- `tests/test_ws2_execution_boundary_invariant.py` — static bypass detection
