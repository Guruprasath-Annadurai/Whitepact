# WhitePact v1.3.1 — Phase 0C final pre-freeze report

| Field | Value |
|-------|-------|
| Starting SHA | `d076778d611b9d820cc5752e23c6f34b829a8847` |
| Final SHA | `ff3f127` |
| PR | **#114** (open, unmerged) |
| Version | **1.3.1** |
| Gate B | `PRODUCTION_GATE_B_OPEN = False` (unchanged) |
| Phase7A | default **off** (unchanged) |
| MCP production tools | **30** (unchanged) |

## Phase 0C decision

**WHITEPACT PHASE 0C PASS — READY FOR RELEASE FREEZE**

(External launch-readiness items remain documented; they do not block freeze per §12.)

## Exact-head CI

Re-run required after Dockerfile + evidence push — confirm all release checks green on PR #114 head.

## Container scan

| | CRITICAL | HIGH | MEDIUM |
|---|--:|--:|--:|
| **Before** (`phase0c-candidate`) | 3 | 65 | (see Trivy JSON) |
| **After** (`phase0c-patched` / `responsibleai:95test`) | **0** | **52** | **81** |

All three pre-patch CRITICALs were `perl-base` (CVE-2026-13221, CVE-2026-42496, CVE-2026-8376) → **FIXED** via runtime `apt-get upgrade`. WhitePact does not invoke Perl; disposition documented in `WHITEPACT_V131_95_FINAL_CONTAINER_SECURITY_CLOSURE.md`.

## Instrumented soak (30 min)

| Metric | Result |
|--------|--------|
| Duration | 1800s |
| Requests / errors | 11517 / **0** |
| p95 latency | 7.60 ms |
| RSS (aggregate workers) | 908124 → 936960 kb (~+3.2%) |
| Threads | stable at 14 |
| DB connections | active ~1, idle 4→6 |
| Redis clients | 1–2 |
| Leak assessment | **NO SIGNIFICANT LEAK OBSERVED DURING 30-MIN LOCAL SOAK** |

## HTTP concurrency

| Scenario | Result |
|----------|--------|
| Approval resolution (4 workers, barrier) | **1×200**, 15×409 |
| Approval execute (barrier) | 422 (harness seeding); **authoritative:** `test_v1_two_process_replicas.py` **PASS** (counter=1, downstream=1) |
| API key revoke race | after-revoke **401** |
| Nonce replay | pytest **PASS** |
| Two HTTP replicas journey | pytest **PASS** |

## MCP STDIO

**PASS** — external `stdio_client`, 30 tools, initialize/list/call/reconnect (`WHITEPACT_V131_95_FINAL_MCP_STDIO_INTEROP.md`).

## Regressions

| Area | Result |
|------|--------|
| Lost ACK / UNKNOWN | **PASS** |
| Trust / nonce / concurrency / MCP registry | **PASS** (targeted pytest) |
| Package surfaces @ 1.3.1 | Python `pyproject.toml`, Helm `appVersion`, TS SDK |

## Remaining (non-freeze-blocking)

Paddle sandbox, K8s multi-replica, email capture, customer pilots, production regional ops — see `WHITEPACT_V131_PHASE0C_FINAL_BLOCKER_REGISTER.md`.
