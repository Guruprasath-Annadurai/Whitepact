# M5 — integrated RC engineering gate

**Branch:** stacked on M4 (`cursor/whitepact-ws5-m4-cloud-hardening-f7a9` or successor)  
**Cursor status:** `M5_INTEGRATED_RC_IN_PROGRESS` — see `docs/engineering/M5_INTEGRATED_RC.md`

## Integrated RC criteria

1. Single stacked SHA spanning M1–M4 engineering branches merged or fast-forward equivalent.
2. Full `ci.yml` green on that SHA (Cursor does not substitute Antigravity sign-off).
3. `tests/test_m5_integrated_rc_gate.py` documents mandatory regression suites.

**Integrated RC SHA:** *declare on GitHub Actions success only.*
