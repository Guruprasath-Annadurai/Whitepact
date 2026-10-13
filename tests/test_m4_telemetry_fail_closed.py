# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 — tracing/OTEL must not be an authority dependency."""

from __future__ import annotations

import responsibleai.dashboard.telemetry as telemetry


def test_setup_telemetry_without_exporter_uses_noop_tracer() -> None:
    telemetry._initialized = False
    telemetry._tracer = None
    telemetry._meter = None
    telemetry.setup_telemetry("whitepact-test", otlp_endpoint=None)
    tracer = telemetry.get_tracer()
    with tracer.start_as_current_span("m4-fail-closed-smoke"):
        pass
    telemetry.record_evaluation("model", "provider", 0.5, "B")


def test_broken_exporter_does_not_raise_from_record_helpers(monkeypatch) -> None:
    telemetry._initialized = False
    telemetry._tracer = None
    telemetry._meter = None

    def _boom(*_a, **_k):
        raise OSError("exporter unavailable")

    monkeypatch.setattr(telemetry, "setup_telemetry", _boom)
    telemetry.record_guardrail_scan(False, 0)
    telemetry.record_cost("p", "m", 0.0, 0)
