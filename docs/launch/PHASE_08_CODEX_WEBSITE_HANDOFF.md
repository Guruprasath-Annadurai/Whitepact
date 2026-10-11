# Phase 8 — Codex website handoff

**Codex owns corporate website implementation. This branch does not edit website source.**

## Frozen references

Do not rewrite these commits. Build forward from them if the owner asks for a website change.

| Commit | Subject |
|--------|---------|
| `fe3ee6c61a3cc2b17c469f37b30d5ea73b62881e` | Website final successor |
| `9c43229fa3ce91bdc975240deaa8b0e568871325` | Pin repository quickstart to qualified source |
| `ce9bd2cc11a6a0292e1085df4cd4bfee05b7dfb3` | Stabilize public navigation after skip-link focus |
| `c9622a2539f20314205e1c30a0f4b8de3927b8f4` | Phase 4 launch integration contracts |

PR #168 (`ae9e59057bdc69bd7681275db0daef7b815241e2` on `cursor/whitepact-global-ecosystem-readiness-ed96`) is **not** contained in `0cdef394`. Do not drop it and do not republish packages from it.

The integrated RC `0cdef394` already contains the website merge `35488a68e587df2adfdb1ceaad44001faca524a4` and later website commits through `9c43229`. Treat that website tree as qualified history inside the RC, not as a new Codex task.

## Product facts the site may state

- Product name: WhitePact.
- Python distribution name: `rai-governance-platform`.
- Declared version string in the RC: `1.3.1`.
- Git tag `v1.3.1` points at `894efe30514553f7e0d047a1569a80d36c53a236`, which is not `0cdef394`.
- Install from PyPI only for the already published distribution. Do not announce a new publish.
- Install shape: `pip install "rai-governance-platform[dashboard,postgres]"`.
- CLI entry: `whitepact`. Do not document `pip install whitepact`.
- The agent may plan freely. Consequential execution requires the independent authority path: identity, authority, policy, approval where required, short-lived grant, isolated execution, evidence, audit, revocation.
- Authentication is not authority.

## The site must not state

- That staging or production is live.
- A customer, investor, partner, or certification that is not in an owner-approved source.
- An uptime percentage, including the proposed 99.9% figure, which is not approved.
- That Antigravity passed the successor branch.
- That paid plans are available.
- That the memory-scope fix has an independent pass before Antigravity says so.

## Acceptance tests for a future Codex change

1. Skip link and mobile navigation still match the qualified browser tests.
2. Every install command uses `rai-governance-platform`.
3. No page offers a price, a trial, or a status of "generally available" until the owner decisions in Phase 7 and Phase 10 are recorded.
4. Security contact matches `SECURITY.md`.
5. Rollback is redeploy of the previous static artifact. Do not point DNS at an unreleased host as part of content work.

## Accessibility and SEO

Keep the existing WCAG2AA job green. One passed job on `0cdef394` is not a new audit of later copy. Titles and descriptions must describe governance of agent actions, not a claim of certification.

## Gate

CONDITIONAL as a handoff. Website deployment is NOT EXECUTED by Cursor.
