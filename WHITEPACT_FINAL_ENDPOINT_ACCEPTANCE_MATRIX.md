# Endpoint acceptance matrix (summary)

**259 routes** remain **CATALOGUED** from audit inventory; this campaign did not re-enumerate every route behavior.

| Subsystem | Depth | Status |
| --- | --- | --- |
| Auth / session / CSRF | Integration tests + browser journey | **INTEGRATION TESTED** |
| API keys / identity gate | Journey + enterprise tests | **INTEGRATION TESTED** |
| Billing / Paddle webhooks | Existing suite + prior sandbox E2E | **LIVE SANDBOX TESTED** (historical) |
| Approvals / execution / evidence | Customer journey + governance tests | **INTEGRATION TESTED** |
| Enterprise IAM (passkey/OAuth/live IdP) | Crypto/unit + mocks | **PARTIAL** — live IdP **BLOCKED** without secrets |
| Public read-only pages | Vitest + a11y CI | **STATICALLY VERIFIED** |

High-risk groups retain fail-closed regression coverage via existing security campaigns; no threshold reduction.
