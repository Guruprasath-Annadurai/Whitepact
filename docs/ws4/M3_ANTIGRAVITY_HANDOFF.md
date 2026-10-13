# M3 — Antigravity handoff (Cursor engineering)

**Cursor status:** `ENGINEERING_IN_PROGRESS — EXACT_HEAD_CI_PENDING` (post TOTP remediation)  
**Do not claim independent M3 PASS.**

## M3-P1-TOTP-REPLAY-01 (retest focus)

| Item | Detail |
|------|--------|
| Prior CI candidate | `656de8a5caaa8c8869017a121f9437860061475b` (superseded; not independently qualified) |
| Reproduction | Confirm/verify at end of counter `N`, reuse same OTP in counter `N+1` with `valid_window=1` |
| Root cause | `last_timestep` tracked server wall counter, not matched OTP counter |
| Remediation | `verify_code_with_counter` + atomic `last_timestep < matched` UPDATE |
| Tests | `tests/test_totp_matched_counter_security.py` (boundary, confirm→verify, verify→verify, concurrency) |
| Incident doc | `docs/ws4/M3_TOTP_REPLAY_INCIDENT.md` |

**Ask Antigravity:** attempt cross-window and concurrent replay against the new exact-head SHA after full CI is green.

## Frozen M3 WS-4 head (stacked PR #133)

| Field | Value |
|-------|--------|
| Branch | `cursor/whitepact-ws4-m3-enterprise-f7a9` |
| Commit | `c281954a3c49094df7a7b19044c3035ef40f54c8` |
| Tree | `98ace416a427c70539b50db808d9b92ba3cc5c14` |
| Qualified M2 ancestor | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` |

## Exact-head full CI gate

Full `ci.yml` matrix runs on PR **#135** integrated head (must include M3 ancestor above).  
Record workflow run ID on `da9bfc9` (or successor green SHA) before marking **`M3_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`**.

## Targeted evidence

| Scope | Anchor |
|-------|--------|
| M3 adversarial campaign | `tests/test_m3_adversarial_security_campaign.py` — 14/14 local |
| P1-02..P1-07 | See `docs/ws4/M3_ENGINEERING_STATUS.md` |

Log: `/opt/cursor/artifacts/m3_adversarial_campaign.log`

## Known limitations

- Stacked PR #133 does not target `main`; integrated PR #135 is the authoritative full CI gate.
- Cloud provisioning remains **BLOCKED**.
