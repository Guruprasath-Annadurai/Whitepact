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
    whitepact_decisions_total     Counter Governance decisions by decision/risk_tier/org
    whitepact_evaluation_seconds  Histogram WhitePactRuntimeGateway.evaluate() latency by org
    whitepact_approvals_total     Counter Approval resolutions by outcome/org
    whitepact_heart_denials_total Counter Heart legitimacy denials by reason/org (Phase 14)
    whitepact_revocations_total   Counter Root/consent revocations by target_type/org (Phase 14)
    whitepact_audit_chain_failures_total Counter Evidence-chain tamper detections by org (Phase 14)
    whitepact_approval_queue_backlog Gauge Live PENDING approval count by org (Phase 14)
    whitepact_db_pool_checked_out Gauge  DB connection-pool connections currently checked out
    whitepact_db_pool_size        Gauge  DB connection-pool configured size

The `whitepact_*` metrics are named separately from the `rai_*` ones
above (not `rai_governance_decisions_total`) deliberately — they belong
to the v3 authority-layer pipeline (`governance/gateway.py`), a
distinct subsystem from the pre-v3 `rai_*` product surface these other
metrics instrument, and the naming makes that origin traceable in any
dashboard or alert rule built against them.

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

from typing import TYPE_CHECKING

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

if TYPE_CHECKING:
    from responsibleai.db.engine import DatabaseEngine

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

governance_decisions_total = Counter(
    "whitepact_decisions_total",
    "Total governance decisions produced by WhitePactRuntimeGateway.evaluate()",
    ["decision", "risk_tier", "org_id"],
)

governance_evaluation_seconds = Histogram(
    "whitepact_evaluation_seconds",
    "WhitePactRuntimeGateway.evaluate() wall-clock latency",
    ["org_id"],
    # Sub-millisecond to low-single-digit-millisecond buckets -- evaluate()
    # is a synchronous, regex-only, no-I/O call (gateway.py's own module
    # docstring: "No LLM call anywhere in this file"), so anything above
    # the top bucket here is itself a signal worth alerting on.
    buckets=(0.0005, 0.001, 0.0025, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

governance_approvals_total = Counter(
    "whitepact_approvals_total",
    "Total ApprovalRepository.resolve() outcomes",
    ["outcome", "org_id"],  # outcome: APPROVED | DENIED
)

# Enterprise Readiness Phase 14 (metrics enumeration): the specific
# names 00_MASTER_READINESS_AUDIT.md's "Observability" row flagged as
# unconfirmed -- denied decisions were already covered by
# `whitepact_decisions_total{decision="DENY"}` above; these four close
# the rest (Heart failures, revocation failures, audit failures, queue
# backlog), plus DB pool usage.

heart_denials_total = Counter(
    "whitepact_heart_denials_total",
    "Total Heart legitimacy denials (resolve_authority_grant() not legitimate)",
    ["reason", "org_id"],
)

revocations_total = Counter(
    "whitepact_revocations_total",
    "Total root-authority/consent revocations recorded",
    ["target_type", "org_id"],  # target_type: root_authority | consent
)

audit_chain_failures_total = Counter(
    "whitepact_audit_chain_failures_total",
    "Total evidence hash-chain verifications that found tampering",
    ["org_id"],
)

approval_queue_backlog = Gauge(
    "whitepact_approval_queue_backlog",
    "Live count of PENDING approvals, tracked incrementally from process "
    "start -- does NOT reflect approvals already PENDING in the DB before "
    "this process started (no startup backfill query); restart a process "
    "and this resets to 0 even though the DB may still hold pending rows.",
    ["org_id"],
)

db_pool_checked_out = Gauge(
    "whitepact_db_pool_checked_out",
    "DB connection-pool connections currently checked out (sampled at scrape time)",
)

db_pool_size = Gauge(
    "whitepact_db_pool_size",
    "DB connection-pool configured size (sampled at scrape time)",
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
    model: str,
    provider: str,
    cost_usd: float,
    input_tok: int,
    output_tok: int,
    org_id: str | None = None,
) -> None:
    org = _org_label(org_id)
    cost_usd_total.labels(model=model, provider=provider, org_id=org).inc(cost_usd)
    tokens_total.labels(model=model, provider=provider, token_type="input", org_id=org).inc(
        input_tok
    )
    tokens_total.labels(model=model, provider=provider, token_type="output", org_id=org).inc(
        output_tok
    )


def observe_guardrail(blocked: bool, org_id: str | None = None) -> None:
    guardrail_scans_total.labels(
        result="blocked" if blocked else "clean", org_id=_org_label(org_id)
    ).inc()


def observe_drift_alert(severity: str, org_id: str | None = None) -> None:
    drift_alerts_total.labels(severity=severity.upper(), org_id=_org_label(org_id)).inc()


def observe_websocket_connections(count: int) -> None:
    active_ws_connections.set(count)


def observe_webhook_delivery(event: str, success: bool, org_id: str | None = None) -> None:
    webhook_deliveries_total.labels(
        event=event,
        success=str(success).lower(),
        org_id=_org_label(org_id),
    ).inc()


def observe_governance_decision(
    decision: str,
    risk_tier: str | None,
    duration_seconds: float,
    org_id: str | None = None,
) -> None:
    org = _org_label(org_id)
    governance_decisions_total.labels(
        decision=decision,
        risk_tier=risk_tier or "UNCLASSIFIED",
        org_id=org,
    ).inc()
    governance_evaluation_seconds.labels(org_id=org).observe(duration_seconds)


def observe_governance_approval(outcome: str, org_id: str | None = None) -> None:
    governance_approvals_total.labels(outcome=outcome, org_id=_org_label(org_id)).inc()


def observe_heart_denial(reason: str, org_id: str | None = None) -> None:
    heart_denials_total.labels(reason=reason, org_id=_org_label(org_id)).inc()


def observe_revocation(target_type: str, org_id: str | None = None) -> None:
    revocations_total.labels(target_type=target_type, org_id=_org_label(org_id)).inc()


def observe_audit_chain_failure(org_id: str | None = None) -> None:
    audit_chain_failures_total.labels(org_id=_org_label(org_id)).inc()


def observe_approval_queued(org_id: str | None = None) -> None:
    approval_queue_backlog.labels(org_id=_org_label(org_id)).inc()


def observe_approval_dequeued(org_id: str | None = None) -> None:
    approval_queue_backlog.labels(org_id=_org_label(org_id)).dec()


def observe_db_pool(engine: DatabaseEngine) -> None:
    """Sample live pool stats at /metrics scrape time -- SQLite's
    AsyncAdaptedQueuePool(pool_size=1) still exposes the same
    checkedout()/size() API, so this is safe to call unconditionally
    regardless of backend."""
    pool = engine.raw.pool
    checked_out = getattr(pool, "checkedout", None)
    size = getattr(pool, "size", None)
    if callable(checked_out):
        db_pool_checked_out.set(checked_out())
    if callable(size):
        db_pool_size.set(size())


def get_metrics_output() -> tuple[bytes, str]:
    """Return (body, content_type) for the /metrics endpoint."""
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
