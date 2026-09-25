# Final omission audit (Phase 0B)

HEAD: `c9e0892c4e536bf1a631e833dba46e29e80785bc`

| Cat | Topic | Status | Notes |
|---:|---|---|---|
| A | In-place upgrade | **PARTIAL** | Historical PG migrations + 0061 backup restore |
| B | Rollback | **PARTIAL** | Supported alembic downgrade paths only |
| C | Backup/restore | **PASS** | Destroy+restore manifest match |
| D | Soak | **PARTIAL** | 30m client soak: 8763 samples, 0 errors, p95 6.9ms (no server RSS) |
| E | Distributed race | **PARTIAL** | Pytest only |
| F | Rolling restart | **BLOCKED** | No live multi-worker harness |
| G | Paddle sandbox | **BLOCKED** | No credentials |
| H | MCP interop | **PARTIAL** | Streamable HTTP pytest; stdio BLOCKED |
| I | OpenAPI diff | **PASS** | 245 paths; 0 removed/added vs v1.3.0-rc-final |
| J | Legacy | **PARTIAL** | Seams tests |
| K | Auth edge | **PARTIAL** | Pytest subset |
| L | Email | **BLOCKED** | No mail capture |
| M | Limits | **PARTIAL** | Unit tests |
| N | Hostile input | **PARTIAL** | Sample probes |
| O | Proxy | **PARTIAL/BLOCKED** | nginx not fully exercised |
| P | Container CVE | **BLOCKED/PARTIAL** | Trivy if installed |
| Q | Secret leak | **PARTIAL** |  |
| R | Artifacts | **PASS** | Wheel build |
| S | K8s multi-replica | **BLOCKED** |  |
| T | Time boundaries | **PARTIAL** |  |
| U | Resource exhaustion | **PARTIAL** |  |
| V | Lost ACK | **PASS** | test_v1_exactly_one_effect |

## WHAT, IF ANYTHING, WAS NOT TESTED?

### TECHNICALLY UNTESTED

- Live 4-worker rolling restart under load
- 30–60m instrumented server-side leak watch (unless soak job completed)
- Full populated backup with evidence/approvals/billing (minimal seed only)

### EXTERNALLY BLOCKED

- Paddle sandbox E2E
- Kubernetes multi-replica
- Cursor Desktop MCP stdio
- Email capture provider

### REAL-WORLD VALIDATION REQUIRED

- External customer pilots
- Production regional DR
