# CrewAI and LlamaIndex consumer qualification

## Scope / ownership

Base `01cc0d9b815d7ce27f41cc42fb4853b845003d75`, isolated branch
`codex/crewai-llamaindex-consumers`. Changes are only the new test, direct
dependency pins and this evidence. Existing 47 framework tests are not duplicated
or modified. No adapters, SDK, core, runtime, auth, security or workflow changed.
Antigravity's P0 remediation ownership is preserved.

## Actual execution

Fresh dedicated Python 3.11 venv `/private/tmp/wp-crewai-llamaindex-venv`.
Actual CrewAI **1.15.28**, LlamaIndex Core **0.14.25**, HTTPX **0.28.1**,
pytest **9.1.1**, pytest-asyncio **1.4.0**, Ruff **0.17.0**.

```sh
python -m pip install -r tests/requirements-crewai-llamaindex-consumers.txt
OTEL_SDK_DISABLED=true CREWAI_TRACING_ENABLED=false PYTHONPATH=src:sdk/python \
  python -m pytest tests/test_crewai_llamaindex_governance_consumers.py \
  -q -o addopts='' --noconftest
ruff check tests/test_crewai_llamaindex_governance_consumers.py
ruff format --check tests/test_crewai_llamaindex_governance_consumers.py
git diff --check
```

Fresh result: **22 passed, 0 failed, 0 skipped, 0 warnings**, 26.45 seconds.
Lint, format and diff checks passed. No tests were deleted or assertions weakened.
`--noconftest` isolates dependency-only consumers from unrelated backend fixtures.
Direct pins are not represented as a full transitive lock or package security audit.

## Behavior demonstrated

Real `CrewStructuredTool.from_function` / `ainvoke`, and real LlamaIndex
`FunctionTool.from_defaults` / `acall` execute the actual WhitePact Python SDK
against a real ephemeral localhost HTTP connection. No fake framework modules
or stand-in framework classes are used.

For both frameworks:

- SUCCEEDED is completed; UNKNOWN stays uncertain; DENY, REQUIRE_APPROVAL,
  QUARANTINE and malformed empty-object responses never become completed.
- Null and list responses raise the SDK's real `GovernanceRequestError`.
- HTTP 401 and 403 propagate as credential errors, not successful tool outputs.
- One governed request occurs; no automatic mutation replay is observed.
- Injection-like argument text containing forged organization/grant instructions
  is preserved strictly as `arguments.value`, not promoted into request authority.
- Explicit task cancellation after the server received the POST propagates
  `CancelledError`, with one request and no client retry. This proves cancellation
  compatibility, **not** that a remotely admitted effect can be undone or is absent.
- Client output and errors do not reveal the synthetic test credential.

## Evidence boundary / remaining work

The localhost server is an explicitly controlled SDK **response contract fixture**,
not WhitePact Core. These are genuine framework-object, tool-execution and transport
tests; they do not prove canonical authorization, tenant isolation, durable grants,
revocation, approval quorum, replay admission or consequential side-effect safety.
No model-provider calls, real credentials, paid resources or external tools were used.
No Crew/agent model run, retrieval pipeline or production qualification is claimed.
The consumer closures are test examples, not shipped new framework adapters.

Optional imports skip in minimal installs. Qualification must install direct pins
and require zero skips; a dependency skip must not be interpreted as a passed case.
Coordinator owns fresh integrated-head CI and independent Antigravity handoff.
Antigravity should reproduce these tests, then pair them with actual Core-backed
security/tenant/approval tests without substituting this provider fixture for those.
Production remains **NO-GO**. Local signed-off commit only; no push, merge,
deployment, package publication, cloud or DNS mutation in this subtask.
