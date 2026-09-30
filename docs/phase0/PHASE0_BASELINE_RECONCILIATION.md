# Phase 0 — Baseline reconciliation (corrected)

Date: **2026-09-30**. Phase 0 HEAD: `23d47cadf06a7012d0d2ef95fbc6ff7300120d27` (PR #100).

## 1. Antigravity reported audit SHA (recovered)

| Field | Value |
|-------|--------|
| **Recovered full SHA (founder-supplied)** | `3c955c76e2ae63ef428a4e3e32b9e87cd4ecc6ad` |
| Present on `origin` (2026-09-30 fetch) | **No** — `git fetch` reports `not our ref` |
| Reproduce Antigravity’s original checkout | **Not claimed** until object is available on a reachable remote |
| Official findings | Preserved in [ANTIGRAVITY_GLOBAL_ENTERPRISE_AUDIT_2026-09-30.md](./ANTIGRAVITY_GLOBAL_ENTERPRISE_AUDIT_2026-09-30.md) |

## 1b. Antigravity Phase 0 documentation baseline

| Field | Value |
|-------|--------|
| **Evaluated Phase 0 docs SHA** | `6746394e19559a176a24ca968349e27808a09676` |
| Role | Historical documentation baseline for Antigravity conditional PASS — not the WS-1 code baseline |
| WS-1 code baseline | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` (`origin/main`) |

Reproduction uses **B-main**, **B-combined-rc**, **B-cloud**, and **B-published** — see [PHASE0_REPRODUCTION_MATRIX.md](./PHASE0_REPRODUCTION_MATRIX.md).

## 2. Verifiable SHAs

| Label | Full SHA | Notes |
|-------|----------|--------|
| B-main | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` | `origin/main`; version **1.3.1** |
| B-combined-rc | `6190cc7a9874d0ad0778c2b5ae3179fbc978aa16` | PR #107 |
| B-cloud | `7386fadf8c88dc78044e9e7aceef9b655f6496b2` | PR #128 |
| B-phase0-docs | `23d47cadf06a7012d0d2ef95fbc6ff7300120d27` | Phase 0 documentation on PR #100 |

## 3. Integrated release candidate

**Not declared.** Product truth is split across B-main and unmerged PRs. Phase 1 proposes qualification-first integration — **no automatic PR merges**.

## 4. Cloud independent audit status (corrected)

| Previous (incorrect) | Corrected |
|--------------------|-----------|
| Antigravity Cloud review “NOT STARTED” | **Submitted** — verdict **BLOCKED — UNSAFE TO PROVISION** |

Register: [ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md](./ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md). **Re-audit required** after remediation.

## 5. Implementation ownership (corrected)

| Owner | Scope |
|-------|--------|
| **Cursor** | Entire product application (React SaaS dashboard, approvals, policies, team management, backend, SDKs, runtime enforcement, infrastructure) |
| **Codex** | Official public corporate website only |
| **Antigravity** | Independent verification |
