# WS-3 — Unified SaaS surface (Lane B analysis only)

**Dependency:** WS-2 canonical authority contract (`apply_governance`, `resume_approval`, REST `/api/governance/*`). WS-3 must **not** introduce a parallel execution kernel.

## Scope (planned)

- Single authentication story across dashboard, marketing web, and API (collision removal between legacy `rai_*` and `whitepact_*` session paths).
- Approval UX wired to existing `ApprovalRepository` and resume endpoints.
- Policy management UI on top of `PolicyRepository` / gateway evaluate — no new enforcement layer.

## Out of scope for WS-3 design

- Replacing `InternalToolExecutor` / nonce consumption
- Community stdio governance
- Billing canonicalization (deferred WS-4; Stripe vs Paddle noted in Phase 1 tracker)

## Recommended branch (when implementation starts)

`cursor/whitepact-ws3-saas-unified-f7a9` off merged `main` after WS-1 + WS-2 integration gates.

## Next engineering actions (analysis)

1. Inventory duplicate auth entrypoints in `dashboard/app.py` vs `web/` / sovereign routes.
2. Map approval screens to `governance_resolve_approval` + `resume_approval` API contracts.
3. Document BLK-P0-04 / BLK-P0-06 touchpoints without merging until M1 qualified.
