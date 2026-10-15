# Handoff to Antigravity: global distribution and assurance pass

Code baseline for this pass: PR #180 head `92a08e01ab68b30f82a7da7a43af21a447175b64` (tree
`dd271bb74b5b00c37a2819f405a6b5b6cbb4c2e8`) at the time of writing. Later commits that only edit this file or the PR text
do not change code; confirm with `git diff 92a08e01..HEAD --stat`. **No earlier audit qualifies this tree.**
Antigravity authored PR #183 (FastStart): a different reviewer must assess that code. This reviewer is also an AI agent.

## What to retest independently (do not trust the green runs)

| Area | How |
| --- | --- |
| Step-up | `tests/test_step_up_forged_proofs_http.py`; try your own forgeries over HTTP: any non-TOTP method, replayed code, nonce for another action/user/session, unenrolled user, brute-force burst |
| Policy governance | `tests/test_policy_tiered_governance_http.py`, `test_policy_mutation_routes_are_gated.py`; look for a mutation route the structural test misses (`governance_policies` writers) |
| Policy history | `tests/test_policy_history*.py` (SQLite and PostgreSQL); try a rewrite that keeps every digest valid and a rollback of both tables |
| Authority Challenge | `python scripts/authority_challenge.py` (12 scenarios; scenario 10 is BLOCKED off Linux; I ran it on a Linux 6.12 kernel via `scripts/verify-linux-container-isolation.sh nonroot` and it passed) |
| MCP | `tests/test_mcp_protocol_matrix.py`, `test_mcp_http_credential_negatives.py`, `test_mcp_directory_conformance.py`; try SSE (`/sse`) with the same credential matrix: **not covered** |
| SDKs | `tests/test_sdk_fail_open_defaults.py`, `sdk/typescript/test`; Go SDK untested (no toolchain here) |
| Supply chain | the commands in `docs/assurance/WHITEPACT_SUPPLY_CHAIN_SECURITY_EVIDENCE.md`; re-run the OSV query on `uv.lock` |
| Config | `tests/test_production_environment_resolution.py`, `test_production_unsafe_flags.py`: look for an environment spelling or `.env` precedence case that yields development semantics in production |

## Findings and fixes this pass (see the issue register for the full list)

REC-30 step-up verified nothing (P0, fixed, OIDC/WebAuthn refused); REC-31 policy-history verification gaps (fixed);
REC-25 tiered governance (built, off); REC-32 MCP 500 on malformed body (fixed); REC-33 unsafe flags accepted in
production and `WHITEPACT_` lines ignored in `.env` (fixed); REC-34 OIDC cookie alerts (fixed); SDK fail-open default
(fixed); mako/multidict advisories (fixed); manifest/tool description truthfulness (fixed).

## Known open, not fixed

REC-28 (30/min per-route cap), REC-29 (1,000 concurrency not met), host-side fixture exception (REC-12), running tools are
not cancelled by revocation, no external evidence anchor, two public witness-file CodeQL alerts (owner decision),
OpenSSF items needing a second maintainer, no human penetration test, no third-party assistant tested, hosted endpoint
not on an owned domain, OIDC/WebAuthn step-up unimplemented.

## Not done in this pass

ChatGPT/Claude/Grok connections; plugin ZIP; Smithery/Glama inspection; fuzzing; hash-pinned build tooling; container
image scanning; real-browser journeys beyond the one CI journey; observability review; billing/webhook idempotency;
Redis failover; competitor benchmarks; consolidated threat model document.

## Verdict request

PASS / CONDITIONAL / FAIL / BLOCKED / NOT TESTED per area above, with exact SHA and tree, addressed to ChatGPT (GPT-6)
through the founder. Production remains NO-GO.
