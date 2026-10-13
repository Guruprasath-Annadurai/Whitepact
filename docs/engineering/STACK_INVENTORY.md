# Engineering stack inventory (live refresh)

**Recorded:** 2026-10-02 (Cursor; verify on GitHub before release)

## Pull requests

| PR | Head branch | Base | State |
|----|-------------|------|-------|
| #130 | `cursor/whitepact-ws2-runtime-authority-f7a9` | `main` | OPEN (M1 runtime; Antigravity qualified) |
| #132 | `cursor/whitepact-ws3-saas-unified-f7a9` | `main` | OPEN (M2) |
| #133 | `cursor/whitepact-ws4-m3-enterprise-f7a9` | `cursor/whitepact-ws3-saas-unified-f7a9` | OPEN (M3) |
| #134 | `cursor/whitepact-ws5-m4-cloud-hardening-f7a9` | `cursor/whitepact-ws4-m3-enterprise-f7a9` | OPEN (M4+M5 candidate) |

## Branch heads (after `git fetch origin`)

| Branch | Commit (2026-10-02 refresh) |
|--------|------------------------------|
| `origin/cursor/whitepact-ws3-saas-unified-f7a9` | `4d511985a17b5c8960f080e2ca96f83872df3e05` |
| `origin/cursor/whitepact-ws4-m3-enterprise-f7a9` | `35d0e6cd92e1670da1f6542098511a74d10f1ead` |
| `origin/cursor/whitepact-ws5-m4-cloud-hardening-f7a9` | `b15e543` (verify after fetch) |
| `origin/cursor/whitepact-m5-integrated-rc-f7a9` | same tip as WS-5 — PR to `main` for full CI |

## Ancestry (expected)

```
main
 └── #130 WS-2 (M1 qualified head 74e091e…)
      └── #132 WS-3 M2
           └── #133 WS-4 M3
                └── #134 WS-5 M4/M5 integrated candidate
```

## M5 integrated candidate

**Branch:** `cursor/whitepact-ws5-m4-cloud-hardening-f7a9` (rename tip to `cursor/whitepact-m5-integrated-rc-f7a9` when CI-green SHA is frozen).

**Tree / commit:** set at exact-head green CI only — do not copy stale SHAs from this doc.

## Local M3 targeted gate (Cursor)

33 tests passed — log: `/opt/cursor/artifacts/m3_exact_head_tests.log`
