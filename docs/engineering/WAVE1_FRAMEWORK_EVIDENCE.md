# Wave 1 genuine framework compatibility evidence

## Ownership and provenance

- Base: `f338556baf9984ab485f2d4758179fb87e8baa4d` (preserved PR #198).
- Branch: `codex/wave1-framework-compatibility`.
- Owned surfaces: new compatibility test, its direct dependency pins, this evidence.
- No SDK, runtime, authentication, billing, authority, shared security, migration,
  or existing framework adapter source changed. Antigravity P0 ownership remains intact.

## Executed environment

Dedicated `/private/tmp/wp-wave1-framework-py311` virtual environment, Python 3.11.
Genuine installed distributions: LangChain 1.4.4, LangGraph 1.2.14,
OpenAI Agents SDK 0.23.1, Google ADK 2.11.0, HTTPX 0.28.1,
pytest 9.1.1, pytest-asyncio 1.4.0. Direct pins are in
`tests/requirements-wave1-frameworks.txt`; this is not a transitive release lock.

```sh
PYTHONPATH=src:sdk/python python -m pytest \
  tests/test_wave1_framework_compatibility.py \
  tests/test_langchain_middleware.py tests/test_langgraph_gate.py \
  tests/test_adk_toolset.py -q -o addopts='' --noconftest
ruff check tests/test_wave1_framework_compatibility.py
ruff format --check tests/test_wave1_framework_compatibility.py
git diff --check
```

Fresh result: **47 passed, 0 failed, 0 skipped, 1 warning**, 20.59 seconds.
New file contributes 24 cases; existing framework adapters contribute 23.
Ruff lint/format and diff checks passed. ADK emits its existing experimental
`PLUGGABLE_AUTH` feature warning; it was not suppressed or interpreted as qualification.
`--noconftest` intentionally isolates these dependency-only consumers from shared
backend fixtures. This does not constitute backend, PostgreSQL or release CI proof.

## What the tests prove

- Real LangChain `ToolCallRequest`, middleware and `StructuredTool` invocation:
  known/high-score invokes exactly once; low score and unknown trust invoke zero times.
- Real compiled LangGraph with `InMemorySaver`: interrupt/resume reruns the live
  localhost trust lookup; invalid approval input rejects after the second lookup.
- Real OpenAI `Agent` / function tool / `ToolContext` and Google ADK `LlmAgent` /
  `FunctionTool`: the actual Python governance SDK calls localhost HTTP once and
  preserves success, denial, approval-required, uncertainty, quarantine, failed,
  pending, empty-object and nested-error responses as non-success where appropriate.
- Request is the supported server-governed tool-call payload. No client organization,
  price, grant, authority algorithm or downstream consequential effect is introduced.

The first OpenAI run failed five cases because the test used `RunContextWrapper`
where this actual framework version requires `ToolContext`. Correcting the test
to the published runtime object's `from_agent_context` seam resolved those failures.
No product workaround or test deletion was used.

## Explicit limitations / integration instructions

The localhost HTTP fixture is a controlled provider contract, **not a WhitePact
canonical governance server**. Framework objects and SDK serialization/transport
execute for real; server authority enforcement is not substituted by this fixture.
LangChain/LangGraph Trust Index gates are advisory framework surfaces, not proof of
canonical execution grants. LangGraph human resume is not WhitePact durable approval.
No external LLM/API calls, paid resources, secrets, packages or deployments were used.
No full model-driven Runner conversation, ADK model invocation, real ADK MCP discovery,
four-eyes approval or production revocation qualification is claimed here.

Optional packages retain explicit `importorskip` behavior in normal minimal installs.
Qualification must install the pinned dependencies and verify **zero skips**. Missing
packages cannot be reported as passing these cases. Coordinator should run this suite
fresh on the integrated head, then include exact-head Actions evidence separately.
Antigravity should reproduce these tests independently and combine them with canonical
real-server security tests; these tests do not close its P0 dependencies.

Production remains **NO-GO**. No merge, push, publication or production action occurred
in this subtask. Local commit provenance is supplied separately to the coordinator.
