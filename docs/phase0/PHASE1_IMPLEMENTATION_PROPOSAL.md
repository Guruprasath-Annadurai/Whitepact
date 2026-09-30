# Phase 1 — Implementation proposal (revised, founder approval required)

**Status:** PROPOSED — **no Phase 1 code** until founder approves.  
**Billing:** Implement against **Paddle** architecture on `main` / PR #107 — **do not** adopt Stripe because the audit text might mention card processors generically.

## 1. Scope boundaries (unchanged constraints)

- No mass rewrite; no legacy deletion without dependency analysis.
- No PyPI **2.0.0** or mass package rename campaign.
- No cloud **provisioning** during Phase 1 without passing Cloud re-audit.
- **Community stdio** may remain non-governed; **enterprise** must not advertise it as protected.
- **No live authorization bypass** accepted via founder risk sign-off — remove or gate unsupported capabilities from enterprise release scope.

## 2. Integrated release strategy (qualification-first)

**Do not** automatically merge PR #108 → #107 → #128.

### 2.1 Pre-merge qualification checklist (required per branch)

| Step | Action |
|------|--------|
| 1 | Record exact HEAD SHA and green CI run URL for candidate branch |
| 2 | `git merge-base` and `git merge-tree` vs integration target — list **changed in both** paths |
| 3 | Detect duplicate commits on `web/`, `pyproject.toml`, `dashboard/app.py`, migrations |
| 4 | Run full `ci.yml` equivalent locally or on CI for that SHA |
| 5 | Map each merge to **BLK-*** rows it claims to close — no closure without reproduction |

**Observed (Phase 0):**

- `origin/main` vs `cursor/whitepact-v1-combined-rc-f7a9`: merge-base `67380a8`; **many** “changed in both” paths (high conflict risk).
- `cursor/whitepact-v1-combined-rc-f7a9` vs `cursor/whitepact-enterprise-cloud-v1-f7a9`: large diffs (`web/`, infra additions).
- Cloud branch is **descended from** `main` (`81beb3a` merge-base); combined-rc diverged earlier from `67380a8`.

### 2.2 Recommended integration path (proposal — not approved)

1. **Qualify B-main** as baseline with official register reproductions frozen in `release-evidence/<sha>/`.
2. **Qualify B-combined-rc** independently (Paddle, web console) — merge to integration branch only if merge-tree is clean or conflicts are resolved with tests.
3. **Qualify B-cloud** independently — merge only after **BLK-P0-03** / **BLK-P0-02** enterprise closure plan is explicit (cloud must not bypass global authority).
4. Declare **B-integrated-rc** only when one SHA passes CI + Antigravity spot-check of P0 rows.

Alternative: rebuild integration branch from `main` with cherry-picks instead of stacking PR merges if merge-tree risk is unacceptable.

## 3. Phase 1 workstreams (mapped to official BLK findings)

| WS | BLK focus | Work | Acceptance |
|----|-----------|------|------------|
| **WS-1** | BLK-P0-01, P0-05, P3-03 | WhitePact CLI entry → governance platform launcher; document package identity; no 2.0 rename | `whitepact --help` describes WhitePact; PyPI metadata aligned per `PACKAGE_IDENTITY` policy |
| **WS-2** | BLK-P0-03, P0-02 | Wire sovereignty kernel / canonical path to hosted + dashboard dispatch; enterprise profile for stdio | Fail-closed tests; Community profile unchanged by default |
| **WS-3** | BLK-P0-04, P0-06, P1-01 | Single authenticated SaaS surface; approvals actionable; policy management UI | E2E Playwright approve/deny; one session model |
| **WS-4** | BLK-P1-02, P1-04 | Paddle invitation + billing verified in sandbox | E2E on qualified RC SHA with Paddle keys |
| **WS-5** | BLK-P1-03 | SDK governance runtime methods (TS/Python) | Contract tests against `/api/v1/web` governance endpoints |
| **WS-6** | BLK-P1-05, P1-06, P1-07 | Break-glass interrupt, SIEM export, erasure | Adversarial tests + documented data lifecycle |
| **WS-7** | BLK-P1-08, CLOUD-* | LB/origin hardening in Terraform — **plan only** until Cloud re-audit | `terraform validate`; no apply without founder + Antigravity |
| **WS-8** | P2/P3 backlog | SSO/SCIM, a11y, tracing, docs — after P0 closure | Per-row verification in official register |

**Codex:** corporate website only — no dashboard/governance code.

## 4. Phase 1 exit criteria (acceptance)

| # | Criterion |
|---|-----------|
| 1 | All **P0** BLK rows **VERIFIED_CLOSED** or explicitly removed from enterprise scope with fail-closed behavior |
| 2 | **B-integrated-rc** SHA with green CI and `release-evidence` bundle |
| 3 | Antigravity re-validates P0 reproduction matrix on B-integrated-rc |
| 4 | Cloud: remediation for **CLOUD-AG-01..07** + **re-audit** pass before provisioning |
| 5 | No claim of unrestricted stdio in enterprise deployment guides |
| 6 | Paddle billing verified — not mock — for paid plans on RC |

## 5. Founder approval checklist

- [ ] Approve integration strategy (merge vs cherry-pick) after reviewing merge-tree report
- [ ] Approve WS ordering (recommend WS-1 → WS-2 → WS-3 before cloud merge)
- [ ] Approve enterprise vs Community transport policy (WS-2)
- [ ] Authorize Cursor to begin **WS-1** only after Antigravity acknowledges corrected official register
