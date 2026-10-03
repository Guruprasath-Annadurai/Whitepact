# WhitePact M1–M6 — final engineering master report (Cursor)

**Document status:** ENGINEERING DRAFT — evidence-tracked; **not** Antigravity PASS.  
**Parallel engineering branch:** `cursor/whitepact-m3-m6-parallel-engineering-f7a9` (does not supersede frozen CI heads).

## Frozen qualification heads (exact SHA discipline)

| Gate | PR | Frozen exact CI head | CI | Cursor status |
|------|-----|----------------------|-----|----------------|
| M2 | #132 | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` | 18/18 | **FULL PASS — EXACT-SHA QUALIFIED** |
| M3 | #136 | `620399b7973f5ed058d45218610be228e72d3ed8` | 18/18 `37107348827` | **FULL PASS — EXACT-SHA QUALIFIED** |
| M4 gate | #138 | `bfc4a01` (pending CI) | TBD | `M4_ENGINEERING_IN_PROGRESS` |
| M5 lineage (#137) | #137 | evidence only | — | Rebuild RC after qualified M4 |

Implementation anchor for BYPASS-02: `d13caa114576d95eb20170eb1858387956103ae5` (ancestor of `893d34a`).

## Milestone summary

| Milestone | Independent | Cursor engineering |
|-----------|-------------|-------------------|
| M1 | `BLK-P0-02` / `BLK-P0-03` **VERIFIED_CLOSED** | WS-2 authority suites |
| M2 | **FULL PASS — EXACT-SHA QUALIFIED** @ `893d34a` (Antigravity) | `BLK-P0-06` / BYPASS-01/02 **VERIFIED_CLOSED** |
| M3 | **QUALIFIED** @ `620399b` | P1-02..P1-07 + TOTP replay **VERIFIED_CLOSED** |
| M4 | Not qualified | Successor @ qualified M3; PR **#138** full CI |
| M5 | Not frozen RC | #137 not final until M1→M4 chain |
| M6 | **NOT FROZEN** | `docs/enterprise/M6_DEFECT_REGISTER.md` |

## M4 engineering slices (local)

| Area | Regression anchor |
|------|-------------------|
| PostgreSQL concurrency | `tests/test_auth_real_postgres.py`, `tests/test_phase3_postgres_concurrency.py` |
| SSO/SCIM | `tests/test_scim_and_session_lifecycle.py`, `tests/test_iam_adversarial_matrix.py` |
| Restore | `tests/test_restore_admission_chokepoint.py` |
| Audit / SIEM | `tests/test_siem_audit_export.py`, `tests/test_m4_audit_export_batch_smoke.py` |
| Accessibility | CI `Accessibility (WCAG2AA)` on integrated head |

## Production exclusions

No `terraform apply`, PyPI publish, founder merge, or DNS changes without explicit approval.
