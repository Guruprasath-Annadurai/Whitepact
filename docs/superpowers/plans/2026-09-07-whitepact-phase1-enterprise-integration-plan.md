# WhitePact Phase 1 Implementation Plan

> Execute task-by-task with the code-work verification discipline and checkpoint
> evidence. The user's approved directive authorizes inline execution without an
> additional strategy or execution-mode approval.

**Goal:** one coherent, locally verified enterprise candidate from the website freeze.
**Architecture:** forward schema integration, one trusted governance context and
one guarded execution path; self-hosted first, independent commercial services.
**Tech Stack:** Python, FastAPI, SQLAlchemy/Alembic, PostgreSQL, React, Docker, Helm.
**Spec:** `docs/superpowers/specs/2026-09-07-whitepact-phase1-enterprise-integration-design.md`.

## Global constraints

Start SHA `6f030a3e0bcece0e68f9ec5f18c9b28a2a42904d`.
No push, merge, destructive rebase, fake stamps, customer-data deletion or Phase 2.
PR85 is contained; PR50/54 only inform PR55 invariants. No wholesale PR55 merge.
Authentication is not authority. Billing and deployment identity never grant it.
Record exact tests and failures in `docs/phase1/`; no unsupported readiness claims.

## Checkpoint 1 — architecture and source contract

- [x] Verify branch, exact frozen SHA and clean worktree; create integration branch.
- [x] Read directive and source migration/resolver contracts; document design.
- [x] Review design/plan against scope, migration and security invariants; commit with DCO.

## Checkpoint 2 — canonical database

Files: `migrations/versions/0033_*` through `0040_*`, `migrations/env.py`,
`src/responsibleai/db/engine.py`, `src/responsibleai/db/migrate.py`,
`tests/test_phase1_migrations.py`, `tests/test_db_migrate.py`.

- [x] Add tests requiring exactly one head; verify unchanged website 0030–0032 with Git.
- [x] Add real SQLite/PostgreSQL empty/0029/0032 upgrades, tenant constraints,
  evidence-fork rejection and empty consent-scope assertions.
- [x] Implement schema from inspected intent; include tenant FKs and fail-closed
  schema preflight. Reject unversioned and legacy-ID mismatches without stamping.
- [ ] Run `.venv/bin/python -m pytest tests/test_phase1_migrations.py tests/test_db_migrate.py`;
  inspect migrations and focused lint; record evidence and DCO commit.

## Checkpoint 3 — identity, tenant, Heart and authority

Files: `governance/context.py`, `governance/authority_resolver.py`,
`governance/consent_proof.py`, `db/root_authority_repository.py`,
`db/consent_proof_repository.py`, `rbac/models.py`, under `src/responsibleai/`.

- [ ] Test authenticated tenant disagreement, missing root/consent, empty targets,
  wrong purpose, revoked/expired/tampered proof and explicit valid grant.
- [ ] Extract PR55 persistence/primitives, retain current auth contracts, implement
  trusted context and mandatory scoped resolution with no self-root fallback.
- [ ] Run context/Heart/consent/OAuth/tenant suites; inspect all auth-to-authority
  conversion sites; record evidence and DCO commit.

## Checkpoint 4 — execution, epochs and nonces

Files: `governance/execution.py`, `governance/models.py`, `governance/approval.py`,
`db/execution_nonce_repository.py`, `db/revocation_epoch_repository.py`,
`db/approval_repository.py`, and focused execution/approval tests.

- [ ] Test DENY/QUARANTINE refusal, all permit binding mutations, expiry, replay,
  multi-connection nonce race, revoked approval and policy change on resume.
- [ ] Bind permits to context and current versions; atomically consume durable
  nonce; perform fresh validity checks immediately before consumption.
- [ ] Verify focused tests and real PostgreSQL races; document same-process limit;
  record evidence and DCO commit.

## Checkpoint 5 — evidence

Files: `db/evidence_repository.py`, `governance/evidence.py`,
`governance/outcome.py`, evidence/concurrency tests.

- [ ] Test two repositories appending concurrently, tampering, tenant isolation,
  evidence-write failure before dispatch and timeout yielding UNKNOWN.
- [ ] Reconcile PR55 DB fork resistance and canonical reconstructive references;
  retain website readers; prohibit secrets in evidence.
- [ ] Verify chain and outcome suites against PostgreSQL; record evidence/commit.

## Checkpoint 6 — transports

Files: `mcp/governance_integration.py`, `mcp/upstream_dispatch.py`, `mcp/server.py`,
`mcp/tools.py`, `dashboard/app.py`, `governance/upstream_executor.py`,
`webhooks/manager.py`, PR84 verifier and transport contract tests.

- [ ] Test REST/MCP/dashboard and existing workers reach context/chokepoint;
  test auth, denied calls, OAuth, cross-tenant, SSRF/DNS and bypass attempts.
- [ ] Adapt controllers to canonical services while retaining PR85 and website APIs.
- [ ] Verify PR84 initialize/list/call checks locally; record evidence/commit.

## Checkpoint 7 — deployment

Files: `dashboard/config.py`, `Dockerfile`, `docker-compose*.yml`, `helm/`,
startup and deployment tests.

- [ ] Test production SQLite rejection, Redis outage, non-root image, health and
  readonly runtime; render Helm multi-replica/PDB/migration job/network policy.
- [ ] Reconcile settings and runtime with explicit PostgreSQL and local secrets.
- [ ] Build/run image; lint/render Helm; record digest/evidence and DCO commit.

## Checkpoint 8 — supply chain

Files: `.github/workflows/`, dependency lockfiles, release regression scripts/tests.

- [ ] Compare PR79 against current builder; retain exact artifact transfer and
  signed tags, add compatible hash-lock/CodeQL/policy checks.
- [ ] Run pinned-action, trust, release provenance and reproducibility checks;
  identify GitHub-only checks without claiming execution; evidence/commit.

## Checkpoint 9 — billing and entitlements

Files: `billing/provider.py`, `billing/stripe_service.py`, `billing/entitlements.py`,
provider event/subscription repositories, forward migration after 0040, website
billing routes and tests.

- [ ] Test unsigned/replayed/provider-colliding events, concurrent failed-event
  retry, payment failure and downgrade preserving DENY.
- [ ] Wrap Stripe with provider-neutral domain/state and commercial capabilities;
  retain checkout/portal UX and no raw payment data persistence.
- [ ] Verify billing/web regression plus migration tests; evidence/commit.

## Checkpoint 10 — deployment activation

Files: `deployment/identity.py`, `deployment/activation.py`, separate issuer
interface, startup settings and activation tests.

- [ ] Test local key binding, valid credential, tampering, wrong org/mode/env/KID,
  expiry, offline operation, rotation and air-gap request/import.
- [ ] Implement canonical signed credential and issuer seam with public keys only
  in runtime; no vendor administrator and no per-request cloud dependency.
- [ ] Verify community remains functional and expiry never disables protection;
  evidence/commit. Live issuer provisioning remains an external activation gate.

## Checkpoint 11 — documentation

Files: README, deployment/runbook, enterprise security, SLA, Trust Center and
`docs/phase1/`.

- [ ] Align claims, commands, tool counts and actual three-root behavior; preserve
  legitimate package/import names rather than blindly rename compatibility APIs.
- [ ] Run documentation/SPDX/trust checks; evidence and DCO commit.

## Checkpoint 12 — integrated verification and freeze

- [ ] Stop feature work. Run full Python 3.11/3.12 where available, coverage,
  frontend lint/tests/build, browser accessibility, audits, Gitleaks, migrations,
  tenant/execution/evidence/MCP attack matrices, Docker and Helm.
- [ ] Inspect combined diff, record skipped/unverified checks and known risks.
- [ ] Freeze one local DCO candidate only when mandatory gates pass; verify clean
  tree and source/artifact identity. Produce directive's seventeen-section report.
- [ ] Stop. No push, merge or Phase 2 implementation.
