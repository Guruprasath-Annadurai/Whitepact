# Long-run soak (addendum)

**Label:** SHORT SOAK — **120s** client loop (not production certification)

Target: `http://127.0.0.1:18765/api/health`

| metric | value |
|---|---:|
| samples | 469 |
| errors | 0 |
| p95 latency (ms) | 7.10 |
| client RSS delta (KB) | 2116 |

Worker RSS / FD / DB pool / Redis: **NOT MONITORED** in this harness (requires instrumented server process). Mark **PARTIAL**.
