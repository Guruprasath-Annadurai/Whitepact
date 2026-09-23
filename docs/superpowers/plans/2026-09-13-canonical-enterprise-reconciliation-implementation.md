# Canonical Enterprise Security Integration — Implementation Plan

## Wave 0 — Checkpoint 6 formal closure (this session)

1. Independently re-verify Checkpoint 6's test suite and inventory
   claim (DONE — see design spec).
2. Write `docs/security/CANONICAL_RECONCILIATION_LEDGER.md` recording
   Checkpoint 6's closure with exact source commits and test evidence.
3. Run the broader regression set touching the same subsystems
   (dashboard, webhooks, websocket, MCP governance dispatch) to build
   additional confidence before treating Checkpoint 6 as a stable base
   for Wave 1.
4. Commit (DCO-signed) at a clean boundary.

## Wave 1 — DNS / Egress reconciliation (next, not started this pass
unless time remains)

1. Diff `audit/dns-egress-security-closure` (`c137ce4b`) against its
   true parent (determine via `git merge-base`).
2. Identify the accepted `SafeNetworkBackend` behavior: resolve-all-
   then-validate, fail-closed on forbidden destination, DNS-rebinding
   resistance, connect-to-validated-address, post-connect peer
   validation, original-hostname TLS/SNI, cert-mismatch rejection,
   proxy-bypass prevention, `PUBLIC_ONLY` mode for untrusted input.
3. Compare against current canonical webhook/upstream-MCP delivery
   code.
4. Classify each piece of behavior; integrate.
5. Re-run the specific adversarial attack named in the mission
   (public IP at validation time, private/loopback IP at connection
   time) for real, not just unit tests.
6. Test, commit, ledger entry.

## Waves 2–5 — Runtime Isolation, Trust Fabric, Enterprise IAM,
Policy/Data Governance (not started this pass)

Each follows the same pattern as Wave 1: diff against true parent,
classify, integrate minimally, remove duplicate security planes, test
immediately, commit, ledger entry. Each phase's own adversarial list
(Sections 11–14 of the governing mission) must be attempted for real
against the integrated result, not assumed from the source branch's own
claims.

## Wave 6 — Cross-phase adversarial matrix (after all phases integrated)

The 12-scenario matrix in Section 18 of the governing mission. Requires
all five phases integrated first — cannot be meaningfully run against a
partial integration.

## Wave 7 — Alembic reconciliation, PostgreSQL concurrency, exact-SHA
freeze, final report

Per Sections 16, 21, 28–33 of the governing mission.

## Explicit pacing statement

Given the size of this mission, this implementation plan is written to
be executed across multiple sessions/waves, each ending at a clean,
fully-tested boundary (per Section 27's own instruction). This session
covers Wave 0 in full and begins Wave 1 only as far as time allows. No
wave is reported as complete without the specific test evidence this
plan requires for it.
