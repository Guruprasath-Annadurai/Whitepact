# Cloud staging known limitations

| Limitation | Severity | Notes |
|------------|----------|-------|
| No live environment yet | — | Owner Gate 1 not approved |
| `ORIGIN-LIVE-BYPASS` | P2 | Static only until staging drill |
| SBOM for deployed image | P3 | Generate at container build |
| Email provider | P2/P3 | May block full signup journey until SMTP configured |
| Single SaaS node | Accepted | Staging cost; HA documented for production |
| External uptime | Pending | Requires approved staging hostname (Gate 2) |
| GCP DR | Out of scope | Per architecture lock |
| Production apex DNS | Untouched | `whitepact.com` not modified |
| Paddle production | Disabled | Sandbox only |
| PyPI/npm publish | Not performed | |
