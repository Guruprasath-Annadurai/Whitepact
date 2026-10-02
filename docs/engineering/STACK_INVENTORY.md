# Engineering stack inventory (live refresh)

**Recorded:** 2026-10-02 (Cursor; verify on GitHub before release)

## Pull requests

| PR | Head branch | Base | State |
|----|-------------|------|-------|
| #130 | `cursor/whitepact-ws2-runtime-authority-f7a9` | `main` | OPEN (M1 runtime; Antigravity qualified) |
| #132 | `cursor/whitepact-ws3-saas-unified-f7a9` | `main` | OPEN (M2 qualified @ `893d34a`) |
| #133 | `cursor/whitepact-ws4-m3-enterprise-f7a9` | `cursor/whitepact-ws3-saas-unified-f7a9` | OPEN (M3) |
| #134 | `cursor/whitepact-ws5-m4-cloud-hardening-f7a9` | `cursor/whitepact-ws4-m3-enterprise-f7a9` | OPEN (M4) |
| #135 | `cursor/whitepact-m5-integrated-rc-f7a9` | `main` | OPEN (full CI gate) |

## Branch heads (verify after `git fetch origin`)

| Branch | Commit |
|--------|--------|
| `origin/cursor/whitepact-ws3-saas-unified-f7a9` | `893d34a` (frozen M2) |
| `origin/cursor/whitepact-ws4-m3-enterprise-f7a9` | `c281954` (M3) |
| `origin/cursor/whitepact-m5-integrated-rc-f7a9` | verify on PR #135 |

## Ancestry (expected)

```
main
 └── #130 WS-2 (M1)
      └── #132 WS-3 M2 @ 893d34a
           └── #133 WS-4 M3 @ c281954
                └── #134 WS-5 M4
                     └── #135 M5 integrated → main (full CI)
```
