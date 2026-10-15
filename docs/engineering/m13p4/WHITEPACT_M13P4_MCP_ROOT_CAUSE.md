# M13-P4 MCP root cause

GLOBAL PRODUCTION NO-GO. This finding concerns the real-TCP test-server lifecycle, not a security acceptance verdict.

## Exact comparison

- Security baseline: `57c69344961196fd89b40e8ffec65c06a1898fce`, tree `b6f3cec8666da0a9960ee2ec2a725ef81a4eb7d4`.
- Product baseline: `bb87d76841c1aef7a22e53b20728c646f94c85a5`, tree `f087989a4ee36e7841624bb891241271b64415da`.
- `src/responsibleai/mcp/`, `src/responsibleai/ops/admission.py` and `tests/test_mcp_wave1_compatibility.py` are identical between those candidates.
- Reproduction dependencies: Python 3.11.15, MCP 1.29.1, sse-starlette 3.4.11, Starlette 1.6.0, AnyIO 4.15.1, Uvicorn 0.52.4, HTTPX 0.28.1.

Both named tests passed in a fresh process when selected alone: 2 passed. The unchanged full product sequence produced 2 failures and 3 passes. The unchanged full security sequence passed once, then reproduced the same 2 failures and 3 passes with shutdown-state observation. This is a pre-existing intermittent fixture lifecycle defect; it was not introduced by M13-P3 product source changes.

## First failing boundary

The SSE dependency stores `AppStatus.should_exit` at process scope. Its shutdown watcher observes the preceding Uvicorn instance's `should_exit` flag and sets the global flag. The fixture then starts another Uvicorn instance in the same interpreter, unlike a fresh production process. When that instance serves SSE, the dependency's exit listener returns immediately; its response task group cancels streaming before the final ASGI body frame. Uvicorn reports `ASGI callable returned without completing response`, and HTTPX raises an incomplete chunked-response `RemoteProtocolError` after `200 OK`.

Observation on the exact security baseline recorded:

```text
after stdio discovery: should_exit=False
after enterprise stdio refusal: should_exit=False
after TCP discovery fixture teardown: should_exit=True
after malformed/invalid test teardown: should_exit=True
after revoked-session test teardown: should_exit=True
```

Watcher timing explains why one baseline run passes: the previous server can stop before the watcher copies its flag. No arbitrary sleep or timeout increase is needed to repair the fixture.

## Minimal correction and preserved assertions

Only the `tcp_mcp` test fixture resets `AppStatus.should_exit=False` when starting a new independent in-process test server. Pytest monkeypatch restores surrounding state. No authentication, revocation, protected dispatch, MCP session manager, HTTP production response or security-owned source is changed. Graceful shutdown remains enabled.

`tests/test_m13p4_mcp_lifecycle.py` deterministically simulates a prior shutdown before requesting a fresh server and calls the original malformed-input and revoked-session test functions. Before the fixture correction both tests fail; after it all seven original/new tests pass. Assertions checking no dispatch, immediate revoked-key refusal and absence of reflected credentials remain unchanged.

The original two failures did not reach their later security assertions reliably. Passing the corrected tests establishes their local fixture contract, not global credential-revocation or privileged customer journey qualification. An embedded production deployment that restarts multiple Uvicorn applications in one interpreter would need its own lifecycle review; no unsupported production workaround is added here.

## Antigravity handoff

No production protected-execution or revocation defect was established by this reproduction. The minimal prior-shutdown regression and unchanged assertions are available for security review. All original `tests/independent_m13r2/` files are preserved. M13-S4 was fetched read-only at `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`; it is not integrated or independently accepted by this product change.
