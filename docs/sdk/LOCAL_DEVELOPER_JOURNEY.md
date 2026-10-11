# Real local SDK journey

This is development integration evidence, not production qualification. Use only a
disposable PostgreSQL instance and literal-loopback HTTP. Authentication stays on;
explicit test root, consent and delegation records are not a hosted issuance path.
The counter tool creates a local database effect, not an external production action.

## Reproduce from a clone

Prerequisites: Python 3.11 or 3.12, Node 22+, Docker (or an explicitly isolated
PostgreSQL instance). Do not use production database credentials.

```sh
python -m venv .venv-sdk-journey
.venv-sdk-journey/bin/python -m pip install -r sdk/python/requirements-test.txt
.venv-sdk-journey/bin/python -m pip install '.[dashboard,postgres,mcp]' alembic
npm --prefix sdk/typescript ci --ignore-scripts --no-audit --no-fund
npm --prefix sdk/typescript run build
docker run --name wp-sdk-local-pg -p 127.0.0.1:55432:5432 \
  -e POSTGRES_USER=wp -e POSTGRES_PASSWORD=wp -d postgres:16
PYTHONPATH=src:. .venv-sdk-journey/bin/python -m pytest \
  tests/test_developer_sdk_live_api.py -q --no-cov
```

The shown database password is deliberately public, local-test-only and must never
be reused elsewhere. If the container name/port already exists, use the existing
verified disposable instance or configure `WHITEPACT_TEST_PG_ADMIN_URL` privately.
The test creates and removes only its own randomly named database and migrates it
to the repository's actual head. It binds the real application to an ephemeral
127.0.0.1 port and shuts it down afterwards. No paid service is required.

The test exercises Python and TypeScript over real TCP: invalid authentication,
DENY without authority, explicit test authority, REQUIRE_APPROVAL without effect,
fresh ALLOW invocation, actual counter execution, UNKNOWN after an effect with
lost acknowledgement, bounded evidence listing/attestation, delegation revocation,
and DENY after revocation. The pending request is not approved or resumed; the
later ALLOW is a separate invocation. Approval resume/four-eyes remains a separate
release-critical workflow, not proved by this test.

## Use the examples against your configured server

Install/build the SDK, then privately set `WHITEPACT_API_KEY`, `WHITEPACT_URL`,
`WHITEPACT_TOOL` and `WHITEPACT_PURPOSE` to an operator-approved scope. Do not put
keys in command arguments or source files. Run either:

```sh
python sdk/python/examples/governed_call.py
node sdk/typescript/examples/governed-call.mjs
```

These examples perform one call and print classification only, not raw arguments,
credentials or tool output. They do not provision authority, approve actions,
retry uncertain mutations or grant themselves access. See
[mutation reconciliation](MUTATION_UNCERTAINTY.md).

## Evidence contract limitation

Use `list_evidence`/`listEvidence` for the backend's bounded listing (1–200 records),
and `get_attestation`/`getAttestation` for its existing tenant-scoped attestation.
A bounded list is not complete history or server pagination. An attestation is
not a cryptographic signature or proof of an external effect.

The legacy SDK `get_evidence`/`getEvidence` assumes a standalone bearer-auth detail
endpoint absent in the current backend and returns a safe 404 exception. The
browser session detail route is not a substitute for API-key authentication. This
gap is reported to the backend owner; no fictitious endpoint or silently changed
return schema is supplied here.

Installation time is environment-dependent. Five minutes is an onboarding target,
not a measured universal guarantee. Package caching, network and PostgreSQL setup
must be disclosed in any timing result.
