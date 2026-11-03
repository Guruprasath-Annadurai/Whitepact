# Enterprise Compatibility Notes

Community Core does **not** import or modify `src/responsibleai/**`.

Private enterprise code may integrate by:

1. Treating `whitepact_community.models.GovernanceDecision` / `DecisionResult` as a protocol-compatible vocabulary (string enum values match the five-way contract).
2. Wrapping `LocalGovernanceKernel.evaluate()` behind an adapter if a future shared interface is approved.
3. Keeping billing, dashboard, db, auth, and hosted MCP on the enterprise side of the boundary.

No enterprise source was deleted or refactored to make the community package appear clean.
