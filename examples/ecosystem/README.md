# Framework and runtime demonstrations

These examples use the APIs already in this repository. They do not weaken
authorization, and they do not call a hosted endpoint.

Run the authorization demonstration from the repository root:

```bash
PYTHONPATH=src python examples/ecosystem/runtime_authorization_demo.py
```

The same path is covered by `tests/test_ecosystem_runtime_demo.py`.

## What the demonstration actually does

| Check | API | Result in this example |
|---|---|---|
| Denied before execution | `WhitePactRuntimeGateway.evaluate` then `authorize_execution` | `DENY` raises `DecisionNotExecutableError`. No executor runs. |
| Human approval | Gateway `require_approval_for` | `REQUIRE_APPROVAL` is not executable. |
| Short-lived grant | `build_authority_grant(..., ttl_seconds=-1)` | `is_usable` is false. The example does not execute the requested payment. |
| Replay | `admit_execution` twice on one authorization | The second call raises `AuthorizationAlreadyConsumedError`. |
| Tenant isolation | `assert_same_organization` | A cross-organization read raises `SovereignTenantIsolationError`. |
| Evidence | `build_evidence_record` | The record stores `api_token` as a field name and not the raw value. |

`admit_execution` is the in-process replay gate. Durable nonce consumption
against PostgreSQL is a separate, already-tested path
(`tests/test_phase1_live_admission.py` and related suites). This lane does
not change that path.

## Framework entrypoints that exist

| Framework | Entrypoint | Install extra | What it gates |
|---|---|---|---|
| LangChain | `responsibleai.integrations.langchain_middleware.TrustGateMiddleware` | `rai-governance-platform[langchain]` | `wrap_tool_call` can skip the tool handler when a Trust Index check fails. Default network failure posture is fail-open unless `require_known=True`. |
| LangGraph | `responsibleai.integrations.langgraph_gate.make_trust_gate_node` | `rai-governance-platform[langgraph]` | A graph node that consults the same Trust Index client. |
| Google ADK | `responsibleai.integrations.adk_toolset.build_stdio_toolset` and `build_http_toolset` | `rai-governance-platform[adk]` | Exposes the MCP toolset to ADK. Governance of hosted dispatch is the MCP server path, not a bypass inside the toolset. |

Published PyPI `1.2.6` includes the `langchain`, `langgraph`, and `adk`
extras. Source `1.3.1` is not a published install. Do not pin examples to
`1.3.1` for `pip`.

The LangChain and LangGraph gates call `TrustClient`. A local example that
needs a live Trust Index is not started here, because that would depend on
a reachable index and would not by itself prove the runtime `DENY` path.
Use the runtime demonstration above for the authorization boundary. Existing
adapter tests remain `tests/test_langchain_middleware.py`,
`tests/test_langgraph_gate.py`, and `tests/test_adk_toolset.py`.

## Frameworks with no adapter in this tree

LlamaIndex, CrewAI, and AutoGen (including AG2) have no import, extra, or
example in this commit. Do not list WhitePact as a native integration for
those frameworks. Adding one would be new product code and is recorded as
a blocker in `docs/ecosystem/BLOCKERS_AND_DEPENDENCIES.md` rather than
implemented in this lane.
