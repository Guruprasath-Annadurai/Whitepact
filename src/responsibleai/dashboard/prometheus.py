"""Prometheus metrics definitions and helpers.

Exposes a /metrics endpoint compatible with any Prometheus scraper
(Grafana, Datadog agent, VictoriaMetrics, etc.).

Metrics exported:
    rai_trust_score               Gauge   Current trust score per model/provider
    rai_requests_total            Counter API requests by endpoint and HTTP status
    rai_cost_usd_total            Counter Cumulative cost in USD by model/provider
    rai_tokens_total              Counter Cumulative tokens by model/provider/type
    rai_guardrail_scans_total     Counter Guardrail scans by result (clean/blocked)
    rai_drift_alerts_total        Counter Drift alerts fired by severity
    rai_active_ws_connections     Gauge   Live WebSocket connections
    rai_webhook_deliveries_total  Counter Webhook deliveries by event/success
"""

from __future__ import annotations

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    REGISTRY,
)

# ── Gauges ────────────────────────────────────────────────────────────────────

trust_score_gauge = Gauge(
    "rai_trust_score",
    "Current trust score (0–100) for a model/provider pair",
    ["model", "provider"],
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
    ["model", "provider"],
)

tokens_total = Counter(
    "rai_tokens_total",
    "Cumulative tokens processed",
    ["model", "provider", "token_type"],
)

guardrail_scans_total = Counter(
    "rai_guardrail_scans_total",
    "Total guardrail scans",
    ["result"],  # clean | blocked
)

drift_alerts_total = Counter(
    "rai_drift_alerts_total",
    "Total drift alerts fired",
    ["severity"],  # LOW | MEDIUM | HIGH
)

webhook_deliveries_total = Counter(
    "rai_webhook_deliveries_total",
    "Total webhook delivery attempts",
    ["event", "success"],  # success: true | false
)


# ── Helpers called from app endpoints ─────────────────────────────────────────

def observe_request(endpoint: str, status: int) -> None:
    requests_total.labels(endpoint=endpoint, status=str(status)).inc()


def observe_trust_score(model: str, provider: str, score: float) -> None:
    trust_score_gauge.labels(model=model, provider=provider).set(score)


def observe_cost(model: str, provider: str, cost_usd: float, input_tok: int, output_tok: int) -> None:
    cost_usd_total.labels(model=model, provider=provider).inc(cost_usd)
    tokens_total.labels(model=model, provider=provider, token_type="input").inc(input_tok)
    tokens_total.labels(model=model, provider=provider, token_type="output").inc(output_tok)


def observe_guardrail(blocked: bool) -> None:
    guardrail_scans_total.labels(result="blocked" if blocked else "clean").inc()


def observe_drift_alert(severity: str) -> None:
    drift_alerts_total.labels(severity=severity.upper()).inc()


def observe_websocket_connections(count: int) -> None:
    active_ws_connections.set(count)


def observe_webhook_delivery(event: str, success: bool) -> None:
    webhook_deliveries_total.labels(event=event, success=str(success).lower()).inc()


def get_metrics_output() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
