# WhitePact v1.3.1 — Phase 0C final blocker register

| ID | Item | Class | Notes |
|----|------|-------|-------|
| C-01 | Container CRITICAL CVEs (pre-patch) | **P0 — CLOSED** | 3× `perl-base`; fixed via Dockerfile `apt-get upgrade`; after-scan **0 CRITICAL** |
| C-02 | Residual HIGH OS CVEs | **P2** | 52 HIGH / 81 MEDIUM on patched image; mostly inherited Debian; assessed in container reports |
| C-03 | Server-instrumented 30m soak | **P1 — CLOSED** | 11517 requests, 0 errors; RSS +3% aggregate; see `WHITEPACT_V131_95_FINAL_INSTRUMENTED_SOAK.md` |
| C-04 | HTTP multi-worker concurrency | **P1 — CLOSED** | 4-worker barrier: 1×200 / 15×409 on approval resolve; `test_v1_two_process_replicas.py` **PASS** for execute/API-key/rate-limit |
| C-05 | MCP STDIO interop | **P1 — CLOSED** | Real `mcp` `stdio_client` + 30 tools — `WHITEPACT_V131_95_FINAL_MCP_STDIO_INTEROP.md` |
| C-06 | Lost ACK regression | **P1 — CLOSED** | `test_v1_exactly_one_effect.py` **PASS** |
| C-07 | Governance security regression | **P1 — CLOSED** | Targeted pytest batch (trust, concurrency, MCP registry) **PASS** |
| E-01 | Paddle sandbox E2E | **EXTERNALLY_BLOCKED** | No credentials on final SHA |
| E-02 | Kubernetes multi-replica | **EXTERNALLY_BLOCKED** | No cluster in closure VM |
| E-03 | Email capture (Mailpit) | **EXTERNALLY_BLOCKED** | No local mail sink configured |
| E-04 | Real customer pilots | **REAL_WORLD_VALIDATION** | Not available in this phase |
| E-05 | Production regional infra / months-in-prod | **FUTURE_PRODUCTION_PHASE** | Post-freeze launch readiness |

**No open P0 software defects** identified at Phase 0C completion on branch `cursor/v1.3.1-final-enterprise-hardening`.
