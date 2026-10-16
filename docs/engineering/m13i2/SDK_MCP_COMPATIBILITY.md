# M13-I2 independent SDK and MCP compatibility

Executed from isolated `/private/tmp/whitepact-m13-i2-sdk`, branch `codex/whitepact-m13-i2-sdk-validation`, starting commit `8cb692b99fb4b1fa894e07d432105209f430b0f7`, tree `6d00ded41d82feeb57b9f0842e000d9f4d22bd5f`. Starting checkout was clean. This report records newly executed local checks; earlier milestone results are not substituted. Only this report was changed. No SDK defect requiring a source change was found. Security source and original independent reproducers were preserved.

**GLOBAL PRODUCTION NO-GO.** SDK/provider-contract and local MCP tests do not qualify privileged authority, PostgreSQL crash durability, containment or a real customer golden journey. Those remain independently gated.

## Environment and exact commands

Python 3.11.15: `/Users/ag/Whitepact/.venv/bin/python`; test commands below use `PYTHONPATH=src:.:sdk/python`. Node `v26.0.0`, npm `11.12.1`; TypeScript compiler PATH `/private/tmp/whitepact-m13-p3-recovery/web/node_modules/.bin`. Go `go1.27.2 darwin/arm64`: `/private/tmp/whitepact-m13p4-go-toolchain/go/bin/go`, previously downloaded from official Go with verified SHA256, unchanged. MCP `1.29.1`, sse-starlette `3.4.11`, HTTPX `0.28.1`, Uvicorn `0.52.4`. Local version results do not establish Python3.12/Node22/other supported Go matrix results.

| Independent command | Result |
| --- | --- |
| `PYTHONPATH=src:.:sdk/python /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_sdk*.py tests/test_evaluation_benchmark_safety.py -q --no-cov` | **347 passed in 7.21s** |
| `PATH=/private/tmp/whitepact-m13-p3-recovery/web/node_modules/.bin:$PATH npm --prefix sdk/typescript test` | TypeScript build passed; **53 passed**, no skips/failures, 9.109s test duration |
| In `sdk/go`: temporary Go executable `test -race -count=1 ./...`, then `vet ./...`, then `build ./...` | All exit0; `raiclient` race tests passed **2.817s**; command packages have no test files |
| `PYTHONPATH=src:.:sdk/python /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_mcp_wave1_compatibility.py tests/test_mcp_protocol_matrix.py tests/test_mcp_enterprise_trust_domain.py tests/test_mcp_http_transport.py tests/test_m13p4_mcp_lifecycle.py -q --no-cov --tb=short` | **44 passed in 82.14s**, no skips/failures |
| `PYTHONPATH=src:.:sdk/python /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_a2a_adapter.py tests/test_langchain_middleware.py tests/test_wave1_framework_compatibility.py tests/test_crewai_llamaindex_governance_consumers.py -q --no-cov --tb=short -rs` | **39 passed, 32 skipped**, one ADK warning, 29.61s |

Go commands used `GOCACHE=/private/tmp/whitepact-m13p4-go-cache GOMODCACHE=/private/tmp/whitepact-m13p4-go-modcache GOTOOLCHAIN=local`. Network/loopback permission was granted for actual TCP test fixtures. No cloud credentials or customer systems were used.

## Package build and installation

Rebuilt from this exact source using existing disposable environment (Python3.11.15, build1.6.1, hatchling1.32.4, HTTPX0.28.1):

```sh
/private/tmp/whitepact-m13p4-sdk-venv/bin/python -m build sdk/python --no-isolation --outdir /private/tmp/whitepact-m13i2-sdk-dist
uv pip install --offline --no-deps --reinstall --python /private/tmp/whitepact-m13p4-sdk-venv/bin/python --cache-dir /private/tmp/whitepact-m13p4-uv-cache /private/tmp/whitepact-m13i2-sdk-dist/rai_client-1.3.1-py3-none-any.whl
```

Both sdist and wheel built and installed successfully. The first reinstall command omitted `--offline --no-deps` and failed after three PyPI HTTPX resolution retries due unavailable DNS; that environmental attempt did not establish a package failure. The corrected command installed the wheel against already installed dependencies without network. An import from `/private/tmp`, without source `PYTHONPATH`, confirmed version1.3.1 and module path under `/private/tmp/whitepact-m13p4-sdk-venv/lib/python3.11/site-packages/`; `GovernanceRuntimeClient` imported.

From `sdk/typescript`:

```sh
npm pack --pack-destination /private/tmp/whitepact-m13i2-sdk-dist --cache /private/tmp/whitepact-m13p4-npm-cache --json
npm install --prefix /private/tmp/whitepact-m13i2-ts-consumer --ignore-scripts --no-audit --no-fund --cache /private/tmp/whitepact-m13p4-npm-cache /private/tmp/whitepact-m13i2-sdk-dist/responsibleai-client-1.3.1.tgz
node --input-type=module -e 'import("/private/tmp/whitepact-m13i2-ts-consumer/node_modules/@responsibleai/client/dist/index.js").then(m=>console.log(Object.keys(m).sort().join(", ")))'
```

Passed: package1.3.1, 21 entries, 81,247 unpacked bytes; actual temporary consumer install/import exports `GovernanceRequestError, GovernanceRuntimeClient, RAIClient, RAIError, isCompleted`. Nothing published.

| Temporary artifact under `/private/tmp/whitepact-m13i2-sdk-dist/` | SHA256 |
| --- | --- |
| `rai_client-1.3.1-py3-none-any.whl` | `638b70b5062a30384c875138670368299698116de60d0f220a917b5ea562ce39` |
| `rai_client-1.3.1.tar.gz` | `66cde39dae16a1a4a414e18a1a542575b6e1877044da492f18d4f65d22f473f8` |
| `responsibleai-client-1.3.1.tgz` | `368602f30e3a575f15f2e436d007f4e8074168ccd110830dbabe3a77095c553b` |

## Contract coverage and unresolved limits

SDK tests cover common governance envelopes/version metadata, deadlines/cancellation, malformed and contradictory responses, typed errors, credential transport/redaction, safe bounded read retries, one-shot mutations and explicit uncertain completion after lost acknowledgement. They do not authorize automatic mutation replay or imply exactly-once execution. Stop and reconcile existing tenant evidence/approval state after uncertainty; never infer non-execution merely from transport failure.

MCP's combined44-test result includes real TCP/subprocess compatibility, protocol matrix, enterprise trust-domain, HTTP transport and lifecycle regressions. The original test suites were not edited. No concrete MCP regression was found in this run; intermittent failures cannot be disproved by a single clean run.

Adapter skips were explicit missing dependencies: **10 OpenAI Agents** (`agents`), **11 CrewAI** (`crewai`), **11 LlamaIndex** (`llama_index.core`). Installed ADK/LangChain/LangGraph paths ran where applicable; ADK warned that `BaseAgentConfig` is deprecated. A2A coverage is the dependency-free gate/availability guard, not proof of a fully installed external A2A stack. These optional missing integrations remain **UNVERIFIED**, not passing.

Real authenticated PostgreSQL SDK/customer journeys and final integrated candidate CI remain separate validations owned by integration. No historical skip is promoted to success and no security acceptance is inferred from these product compatibility checks.
