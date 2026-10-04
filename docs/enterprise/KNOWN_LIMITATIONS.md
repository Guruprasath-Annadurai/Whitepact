# Known limitations (engineering)

| Area | Limitation | Status |
|------|------------|--------|
| Cloud | Terraform validate/plan only; no production resources | `ACCEPTED LIMITATION` |
| Origin protection | Static policy tests; live bypass drill deferred | `ACCEPTED LIMITATION` |
| Worker lease contention | Documented in M4 P2/P3 disposition | `ACCEPTED LIMITATION` |
| Legacy domain overhang | Marketing/DNS not in scope for M5 prep | `DEFERRED — NON-BLOCKING` |
| PG test battery | Requires isolated PostgreSQL in dev/CI | Operational assumption |
| Paddle | Sandbox tests only; production billing not activated | Policy |
| OTEL | No-op safe; full SaaS trace backend not required for RC | Engineering |
| Runbooks | Several marked **draft** in operator index | `OPEN` for M6 polish |
| M5 | Qualified @ `46685fa` | Antigravity PASS |
| M6 | Independent qualification pending | Engineering RC on M6 branch |
| SBOM | Generator not recorded for M6 RC | `DEFERRED — NON-BLOCKING` |

Performance limits and unsupported third-party integrations are tracked in `docs/enterprise/M6_DEFECT_REGISTER.md`.
