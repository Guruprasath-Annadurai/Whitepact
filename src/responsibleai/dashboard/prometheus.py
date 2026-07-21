"""Prometheus metrics definitions and helpers.

Exposes a /metrics endpoint compatible with any Prometheus scraper
(Grafana, Datadog agent, VictoriaMetrics, etc.).

Metrics exported:
    rai_trust_score               Gauge   Current trust score per model/provider/org
    rai_requests_total            Counter API requests by endpoint and HTTP status
    rai_cost_usd_total            Counter Cumulative cost in USD by model/provider/org
    rai_tokens_total              Counter Cumulative tokens by model/provider/type/org
    rai_guardrail_scans_total     Counter Guardrail scans by result/org
    rai_drift_alerts_total        Counter Drift alerts fired by severity/org
    rai_active_ws_connections     Gauge   Live WebSocket connections
    rai_webhook_deliveries_total  Counter Webhook deliveries by event/success/org

Per-tenant labeling, and its tradeoff: every governance metric now carries
an `org_id` label so a per-tenant Grafana breakdown is possible (closing
the gap `grafana/dashboards/rai-overview.json` used to document). The
tradeoff is Prometheus time-series cardinality — each label combination
is its own series, so total series scale with (models × providers ×
orgs). At today's scale (a handful of self-hosted orgs per deployment)
this is a non-issue; a deployment expecting thousands of active orgs
should watch `prometheus_tsdb_symbol_table_size_bytes` /
`scrape_samples_scraped` and consider dropping `org_id` at the Prometheus
scrape-config relabeling stage (not in this code) if cardinality becomes
a real cost. `org_id` is `"unscoped"` for requests made without org
context (e.g. legacy flat-API-key auth), never omitted or null, so every
series stays queryable.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    generate_latest,
)

# ── Gauges ────────────────────────────────────────────────────────────────────

trust_score_gauge = Gauge(
    "rai_trust_score",
    "Current trust score (0–100) for a model/provider/org",
    ["model", "provider", "org_id"],
)

active_ws_connections = Gauge(
    "rai_active_ws_connections",
    "Number of live WebSocket dashboard connections",
)

# ── Counters ──────────────────────────────────────────────────────────────────

requests_total = Counter(
    "rai_requests_total",
    "Total HTTP API requests",
    ["endpoint", "status"],
)

cost_usd_total = Counter(
    "rai_cost_usd_total",
    "Cumulative AI cost in USD",
    ["model", "provider", "org_id"],
)

tokens_total = Counter(
    "rai_tokens_total",
    "Cumulative tokens processed",
    ["model", "provider", "token_type", "org_id"],
)

guardrail_scans_total = Counter(
    "rai_guardrail_scans_total",
    "Total guardrail scans",
    ["result", "org_id"],  # result: clean | blocked
)

drift_alerts_total = Counter(
    "rai_drift_alerts_total",
    "Total drift alerts fired",
    ["severity", "org_id"],  # severity: LOW | MEDIUM | HIGH
)

webhook_deliveries_total = Counter(
    "rai_webhook_deliveries_total",
    "Total webhook delivery attempts",
    ["event", "success", "org_id"],  # success: true | false
)

_UNSCOPED_ORG = "unscoped"


def _org_label(org_id: str | None) -> str:
    """Never emit an empty/null label — keeps every series queryable."""
    return org_id or _UNSCOPED_ORG


# ── Helpers called from app endpoints ─────────────────────────────────────────

def observe_request(endpoint: str, status: int) -> None:
    requests_total.labels(endpoint=endpoint, status=str(status)).inc()


def observe_trust_score(model: str, provider: str, score: float, org_id: str | None = None) -> None:
    trust_score_gauge.labels(model=model, provider=provider, org_id=_org_label(org_id)).set(score)


def observe_cost(
    model: str, provider: str, cost_usd: float, input_tok: int, output_tok: int, org_id: str | None = None,
) -> None:
    org = _org_label(org_id)
    cost_usd_total.labels(model=model, provider=provider, org_id=org).inc(cost_usd)
    tokens_total.labels(model=model, provider=provider, token_type="input", org_id=org).inc(input_tok)
    tokens_total.labels(model=model, provider=provider, token_type="output", org_id=org).inc(output_tok)


def observe_guardrail(blocked: bool, org_id: str | None = None) -> None:
    guardrail_scans_total.labels(result="blocked" if blocked else "clean", org_id=_org_label(org_id)).inc()


def observe_drift_alert(severity: str, org_id: str | None = None) -> None:
    drift_alerts_total.labels(severity=severity.upper(), org_id=_org_label(org_id)).inc()


def observe_websocket_connections(count: int) -> None:
    active_ws_connections.set(count)


def observe_webhook_delivery(event: str, success: bool, org_id: str | None = None) -> None:
    webhook_deliveries_total.labels(
        event=event, success=str(success).lower(), org_id=_org_label(org_id),
    ).inc()


def get_metrics_output() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
