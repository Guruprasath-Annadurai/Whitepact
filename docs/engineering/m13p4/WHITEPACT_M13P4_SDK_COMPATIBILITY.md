# M13-P4 SDK and adapter compatibility

Validated 2026-10-15 from `/private/tmp/whitepact-m13-p4`, starting HEAD `bb87d76841c1aef7a22e53b20728c646f94c85a5`, tree `f087989a4ee36e7841624bb891241271b64415da`. SDK source was unchanged during these checks. These are local product regressions, not final-head GitHub CI or independent security acceptance. **GLOBAL PRODUCTION NO-GO**.

Environment: Python 3.11.15 (`/Users/ag/Whitepact/.venv/bin/python`), Node 26.0.0, npm 11.12.1. TypeScript compiler supplied through `/private/tmp/whitepact-m13-p3-recovery/web/node_modules/.bin`. Local Node differs from CI Node 22; the exact-head CI matrix remains authoritative for CI compatibility.

| Command (repository root unless stated) | Actual result |
| --- | --- |
| `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_sdk*.py tests/test_evaluation_benchmark_safety.py -q --no-cov` | **347 passed**, 8.29s |
| `PATH=/private/tmp/whitepact-m13-p3-recovery/web/node_modules/.bin:$PATH npm --prefix sdk/typescript test` | Build passed; **53 passed**, 0 failed/skipped, 9.40s test duration; loopback fixture permission granted |
| `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_a2a_adapter.py tests/test_langchain_middleware.py tests/test_wave1_framework_compatibility.py tests/test_crewai_llamaindex_governance_consumers.py -q --no-cov` | Initial environment error: **42 failed, 29 passed**, 29.36s; SDK not installed and `sdk/python` missing from import path |
| Same adapter command with `PYTHONPATH=src:sdk/python` and `--tb=short` | **39 passed, 32 skipped**, 1 warning, 31.30s; local HTTP fixtures, no external model calls |
| `PYTHONPATH=src:sdk/python /Users/ag/Whitepact/.venv/bin/python -c 'import rai_client; from rai_client.governance import GovernanceRuntimeClient; print("local source imports OK")'` | Passed source import; this is not installed-wheel verification |
| `/Users/ag/Whitepact/.venv/bin/python -m build sdk/python --no-isolation --outdir /private/tmp/whitepact-m13p4-sdk-dist` | Initial environment failure: `No module named build`; hatchling and pip also absent; resolved with isolated environment below |
| `npm --prefix sdk/typescript pack --dry-run --json` | Initial command invoked from root was rejected: invalid package name/version; corrected to SDK working directory |
| `npm pack --dry-run --json --cache /private/tmp/whitepact-m13p4-npm-cache` in `sdk/typescript` | Passed: `@responsibleai/client@1.3.1`, 21 package entries, 81,247 unpacked bytes; no package published |
| `go version` | Initial environment failure: `command not found: go`; resolved with checksum-verified temporary official toolchain below |

## Isolated installation follow-up

No system installation or existing virtualenv mutation was needed. The bundled workspace dependency inventory supplies Python/Node but no Go. Existing `uv` was available at `/Users/ag/.local/bin/uv`.

```sh
uv venv --python /Users/ag/Whitepact/.venv/bin/python /private/tmp/whitepact-m13p4-sdk-venv
uv pip install --python /private/tmp/whitepact-m13p4-sdk-venv/bin/python --cache-dir /private/tmp/whitepact-m13p4-uv-cache build hatchling httpx
/private/tmp/whitepact-m13p4-sdk-venv/bin/python -m build sdk/python --no-isolation --outdir /private/tmp/whitepact-m13p4-sdk-dist
uv pip install --python /private/tmp/whitepact-m13p4-sdk-venv/bin/python --cache-dir /private/tmp/whitepact-m13p4-uv-cache /private/tmp/whitepact-m13p4-sdk-dist/rai_client-1.3.1-py3-none-any.whl
```

All passed using Python 3.11.15, build 1.6.1, hatchling 1.32.4, httpx 0.28.1. Both sdist and wheel built. An import check from `/private/tmp`, without source `PYTHONPATH`, confirmed version `1.3.1` and `rai_client.__file__` under `/private/tmp/whitepact-m13p4-sdk-venv/lib/python3.11/site-packages/`; `GovernanceRuntimeClient` imported successfully.

In `sdk/typescript`, actual local packaging and installation also passed:

```sh
npm pack --pack-destination /private/tmp --cache /private/tmp/whitepact-m13p4-npm-cache --json
npm install --prefix /private/tmp/whitepact-m13p4-ts-consumer --ignore-scripts --no-audit --no-fund --cache /private/tmp/whitepact-m13p4-npm-cache /private/tmp/responsibleai-client-1.3.1.tgz
node --input-type=module -e 'import("/private/tmp/whitepact-m13p4-ts-consumer/node_modules/@responsibleai/client/dist/index.js").then(m=>console.log(Object.keys(m).sort().join(", ")))'
```

Installed exports: `GovernanceRequestError, GovernanceRuntimeClient, RAIClient, RAIError, isCompleted`. No packages were published.

Official `https://go.dev/dl/?mode=json` selected stable `go1.27.2`, archive `go1.27.2.darwin-arm64.tar.gz`, 68,195,916 bytes, SHA256 `76812b213b1b2302c978d28fa52fa92d541704b9e7d9d5db8002c50e4018c4c5`. Downloaded from `https://go.dev/dl/go1.27.2.darwin-arm64.tar.gz`; `shasum -a 256 -c -` verified **OK** before extraction to `/private/tmp/whitepact-m13p4-go-toolchain`. Toolchain reports `go version go1.27.2 darwin/arm64`.

In `sdk/go`, all three commands passed (exit 0) with `GOCACHE=/private/tmp/whitepact-m13p4-go-cache GOMODCACHE=/private/tmp/whitepact-m13p4-go-modcache GOTOOLCHAIN=local` and executable `/private/tmp/whitepact-m13p4-go-toolchain/go/bin/go`:

```sh
go test -race -count=1 ./...
go vet ./...
go build ./...
```

`raiclient` race regression package passed in 2.733s; both command packages reported no test files. Vet/build completed silently. These were local Go1.27.2 checks, not proof of the full supported Go version matrix.

Built artifact SHA256: Python wheel `638b70b5062a30384c875138670368299698116de60d0f220a917b5ea562ce39`, Python sdist `66cde39dae16a1a4a414e18a1a542575b6e1877044da492f18d4f65d22f473f8`, TypeScript tarball `368602f30e3a575f15f2e436d007f4e8074168ccd110830dbabe3a77095c553b`. Artifacts remain temporary and unpublished.

Adapter skips reflect missing optional packages: OpenAI Agents `agents`, CrewAI `crewai`, LlamaIndex `llama_index.core`. Google ADK, LangChain and LangGraph paths ran where applicable. ADK emitted `DeprecationWarning: BaseAgentConfig is deprecated and will be removed in future versions`; no test assertions were weakened. A2A tests cover the dependency-free gate and SDK-availability guard; they do not prove an installed external A2A SDK integration. Missing optional integrations remain unverified.

## Contract coverage and limits

The Python/TypeScript suites exercise shared governance envelopes, canonical and legacy success classification, malformed/contradictory responses, typed HTTP/request failures, finite configured deadlines, cancellation, redirect refusal, read retry bounds, single-dispatch mutations, lost-response uncertainty, credential transport and reflected-key redaction. `tests/test_sdk_governance_contract_matrix.py`, `tests/test_sdk_version_parity.py`, `tests/test_sdk_package_metadata.py` and related contract fixtures ran in the Python total. This is test coverage, not a new backend security guarantee.

Python exposes `GovernanceRequestError` while preserving sanitized HTTPX transport/timeout classification; TypeScript separates request failures from denied/approval-required/uncertain outcomes. Go exposes `MutationUncertainError` and `GovernanceHTTPError`, configured timeout/context deadlines, and redaction; its race regressions passed as recorded above. Its module path deliberately remains the existing `github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go`; changing it during compatibility validation would break current consumers.

No mutating retry or exactly-once guarantee should be inferred. After a lost acknowledgement, stop and reconcile using existing tenant-scoped evidence/approval state; do not resubmit automatically, execute the tool directly, or treat transport failure as proof of non-execution. `docs/sdk/MUTATION_UNCERTAINTY.md` and `docs/sdk/LOCAL_DEVELOPER_JOURNEY.md` remain the setup/examples contract. The latter's real local PostgreSQL SDK journey was **not executed in this SDK validation** and cannot qualify privileged customer paths. Parent MCP regression evidence is recorded separately.

Remaining validation: optional adapters with their missing declared dependency sets; SDK CI Python 3.11/3.12 and Node 22, supported Go matrix and real local PostgreSQL SDK journey against the final exact candidate. No package publication is authorized. Security-owned source and the original independent reproducers were not modified.
