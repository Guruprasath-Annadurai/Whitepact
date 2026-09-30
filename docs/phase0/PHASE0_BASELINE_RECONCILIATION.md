# Phase 0 — Baseline reconciliation

Date: **2026-09-30** (UTC). Repository: `Guruprasath-Annadurai/Whitepact`.

## 1. Antigravity reported SHA `3c955c7`

| Check | Result |
|-------|--------|
| `git cat-file -t 3c955c7` (local, all refs) | **unknown revision** |
| `git ls-remote origin 3c955c7` | **no object** |
| `git log --all --oneline \| rg 3c955c7` | **no match** |
| Full 40-character SHA | **not recoverable** from this repository |
| Tree identity for `3c955c7` | **not available** |

**Conclusion:** The audit’s cited SHA cannot be bound to any commit in `origin` or local branches. Phase 0 cannot claim “reproduced on Antigravity baseline” until the founder or Antigravity supplies the **full commit hash**, **branch name**, or **audit artifact** (PDF/markdown) checked into the repo or attached to the run.

### Nearest auditable SHAs (for substitution only — not equivalent to `3c955c7`)

| Label | Full SHA | Tree SHA | Notes |
|-------|----------|----------|--------|
| `origin/main` (merged product line) | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` | `bc0b92120500d1ffc1a1875ae64be45adb67929c` | PyPI project version **1.3.1** in `pyproject.toml`; Formula Gate 3 docs merge (#122) |
| `origin/cursor/whitepact-enterprise-cloud-v1-f7a9` (PR #128) | `7386fadf8c88dc78044e9e7aceef9b655f6496b2` | *(compute at qualification)* | WhitePact Cloud control plane; **not merged**; qualified CI on earlier heads |
| `origin/cursor/whitepact-v1-combined-rc-f7a9` (PR #107) | `6190cc7a9874d0ad0778c2b5ae3179fbc978aa16` | *(compute at qualification)* | Combined RC + Paddle closure; **not merged** |
| `origin/release/whitepact-v1-rc` | `683d1c382ee2fe4a37c2335f201029d47e8471ae` | *(compute at qualification)* | Release-line integration; **not** `main` |
| `origin/codex/enterprise-readiness` | `2568db12bb553d6269e38178647236571dd2655a` | *(compute at qualification)* | Codex enterprise-readiness lane; dependency/license fixes; **not** integrated RC |
| Frozen release evidence (campaign) | `c8ea64be63ac7cc1445a82577376eb3700676366` | per `release-evidence/c8ea64be.../` | Historical RC evidence folder; **not** current `main` tip |

**Recommended audit baseline for Phase 1 planning:** treat **`origin/main` @ `81beb3a`** as **published integration truth** and **`7386fad` (PR #128)** as **required integration delta** for enterprise cloud—until a single merge-qualified RC branch is declared by the founder.

## 2. Integrated release candidate (truth table)

There is **no single fully integrated enterprise RC** at one SHA today. The product is a **composition** of merged `main`, open PR stacks, unpublished local work, and evidence folders.

| Capability | On `main`? | Primary delivery | Published package |
|------------|------------|------------------|-------------------|
| Core governance / MCP / dashboard | **Yes** | `main` | PyPI `rai-governance-platform` **1.3.1** (repo); historical pins may lag |
| DNS egress / rebinding guard (`net/egress.py`) | **Yes** | `main` | In tree; see reconciliation ledger on `main` |
| Phase-1 canonical authority wiring (Heart → live path) | **Partial / gap** | `main` code + `docs/phase1/RELEASE_SECURITY_GATE.md` | N/A |
| WhitePact Cloud (grants, offboarding, Access JWT) | **No** | PR **#128** only | N/A |
| Combined RC + Paddle env closure | **No** | PR **#107** | N/A |
| Launch Cell B production baseline | **No** | PR **#124** | N/A |
| IoT / Device Bridge execution surface | **No** | Absent; see `docs/architecture/IOT_DEVICE_BRIDGE_HARDENING_AUDIT.md` | N/A |
| Public corporate website | **Codex branches** | `origin/codex/*` | Separate from product RC |

**Stage 1 — Development Only** is **consistent** with this picture: CI can be green on slices, but **live staging, canonical execution closure, and PR integration** are not one deployable enterprise product.

## 3. Overlap with WhitePact Cloud pre-staging audit

| Cloud audit theme | Cloud status (PR #128) | Enterprise audit overlap (register IDs) |
|-------------------|------------------------|----------------------------------------|
| Grant verify + `FOR UPDATE` consume | VERIFIED (unit/CI) | AG-EPR-015, AG-EPR-016 |
| Enrollment vs issuance separation | VERIFIED | AG-EPR-017 |
| Offboarding local fail-closed | VERIFIED (local) | AG-EPR-018 |
| Privileged executor default off | IMPLEMENTED_NOT_DEPLOYED | AG-EPR-019 |
| No `terraform apply` / live JWKS / IdP revoke | OWNER gated | AG-EPR-020, AG-EPR-021 |
| Antigravity independent cloud review | **NOT STARTED** | AG-EPR-024 |

Cloud closure **does not** resolve hosted canonical authority, stdio enterprise posture, or RC branch fragmentation on `main`.

## 4. Documentation drift warning

`docs/phase1/RELEASE_SECURITY_GATE.md` on `main` still lists **OPEN P0** items (canonical authority, upstream canonical authorization, stale approval resume). Some items may be **partially mitigated** in code after that document was written—see [PHASE0_P0_REPRODUCTION_LOG.md](./PHASE0_P0_REPRODUCTION_LOG.md). **Do not** mark those findings resolved without Antigravity re-run on the declared baseline SHA.
