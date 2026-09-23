# AI risk management evidence

WhitePact implements AI governance in product code — map AI-CAIQ AI-specific questions here rather than duplicate paper controls.

| Risk | Control | Evidence |
|------|---------|----------|
| Excessive agency | Authority kernel + governance dispatch | `runtime/authority_kernel.py`, `mcp/upstream_dispatch.py` |
| Prompt injection via memory | `rai_memory_write_check`, causal influence | `governance/causal_influence.py` |
| Ungoverned tool execution | MCP production tool registry, read-only directory tools | `tests/test_mcp_production_tool_registry.py` |
| Human oversight | Approvals + step-up auth | `governance/approval.py`, `tests/test_resume_after_approval.py` |
| Revocation | Revocation epoch + kernel | `tests/test_revocation_kernel.py` |
| Audit / explainability | Tamper-evident audit + machine responses | Audit pipeline, global directory evidence states (separate feature branch) |

**Doctrine (unchanged):** Agents may plan freely; execution requires independently enforced authority.
