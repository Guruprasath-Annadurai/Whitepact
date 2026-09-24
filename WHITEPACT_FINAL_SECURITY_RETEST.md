# Security retest (campaign scope)

| Campaign | Status |
| --- | --- |
| MCP malformed args → no process crash | **PASS** (unit) |
| Trust outage → `passes=false`, `trust_status=UNKNOWN` | **PASS** (unit) |
| Tenant isolation / webhook replay / CSRF | **PASS** (existing suite; full run via CI) |
| Gitleaks / CodeQL / Dependency review | **NOT RE-RUN LOCALLY** — rely on GitHub workflows on PR |

No fail-closed behavior weakened for UX tests.
