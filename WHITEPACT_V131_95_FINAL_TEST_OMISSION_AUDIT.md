# Final omission audit (Phase 0B)

HEAD: `a60adae`

| Cat | Topic | Status | Notes |
|---:|---|---|---|
| A | In-place upgrade | **PASS** | Literal 0061-neutral + historical PG migrations |
| B | Rollback | **PARTIAL** | Supported alembic downgrade paths only |
| C | Backup/restore | **PASS** | Destroy+restore+app boot on populated DB |
| D | Soak | **PARTIAL** | 30m client soak complete; server RSS not captured |
| E | Distributed race | **PARTIAL** | Live 4-worker health barrier PASS + pytest concurrency |
| F | Rolling restart | **PARTIAL** | Live SIGTERM worker under health traffic PASS |
| G | Paddle sandbox | **BLOCKED** | No credentials |
| H | MCP interop | **PARTIAL** | Streamable HTTP pytest; stdio/Cursor BLOCKED |
| I | OpenAPI diff | **PASS** | 0 route delta vs v1.3.0-rc-final |
| J | Legacy | **PARTIAL** | Seams tests |
| K | Auth edge | **PARTIAL** | Pytest subset |
| L | Email | **BLOCKED** | No mail capture |
| M | Limits | **PARTIAL** | Unit tests |
| N | Hostile input | **PARTIAL** | Sample probes |
| O | Proxy | **PARTIAL** | nginx live health PASS; TLS/CSP matrix incomplete |
| P | Container CVE | **PARTIAL** | Trivy scan; inherited base OS CVEs documented |
| Q | Secret leak | **PARTIAL** | Transport boundary pytest |
| R | Artifacts | **PASS** | Wheel build |
| S | K8s multi-replica | **BLOCKED** | No cluster in VM |
| T | Time boundaries | **PARTIAL** | Pytest expiry subset |
| U | Resource exhaustion | **PARTIAL** | Hostile samples + soak errors=0 |
| V | Lost ACK | **PASS** | test_v1_exactly_one_effect |

## WHAT, IF ANYTHING, WAS NOT TESTED?

### TECHNICALLY UNTESTED

- Live approval/API-key/nonce races at HTTP layer across workers (DB races covered in pytest)
- 60m instrumented soak with server RSS/FD/thread capture
- Full TLS reverse-proxy + CORS/CSP/body-limit matrix

### EXTERNALLY BLOCKED

- Paddle sandbox E2E
- Kubernetes multi-replica
- Cursor Desktop MCP stdio
- Email capture provider

### REAL-WORLD VALIDATION REQUIRED

- External customer pilots
- Production regional DR
