# Sovereign SDKs

## Python

`responsibleai.sovereign.client.SovereignClient` — in-process typed wrapper over `SovereignService`.

Retry classes: `RETRY_SAFE_READS`, `RETRY_NEVER_BLIND` (documented constants; no blind retry of shadow/simulate/execute).

## TypeScript

`sdk/typescript/sovereign/index.ts` — partial V1 (status negotiation). Full parity not claimed.

## Go

No Sovereign parity in this branch; use HTTP contract `contracts/sovereign-v1-web.json`.
