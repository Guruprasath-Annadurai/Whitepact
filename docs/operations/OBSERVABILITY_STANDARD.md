# Observability Standard

## Structured logging

- Enable: `WHITEPACT_LOG_JSON=true` (recommended production).
- Core fields: see `STRUCTURED_LOG_CORE_FIELDS` in `responsibleai.operations.production_contract`.

## Correlation

- Propagate `request_id` / `correlation_id` from ingress through governance and MCP dispatch.
- Correlation IDs are **not** authentication credentials.

## Metrics (Prometheus-compatible)

Minimum families to instrument over time:

- HTTP: rate, errors, latency
- MCP: tool rate, failures, latency
- Governance: allow/deny/approval counts (low-cardinality labels only)
- DB pool usage, query errors

## Tracing (OpenTelemetry)

- Optional `WHITEPACT_OTEL_ENDPOINT` — sampling configurable.
- Do not export request bodies or secrets in spans by default.

## Privacy

- Never log: passwords, tokens, `Authorization` headers, cookies, private keys.
- See `tests/test_secrets_never_logged_sweep.py`.
