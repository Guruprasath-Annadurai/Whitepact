# WhitePact — Enterprise staging integration plan (Track A / Track B)

**Established:** 2026-09-28 (repository fetch)  
**Authority:** Evidence-first; no silent merges; Formula Ω∞ disabled on Track A.

## Verified baseline (fetch `origin`)

| Ref | SHA | Notes |
|-----|-----|--------|
| `origin/main` | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` | Includes Gate 3 freeze documentation merge (#122); **not** an integrated RC |
| Tag `v1.3.1` | `894efe30514553f7e0d047a1569a80d36c53a236` | Frozen V1.3.1 enterprise-hardened release (annotated tag) |
| Disposable agent HEAD (Cell B PR) | `62103588cd5c23845481d120873fdb28b250c9ac` | PR #124; exact-head CI run `36466638337` **in progress** at last check |

## Open component inventory

| Component | PR | Branch | Head SHA | CI (exact-head) | Integration status |
|-----------|-----|--------|----------|-----------------|-------------------|
| Stranger onboarding (Cell A) | #121 | `feature/whitepact-launch-cell-a-onboarding-distribution` | `66532671c380` | Py3.11/3.12 **SUCCESS** | **NOT YET QUALIFIED** for integrated RC — owner review required |
| Formula Gate 4 | #123 | `feature/whitepact-formula-gate4-safe-future-envelope` | `0abc94c02781` | Py3.11 **FAILURE** | **BLOCKED** (Track B) |
| Production Cell B | #124 | `cursor/whitepact-launch-cell-b-production-f7a9` | `62103588cd5c` | CI **in progress** (`36466638337`); Gitleaks **SUCCESS** on `6210358` | **INCLUDED** in staging *engineering* scope; merge **not** authorized |
| Enterprise assurance | #125 | `security/whitepact-zero-cost-assurance` | `078534a6df01` | Py3.11/3.12 **SUCCESS** | **NOT YET QUALIFIED** for integrated RC — owner review required |

## Track separation

### Track A — V1 enterprise product

- **Scope:** Released authority engine, dashboard/API, MCP (30 production tools), ops/Helm, onboarding (when merged), assurance docs (when merged), Cell B ops evidence (when merged).
- **Formula Ω∞:** **DISABLED** — must not be enabled via feature flags for Track A staging.
- **Integrated RC:** **Not created** — no temporary integration branch has been merged to `main` without owner approval.

### Track B — Formula Ω∞

- Gate 3: **frozen** on `main` (documentation baseline).
- Gate 4: PR #123 **BLOCKED** until exact-head CI green and independent audit.
- Gates 5–10: **NOT_STARTED** until Gate 4 closure.

## Integration procedure (per component)

1. Verify exact source SHA and successful CI on that SHA.  
2. Review independent audit / P0–P1 findings for that PR.  
3. Diff against staging baseline for migrations, Helm values, dependencies.  
4. **Owner approval** for inclusion.  
5. Integrate only via authorized review (merge or approved integration branch).  
6. Run **exact-integration-SHA** full CI (py3.11, py3.12, security workflows).  
7. Record integrated SHA and dependency graph in `artifacts/enterprise-staging/staging-evidence-manifest.json`.

## Proposed staging integration branch (not created)

Name (if authorized): `staging/track-a-rc-YYYYMMDD` from `v1.3.1` tag **or** from post-merge `main`, cherry-picking or merging approved PRs in dependency order:

1. #125 (assurance, non-runtime)  
2. #124 (Cell B ops — after CI green)  
3. #121 (onboarding — after clean-room validation plan)

**Do not** include #123 until Track B gate remediation is complete.

## Environment dependency

Representative enterprise staging (3 replicas, in-cluster load, Helm rollback, 4h soak) requires **owner-approved** Kubernetes capacity. Disposable Cloud Agent VM: kind **ENVIRONMENT_BLOCKED** (`artifacts/production/kind-bootstrap-diagnostics.json`).
