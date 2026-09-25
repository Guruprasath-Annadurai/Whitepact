# Proxy boundary (Phase 0B)

**Verdict:** **PASS** — nginx → `http://127.0.0.1:18765` with forwarded headers.

Config: `/opt/cursor/artifacts/v131_95_phase0b/nginx_wp_live.conf`

```json
[
  {
    "case": "health_via_proxy",
    "status": 200,
    "body_snip": "{\"status\":\"healthy\",\"version\":\"1.3.0\",\"uptime_seconds\":27723.4,\"timestamp\":\"2026-09-25T08:01:52.497356+00:00\",\"checks\":{\"database\":\"ok\",\"db_backend\":\"sqlite\",\"rate_limit_backend\":\"memory\",\"otel\":\"disa"
  },
  {
    "case": "forwarded_proto",
    "status": 200,
    "body_snip": "{\"status\":\"healthy\",\"version\":\"1.3.0\",\"uptime_seconds\":27723.4,\"timestamp\":\"2026-09-25T08:01:52.503817+00:00\",\"checks\":{\"database\":\"ok\",\"db_backend\":\"sqlite\",\"rate_limit_backend\":\"memory\",\"otel\":\"disa"
  }
]
```

TLS termination, CORS/CSP exhaustive matrix, and body-limit characterization remain **PARTIAL**.
