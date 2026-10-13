# M3-P1-TOTP-REPLAY-01 — TOTP cross-window replay

**Status:** `ENGINEERING_FIXED — INDEPENDENT RETEST REQUIRED`  
**Severity:** P1  
**Superseded M3 candidate (CI-only):** `656de8a5caaa8c8869017a121f9437860061475b` (PR #136)

## What happened

TOTP verification could accept the same OTP twice when the server crossed a 30-second
window after the first acceptance. `valid_window=1` kept the prior window’s code
cryptographically valid while replay state keyed only on the **current** server
counter (`int(time.time()) // 30`), not the **matched** RFC 6238 counter.

## Root cause

- `confirm_totp` / `verify_totp` stored `last_timestep` from wall clock at commit time.
- Replay guard compared `last_timestep` to the **current** server counter only when
  `abs(delta) == 0`, so after rollover the guard was skipped while `mfa.verify_code`
  still accepted the prior window’s OTP.

## Why CI passed on `656de8a`

Targeted tests modeled same-timestep replay or manually aligned `last_timestep` to
the verify window. They did not assert cross-window reuse of an already-consumed
matched counter.

## Permanent fix

1. `mfa.verify_code_with_counter()` — returns the matched 30s counter (±1 window).
2. `confirm_totp` / `verify_totp` — conditional `UPDATE` requiring
   `last_timestep IS NULL OR last_timestep < matched_counter` (atomic CAS).
3. Deterministic boundary + concurrency regressions in
   `tests/test_totp_matched_counter_security.py`.

## Skew tolerance

WhitePact retains **±1** TOTP window (`DEFAULT_TOTP_VALID_WINDOW = 1`). Replay safety
uses **monotonic counter consumption**: once counter `C` is accepted, any later
verification must match a counter `C' > last_timestep`; older tolerated-window codes
are rejected after a newer counter is consumed.

## Evidence

- Regression suite: `tests/test_totp_matched_counter_security.py`
- Artifact: `/opt/cursor/artifacts/m3_qualification_gate_620399b_ci.json`
- Gate CI: **18/18** @ `620399b` — run `37107348827`
