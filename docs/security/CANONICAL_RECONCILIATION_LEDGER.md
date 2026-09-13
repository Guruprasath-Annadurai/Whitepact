# Canonical Enterprise Security Integration — Reconciliation Ledger

One entry per reconciled security behavior. Nothing is entered here
without independently re-verified test evidence at the canonical
candidate SHA that introduced or confirmed it.

---

## Entry 1 — Checkpoint 6: Unified Transport Boundary

| Field | Value |
|---|---|
| Source branch | `integration/enterprise-phase1` (native — not a separate frozen phase branch) |
| Source SHA (design) | `a0a904db98725163493b88734fdb3d76a7c7c88e` |
| Source SHA (implementation) | `00560d130f6539a96e6c3036d22e5e6357b57974` |
| Source commits | `a0a904d docs(security): specify unified transport boundary`, `00560d1 fix(security): isolate tenant notification transports` |
| Security invariant | Every consequential execution transport (hosted MCP, upstream MCP, approval resume, internal/upstream executors) either enters canonical governance (`apply_governance` / `apply_upstream_governance` / `resume_approval`) or is an explicit, non-fallback, non-consequential exception (Community stdio, discovery/metadata calls). Operational transports (webhooks, WebSocket) are not tool-execution paths but must remain tenant-scoped — a tenant's event must never reach another tenant's webhook or WebSocket connection. |
| Canonical implementation location | `src/responsibleai/dashboard/app.py` (WebSocket tenant-channel resolution, webhook emission call sites), `src/responsibleai/webhooks/manager.py` (origin-tenant-required emission), `src/responsibleai/db/approval_repository.py` |
| Integration method | Native — already present at the canonical starting SHA, not integrated from a separate phase branch this pass. |
| Tests | `tests/test_checkpoint6_transport_boundary.py` (dedicated), `tests/test_tenant_isolation_webhooks.py`, `tests/test_tenant_isolation.py`, `tests/test_tenant_isolation_org_admin.py` |
| Verification performed this pass | Re-ran all 4 test files fresh: **12 passed, 0 failed**. Independently re-derived the consequential-transport inventory via direct `grep -rn "dispatch_tool("` across `src/responsibleai/` (not trusting the design doc's own table) — found exactly the two real call sites the doc names, no more, no fewer. Independently searched for a scheduler/cron/background-job framework and found none that dispatches a consequential action, corroborating the doc's claim that no scheduled-execution transport exists. |
| Canonical commit SHA (this pass) | No new commit required — Checkpoint 6 was already correctly implemented at the starting SHA; this pass's own commit (below) only adds this ledger entry and the verification record. |
| Status | **CLOSED**, independently re-verified. |

**What this closure does NOT cover**: DNS rebinding remains an explicit, named-open P1 in the design doc itself ("DNS rebinding remains an open P1 release blocker and is not changed here") — this is Wave 1 of this reconciliation, not yet started. Process isolation, trust fabric, IAM, and policy/data governance (Phases 2–5) are entirely separate, unintegrated work — see the implementation plan.
