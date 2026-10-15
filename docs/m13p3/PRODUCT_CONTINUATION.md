# M13-P3 product continuation checkpoint

GLOBAL PRODUCTION NO-GO. This is a product checkpoint, not milestone completion or independent security qualification. No main merge, deployment, cloud provisioning or M14 execution is authorized.

## Recovery and provenance

The incorrect `/Users/ag/Documents/ChatGPT/whitepact` workspace was not modified during this recovery. Both existing local checkouts were inspected with Git and preserved:

| Checkout | Branch | HEAD | Tree | Status |
| --- | --- | --- | --- | --- |
| `/Users/ag/Whitepact` | `local/enterprise-recovery-master` | `3b61db0aed88512b22af613e281479b2aa9b6299` | `8d2c8bb310914a9fe7acb32f61971a52322cea75` | Clean at inspection |
| `/Users/ag/whitepact-m13-product-integration` | `codex/whitepact-m13-product-integration` | `a390f9ecf81e11b9aa327b80b309524d7ec0bfa6` | `674acb5f52a32ff6f22cb18e2b181476ee5643b3` | Clean at inspection |

Both remotes identify `https://github.com/Guruprasath-Annadurai/Whitepact.git`. Neither checkout contained uncommitted work; interrupted uncommitted work is **not recovered or inferred**.

A separate clone made with `git clone --no-hardlinks` is writable at `/private/tmp/whitepact-m13-p3-recovery`. Its origin was set to the canonical GitHub URL. Branch `codex/whitepact-m13-p3-product` starts at `57c69344961196fd89b40e8ffec65c06a1898fce`, tree `b6f3cec8666da0a9960ee2ec2a725ef81a4eb7d4`. GitHub branch lookup and draft PR #206 metadata independently confirm this baseline. The supplied M13-P product commit is already an ancestor. No baseline patches were reapplied.

## Delivered product slice

- Onboarding focuses its heading on initial/restored entry and each step transition. The progress list exposes the current step, and use-case and plan choices have accessible group names. Back navigation preserves selections; draft restoration does not submit data or activate entitlement.
- Dashboard overview validates the existing summary response before rendering. Null payloads, invalid counters, malformed activity records and invalid service values produce an alert and explicit read retry rather than a false empty result or render failure. Unknown backend risk, decision and service labels remain unchanged.
- Committed static dashboard assets are rebuilt from these sources. No backend, SDK, security enforcement, migration or security finding is changed.

Implementation checkpoint: `7fd0fdd19c74cb8b4eab8afcd465eb786ca33817`, tree `a8672a2eb72220c49b523c035376932e18e08af9`. Subsequent documentation-only checkpoint metadata is recorded in the draft PR and external handoff record to avoid a self-referential commit hash.

## Fresh local validation (2026-10-15)

Runtime: Node `v26.0.0`, Python `3.11.15`. Existing web dependencies were copied into the new clone; the existing Python virtual environment was reused with `PYTHONPATH=src`. A clean dependency installation and the CI Python/Node matrix are not established by these local runs.

| Command | Result |
| --- | --- |
| `npm --prefix web test -- --maxWorkers=2` | PASS: 26 files, 251 tests |
| `npm --prefix web run build` | PASS: TypeScript and Vite build |
| `npm --prefix web run lint` | PASS |
| `PATH="$PWD/web/node_modules/.bin:$PATH" npm --prefix sdk/typescript test` | PASS with loopback sockets available: build and 53 tests |
| `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_web_platform.py tests/test_sdk_governance_contract.py tests/test_mcp_wave1_compatibility.py -o addopts='' -q` | 20 passed; 3 MCP fixture errors because sandbox prohibited socket binding |
| `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_mcp_wave1_compatibility.py tests/test_m13p_postgres_schema.py -o addopts='' -q` (loopback permitted) | 4 passed, 2 failed; PostgreSQL schema migration test passed |
| `git diff --check` | PASS |
| `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/python -m pytest tests/test_web_platform.py tests/test_sdk_governance_contract.py -o addopts='' -q --tb=short` | PASS: 18 tests; isolated rerun |
| Rebuild followed by `git diff --exit-code -- src/responsibleai/dashboard/static/whitepact` | PASS: committed assets reproduce |
| Diff against security baseline for enterprise, isolation, database, preserved security acceptance tests and security documentation | Empty |

The first unconstrained web run had 250 passes and one `/developers` test timeout at 5 seconds during concurrent validation. The bounded-worker full rerun passed without changing timeout thresholds. Initial linked-dependency Vite startup failed because its cache targeted the read-only source checkout; dependencies were copied locally before successful validation. The first TypeScript SDK run was also blocked by sandbox loopback restrictions; the subsequent permitted run passed.

## Unresolved and blocked

- **MCP compatibility unresolved:** `test_real_tcp_malformed_and_invalid_arguments_never_dispatch` and `test_real_tcp_revoked_key_cannot_reuse_discovery_session` fail with `httpx.RemoteProtocolError: peer closed connection without sending complete message body (incomplete chunked read)`. Uvicorn reports `ASGI callable returned without completing response.` No MCP source was changed; root cause and baseline attribution remain unverified. No test is skipped or weakened.
- **Privileged journeys BLOCKED:** bootstrap, root activation/revocation, delegation, recovery execution, quorum and containment workflows lack independent qualification in this assignment. Implementation-owner closure claims in security documents are preserved and do not constitute product approval.
- **Inventory integration BLOCKED:** application inventory lacks an integrated customer contract. Agent inventory and recovery preparation remain unwired to production routes; no capability switch, privileged navigation or mutation control is enabled.
- **Security findings preserved:** no finding is closed by this product checkpoint. Historical ownership records and the security defect register remain unchanged. Passing schema migration checks do not establish full migration rollback or security qualification.
- Existing onboarding/organization and SDK functionality receives routine regression coverage; no new organization privilege or SDK capability is added. Full Python suite, browser end-to-end accessibility audit, PostgreSQL downgrade validation and independent security review remain unverified.
- GitHub CI results must be read separately from local validation; draft publication is not a passing CI or release verdict.
