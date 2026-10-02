# M3 — Antigravity handoff (Cursor engineering)

**Cursor status:** `M3_ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING`  
**Do not claim independent M3 PASS.**

## Frozen M3 WS-4 head (stacked PR #133)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-ws4-m3-enterprise-f7a9` |
| Commit | `6979a518ee7194dc539f5417384df2f776efd937` |
| Tree | `fccf3ada3e173a059095f29bbed83656b3267c2c` |
| Qualified M2 ancestor | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` |

## Exact-head full CI gate

Full `ci.yml` runs on PR targeting `main` at **exact commit `6979a51`** (`cursor/whitepact-m3-qualification-gate-f7a9`).  
See `docs/ws4/M3_QUALIFICATION_GATE.md`. **Do not** use history-rewritten integrated heads as the M3 freeze SHA.

Record workflow run ID on **`6979a51`** before marking **`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`**.

## Targeted evidence

| Scope | Anchor |
|-------|--------|
| M3 adversarial campaign | `tests/test_m3_adversarial_security_campaign.py` — 14/14 local |
| P1-02..P1-07 | See `docs/ws4/M3_ENGINEERING_STATUS.md` |

Log: `/opt/cursor/artifacts/m3_adversarial_campaign.log`

## Known limitations

- Stacked PR #133 does not target `main`; use qualification gate branch for full CI on `6979a51`.
- PR #135 (rewritten integrated) is engineering evidence only — not M3/M5 freeze.
- Cloud provisioning remains **BLOCKED**.
