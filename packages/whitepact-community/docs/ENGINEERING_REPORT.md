# Cursor Engineering Report — WHITEPACT A005

**Date:** 3 November 2026 (Asia/Calcutta)  
**Agent:** Cursor Cloud (`bc-9deda1e7-9d60-4755-ab25-1e3cfcbf0e59`)  
**Branch:** `cursor/track-a-community-core-a005-0e59`  
**Final verdict:** `TRACK_A_COMMUNITY_ENGINEERING_READY_FOR_INDEPENDENT_QUALIFICATION`

---

## 1. Baseline and isolation

| Item | Result |
| --- | --- |
| Requested private repo `whitepact-internal` | **Not accessible** (GitHub API 404). Environment linked only to public `Guruprasath-Annadurai/Whitepact`. Access requested via environment setup action. |
| Private PR #251 / #254 / Issue #252 | Unreadable from this environment |
| Public PR #2 head (authoritative accessible candidate) | `19f8d4b6b570d03baa87845867e5f9b268b6d6e6` — verified, 612 files |
| Engineering base | Branched from that exact OSS candidate head |
| Antigravity prior verdict | Treated as `TRACK_A_ENGINEERING_QUALIFIED_LIMITED_SCOPE`; defects independently reproduced |

## 2. Defect reproduction (source-backed)

Confirmed against `19f8d4b`:

1. Broad hatch packaging ships entire `responsibleai` (dashboard/billing/db/auth) in wheel/sdist.
2. Eager `responsibleai/__init__.py` couples imports to sklearn and heavy modules.
3. Empty community subpackage `__init__.py` files break advertised imports.
4. CLI undeclared `rich` dependency.
5. MCP `governance_integration` imports dashboard Prometheus.
6. Tests heavily depend on dashboard/db/auth/stripe.
7. Trust passport/score **files exist** on this head; practical breakage is parent-package coupling (aligns with limited-scope prior finding nuance).

Minimum viable standalone community implementation: **new package**, not a 83-file subset of the monolith.

## 3. Community Core delivered

**Package:** `whitepact-community==0.1.0a1`  
**Layout:** `packages/whitepact-community/`

| Capability | Status |
| --- | --- |
| SDK (`GovernanceClient`) | Pass — local evaluate / execute / deny |
| MCP stdio | Pass — initialize, tools/list (4 tools), authorized + denied calls |
| CLI | Pass — help/version/evaluate/run-local/deny-demo/mcp/enterprise |
| Local governance kernel | Pass — deny-by-default, expiry, revocation, replay, evidence chain |
| Enterprise surfaces | Explicitly unavailable (exit 4), never simulated success |
| Default-deny exporter | Pass — empty allowlist refuses export; replay + tree binding enforced |
| Boundary verifier | Pass — fail-closed on injected `responsibleai/billing/` |

Enterprise `src/responsibleai/**` was **not** gutted or rewritten for cosmetic cleanliness.

## 4. Package qualification

| Check | Result |
| --- | --- |
| Wheel SHA-256 | `9459d769dd98ec032bfa8ccee28a39b25beb163e31b553136b5986ca136c69e6` (26755 bytes) |
| Sdist SHA-256 | `07071bd3e1d8a65635f3a1c0ec769a7e42bfbaab794b4cee8254dafa04a2fc94` (34053 bytes) |
| Twine check | PASSED (wheel + sdist) |
| Archive private-module inclusion | **Zero** (boundary report ok=true) |
| Import closure | Only stdlib + click/pydantic + `whitepact_community` |
| Clean wheel install 3.12 | Pass — ALLOW + DENY demonstrated |
| Clean wheel install 3.11.18 | Pass — ALLOW + DENY demonstrated |
| Pytest 3.11 | 27 passed |
| Pytest 3.12 | 27 passed |
| Fail-closed denylist injection | rc=1 as required |
| Windows | Not executed in this Linux agent environment (declared support via py3-none-any; Antigravity should spot-check if required) |

## 5. CI / DCO / supply chain

| Item | Status |
| --- | --- |
| GitHub Actions (public PR #2 recent) | CI success; Gitleaks success; DCO success; **Dependency Review failure** (see receipts). Not universally “blocked before runner assignment” on the accessible public PR — document accurately. |
| Private internal CI | Unknown (repo inaccessible) |
| This branch CI | Will run only after push to an accessible remote |
| DCO for Cursor commits | Signed-off-by matches Cursor Agent identity only (no forged Founder trailer) |
| minimatch / OTel-ADK / NLTK | Preserved as open dependency blockers on the monolith extras; Community Core does **not** depend on them |
| SBOM | CycloneDX + SPDX JSON under `docs/` (runtime-focused) |
| Publication allowlist | Remains empty; exporter default-deny intact |
| Public upload / merge | **Not performed** |

## 6. Historical disclosure / IP

- First 13-document register: retained as **H** (Security/Legal).
- Second 13-path register: **U** unless new evidence.
- Founder IP matrix updated for new package architecture (`docs/FOUNDER_IP_MATRIX.md`).
- Narrow recommended community manifest listed therein.
- Protected allowlist **not** altered.

## 7. Unresolved / blocked

1. **No write access to `whitepact-internal`** — cannot open the required *private* draft PR on the authoritative private forge from this environment.
2. Public repository writes remain prohibited by A005 absolute rules.
3. Live Founder release authorization intentionally not configured.
4. Monolith packaging defects in `rai-governance-platform` remain (by design — community is a separate package).

## 8. Antigravity handoff

Follow `docs/ANTIGRAVITY_AUDIT_INSTRUCTIONS.md` against the exact candidate SHA of this branch after it lands on an accessible remote.

## Verdict justification

Community prototype **builds, installs (3.11/3.12), and performs advertised local functions** (genuine ALLOW operation + demonstrable DENY), with a **clean package boundary** and fail-closed private-module regression. Therefore:

### `TRACK_A_COMMUNITY_ENGINEERING_READY_FOR_INDEPENDENT_QUALIFICATION`

Caveat for auditors: private-forge PR delivery is blocked until `whitepact-internal` access is granted; do not treat public-main documentation repo presence as Founder publication approval.
