# Canonical Enterprise Security Integration — Design Spec

**Canonical starting branch:** `integration/enterprise-phase1`
**Canonical starting SHA:** `00560d130f6539a96e6c3036d22e5e6357b57974`
**Implementation branch:** `integration/enterprise-canonical-candidate`
**Worktree:** `/Users/ag/whitepact-canonical-candidate`

## Repository inspection performed before writing this spec

- Verified all 5 frozen phase SHAs against git directly (not assumed):
  DNS/Egress (`c137ce4b...`), Phase 2 Runtime Isolation (`3784b196...`),
  Phase 3 Trust Fabric (`53704a12...`), Phase 4 Enterprise IAM
  (`8c753497...`), Phase 5 Policy/Data Governance (`9fa6f05f...`) — all
  five match exactly.
- Confirmed none of the 5 frozen phase branches are yet merged into
  `integration/enterprise-phase1` (`git merge-base --is-ancestor` on
  each returns false).
- Discovered Checkpoint 6 work already exists on the canonical branch
  itself, authored by a prior contributor: a design doc
  (`docs/superpowers/specs/2026-09-09-checkpoint6-unified-transport-boundary-design.md`,
  commit `a0a904d`) and an implementation
  (`fix(security): isolate tenant notification transports`, commit
  `00560d1`, canonical `HEAD`) with a dedicated test file
  `tests/test_checkpoint6_transport_boundary.py`.
- **Independently re-verified, not trusted from the design doc's own
  claim**: ran `tests/test_checkpoint6_transport_boundary.py` +
  `tests/test_tenant_isolation_webhooks.py` +
  `tests/test_tenant_isolation.py` +
  `tests/test_tenant_isolation_org_admin.py` for real — 12/12 pass.
  Independently re-derived the consequential-transport inventory via
  `grep -rn "dispatch_tool("` across `src/responsibleai/` rather than
  trusting the doc's table — found exactly the same two real call
  sites the doc names (`mcp/server.py`'s stdio path,
  `governance/execution.py`'s `InternalToolExecutor`), confirming the
  inventory is exhaustive, not just plausible. Also independently
  searched for a scheduler/cron framework (`APScheduler`,
  `schedule.every`, `CronTrigger`, `croniter`) and for
  `BackgroundTasks`/`asyncio.create_task` call sites in the dashboard —
  found none that dispatch a consequential action, corroborating the
  design doc's own claim that no scheduled-execution transport exists
  to inventory.

**Conclusion: Checkpoint 6 is CLOSED on the canonical branch as of the
starting SHA.** This spec does not redesign it; it accepts the existing
design and moves directly to planning Phase 2–5 integration.

## Architecture (integration order, per the governing mission)

```
Checkpoint 6 (CLOSED, verified above)
        ↓
DNS / Egress            (audit/dns-egress-security-closure @ c137ce4b)
        ↓
Phase 2 Runtime Isolation (feature/runtime-isolation-phase2 @ 3784b196)
        ↓
Phase 3 Global Trust Fabric (feature/global-trust-fabric-phase3 @ 53704a12)
        ↓
Phase 4 Enterprise IAM  (feature/enterprise-iam-phase4 @ 8c753497)
        ↓
Phase 5 Policy/Data Governance (feature/policy-data-governance-phase5 @ 9fa6f05f)
        ↓
Cross-phase adversarial hardening
        ↓
Exact-SHA candidate freeze
```

## Integration method (per phase)

Per the mission's own hard rule (Section 7/8): no whole-branch merge.
For each phase: diff the phase branch against its true parent, identify
the accepted security behavior, compare against current canonical,
classify (already-present / needs cherry-pick / needs reimplementation
against current interfaces), integrate the minimum needed, remove any
duplicate security plane, test immediately, commit with DCO sign-off,
record in `docs/security/CANONICAL_RECONCILIATION_LEDGER.md`.

## Scope and pacing honesty

This is a genuinely large integration (5 major security-architecture
phases, each requiring adversarial and PostgreSQL-concurrency testing
per the mission's own Sections 18/21). This spec covers the full
mission; the implementation plan below sequences it into waves with
explicit stopping points, per Section 27's own instruction not to rush
and to stop only at clean integration boundaries. This pass's own
realistic scope: close out Checkpoint 6 formally (ledger entry,
verification) and begin DNS/Egress reconciliation (the next item in
the required order) as far as this session's budget allows, with an
honest checkpoint report — not a fabricated full-mission closure.

## Self-review

- **Invented claims**: none — Checkpoint 6's closure is backed by a
  fresh, independent test run and an independent re-derivation of its
  own inventory claim, not by trusting the prior contributor's doc.
- **Coupling**: this spec does not touch `AuthorityResolver`,
  `ExecutionAuthorization`, durable admission, or evidence-chain
  architecture — Checkpoint 6's fixes are transport-layer tenant-scoping
  only, exactly as its own design doc states.
- **Non-determinism**: N/A at this stage (no new code written yet
  beyond documentation).
- **Placeholders**: none.
