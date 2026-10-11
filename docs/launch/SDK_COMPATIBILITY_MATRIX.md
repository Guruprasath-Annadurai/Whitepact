# SDK compatibility matrix

Tested 2026-10-11 against the current server API. "Enforced" means the server runs the action behind the call; an
SDK can never enforce anything on code that does not call it (`docs/launch/ENFORCEMENT_PATH_MATRIX.md`).

| | Python (`sdk/python/rai_client`) | TypeScript (`sdk/typescript`, `@responsibleai/client`) | Go (`sdk/go/raiclient`) |
| --- | --- | --- | --- |
| Governed tool call (`/api/v1/governance/tools/call`) | Yes: `GovernanceRuntimeClient.call_tool` | Yes: `GovernanceRuntimeClient.callTool` | **No governance client at all** |
| Approvals, delegation revoke, evidence | Yes | Yes | No |
| Scoring / guardrails / hallucination / cost | `RAIClient` | `RAIClient` | Evaluate, Scan, AnalyzeHallucination, RecordUsage, Health only |
| Auth | Bearer key header; key not echoed in errors (tested) | same (tested) | Bearer key |
| Non-2xx handling for the governed call | **Fixed this pass**: raises `GovernanceRequestError` | **Fixed this pass**: throws `GovernanceRequestError` | n/a; generic client errors on status ≥ 400 |
| Positive signal for "the action may proceed" | `outcome.completed` (2xx and no `error`) | `isCompleted(result)` | n/a |
| Timeouts | httpx timeout (default 30 s) | AbortController (default 30 s); timer now cleared on failure | context-based |
| Retries | none on governance calls | `RAIClient` retries 429/502/503/504 with backoff; governance calls are not retried | not reviewed |
| Idempotency keys | none | none | none (a retried POST that already executed is a server-side reconciliation case) |
| Installation | in-repo package | builds with `tsc`; package metadata fixed (see below) | **not built here: no Go toolchain in this environment**; module path still says `ResponsibleAi` (the old repository name) |
| Automated tests in CI | `tests/test_sdk_*.py` (30) | `sdk/typescript/test` (6, run in the "Frontend closure" job) | none found |
| Status | Engineered + tested | Engineered + tested (new) | **Partial / not tested; scoring client only** |

## Defects found and fixed

* **Fail-open default (P1, Python and TypeScript).** `call_tool` returned the JSON body of *any* response as the
  outcome. A 401, 403, 429 or 5xx has neither `denied` nor `requires_approval`, so code that proceeds when neither is
  set would run the action when authentication failed or the server was down. Now only a 2xx JSON object is an outcome;
  anything else is an exception. `tests/test_sdk_fail_open_defaults.py` (30 cases incl. all non-2xx statuses) and
  `sdk/typescript/test/governance.test.mjs`.
* **TypeScript package metadata (P2).** `package.json` exported `require: ./dist/index.cjs`, a file the build never
  creates, declared `test: jest` with no jest dependency or tests, and shipped ESM output without `"type": "module"`.
  Now: ESM-only exports that exist, `"type": "module"`, a real `node --test` suite.
* **TypeScript timer leak.** The abort timer was only cleared on success; it is now cleared in `finally`.

## Not done

Go: build, test, governance client, module path. TypeScript: CommonJS output if CJS consumers are a requirement
(currently ESM-only, which is a breaking change from the previous, non-functional `require` entry); `npm publish`
dry-run; Node 18 compatibility; framework-integration smoke tests (`src/responsibleai/integrations/`) in a clean
environment. No SDK has been run against a deployed server.
