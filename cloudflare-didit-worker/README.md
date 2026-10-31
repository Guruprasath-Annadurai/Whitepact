# WhitePact — Cloudflare Workers + Neon Didit foundation (LOCAL ONLY)

**Status:** design + local implementation + adversarial tests.  
**Not provisioned.** No live Cloudflare Worker, Neon project, DNS, or Didit destination was created by this work.

## What this package is

Smallest safe public HTTPS ingress layer for Didit V3 webhooks:

- `X-Signature-V2` full-payload HMAC (rejects Simple-only)
- Canonical JSON byte-compatible with frozen PR #244 Python `didit.canonical`
- Timestamp window ±300s + header↔body bind
- Neon-oriented durable schema with idempotent `(provider, event_id)`
- **No HTTP 2xx until durable commit succeeds** (rejects Didit sample “ACK then async” pattern)
- Fail-closed on proof/tenant/replay errors; **503** when store unavailable (provider retries)
- No raw ID documents / biometric media in durable rows or logs

## Run tests (no cloud credentials)

```bash
cd cloudflare-didit-worker
npm test
npm run crosscheck:python
```

Requires Node ≥ 20 and Python 3 (stdlib only for cross-check).

## Branch / worktree

This package lives on an isolated worktree branch (unpushed by policy for this M13 task). See the feasibility report for path and SHA.
