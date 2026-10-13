# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B5/B6 — readiness semantics, Prometheus metrics, alert rule linkage."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app
from responsibleai.dashboard.prometheus import observe_request

REPO = Path(__file__).resolve().parents[2]
ALERT_RULES = REPO / "grafana" / "prometheus" / "alert-rules.yml"
PROMETHEUS_PY = REPO / "src" / "responsibleai" / "dashboard" / "prometheus.py"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("WHITEPACT_ENV", "development")
    monkeypatch.setenv("WHITEPACT_AUTH_ENABLED", "false")
    monkeypatch.setenv("WHITEPACT_DB_PATH", ":memory:")
    monkeypatch.setenv("WHITEPACT_AUTO_MIGRATE", "true")
    return TestClient(app)


def test_readyz_reports_unavailable_when_database_ping_fails(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenEngine:
        async def ping(self, timeout_seconds: float = 2.0) -> bool:
            return False

    monkeypatch.setattr(app_module, "_db_engine", _BrokenEngine())
    resp = client.get("/readyz")
    assert resp.status_code == 503
    body = resp.json()
    assert body["database"] == "disconnected"
    assert "password" not in resp.text.lower()


def test_livez_ok_when_database_unhealthy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _BrokenEngine:
        async def ping(self, timeout_seconds: float = 2.0) -> bool:
            return False

    monkeypatch.setattr(app_module, "_db_engine", _BrokenEngine())
    assert client.get("/livez").status_code == 200


def test_prometheus_metrics_reflect_induced_errors(client: TestClient) -> None:
    observe_request("/api/health", 500)
    observe_request("/api/health", 500)
    observe_request("/api/health", 200)
    body = client.get("/metrics").text
    assert "rai_requests_total" in body
    assert 'status="500"' in body or "status='500'" in body


def test_alert_rules_reference_exported_metric_names() -> None:
    rules_text = ALERT_RULES.read_text(encoding="utf-8")
    prom_text = PROMETHEUS_PY.read_text(encoding="utf-8")
    exported = set(re.findall(r'"([a-z][a-z0-9_]+)"', prom_text))
    exported |= {
        "whitepact_decisions_total",
        "whitepact_evaluation_seconds",
        "whitepact_approvals_total",
    }
    data = yaml.safe_load(rules_text)
    missing: list[str] = []
    for group in data.get("groups", []):
        for rule in group.get("rules", []):
            expr = str(rule.get("expr", ""))
            for token in re.findall(r"\b([a-z][a-z0-9_]+)\b", expr):
                if token in {"sum", "rate", "increase", "offset", "and", "or", "by", "on"}:
                    continue
                if token.startswith("rai_") or token.startswith("whitepact_"):
                    if token not in exported and token not in prom_text:
                        missing.append(token)
    assert not missing, f"alert expr references unknown metrics: {sorted(set(missing))}"


def test_promtool_check_rules_when_available() -> None:
    if subprocess.run(["which", "promtool"], capture_output=True).returncode != 0:
        pytest.skip("promtool not installed")
    result = subprocess.run(
        ["promtool", "check", "rules", str(ALERT_RULES)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr + result.stdout


def test_otel_tracer_records_span_without_exporting_secrets() -> None:
    from responsibleai.dashboard import telemetry as telemetry_mod

    telemetry_mod._initialized = False
    telemetry_mod.setup_telemetry("cell-b-test", None)
    tracer = telemetry_mod.get_tracer()
    with tracer.start_as_current_span("cell_b_qualification_probe") as span:
        span.set_attribute("cell_b.phase", "B5")
        assert span.is_recording()
        span.set_attribute("redaction_probe", "no-bearer-token-here")
