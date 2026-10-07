# WS-2 — Execution boundary allowlist review map

Automated guard: `tests/test_ws2_execution_boundary_invariant.py`.

| Module | Why direct `dispatch_tool` exists | Authority check preceding dispatch | Proving test(s) | Classification |
|--------|-----------------------------------|------------------------------------|-----------------|----------------|
| `mcp/tools.py` | Canonical tool implementation | Handlers assume caller enforced governance; production hosted never calls ungated | `test_mcp_governance_dispatch.py` | Definition |
| `governance/execution.py` | `InternalToolExecutor` after `admit_execution` | `_validate_authorization` + optional `nonce_repo.consume` | `test_executor_bypass_invariant.py`, `test_phase1_live_admission.py` | Enterprise governed |
| `mcp/server.py` | Community stdio / legacy unhosted fallback | Hosted: `apply_governance` runs first; enterprise stdio refused | `test_mcp_ws2_authority_matrix.py`, `test_mcp_enterprise_trust_domain.py` | Community-only ungated path |
| `isolation/subprocess_backend.py` | Child runner after parent admission | Parent `InternalToolExecutor` / broker must call `admit_execution` first; child trusts stdin (LOCAL_DEV) | `test_ws2_isolation_child_admission.py` | Post-admission isolation (non-prod) |
| `isolation/container_backend.py` | Same as subprocess | Same | `test_ws2_isolation_child_admission.py` | Post-admission isolation |

| Module | `executor.execute` | Authority | Tests |
|--------|-------------------|-----------|-------|
| `mcp/governance_integration.py` | After `apply_governance` / `resume_approval` | Full gateway + evidence + nonce | `test_mcp_governance_dispatch.py`, `test_resume_after_approval.py`, `test_mcp_ws2_live_invalidation_matrix.py` |
| `mcp/upstream_dispatch.py` | After upstream governance | Registry + resolver + evidence + nonce | `test_upstream_gateway.py`, `test_mcp_ws2_upstream_reconciliation.py` |
| `governance/upstream_executor.py` | Upstream implementation | Same as internal executor invariants | `test_upstream_gateway.py` |

**Review rule:** any new row in this table requires an explicit PR review and a test that proves the authority relationship — allowlisting alone is insufficient.
