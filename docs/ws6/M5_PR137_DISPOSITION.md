# PR #137 disposition (obsolete for authoritative M5)

**Verdict:** Do **not** merge PR #137 head (`origin/cursor/whitepact-m5-integrated-rc-f7a9` pre-rebase).

## Why excluded

Compared to qualified M4 `52d9b3c`, the legacy #137 branch:

- Removes M4 hostile/assault suites (`test_m4_*` campaign files)
- Removes `test_totp_matched_counter_security.py` (qualified M3 remediation)
- Diverges enterprise identity service in ways not rebased on M4

## Authoritative path

1. Branch `cursor/whitepact-m5-integrated-rc-f7a9` reset to **qualified M4** `52d9b3c`
2. Cherry-pick/merge validated prep `635b812` only
3. New exact-head RC after full CI green

## Optional salvage

If specific commits on old #137 are needed, cherry-pick **individually** with full regression — never wholesale merge.
