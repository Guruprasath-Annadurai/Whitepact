"""Tests for dashboard.telemetry -- previously entirely untested. Uses the
real `opentelemetry` packages (installed in this environment) for the happy
paths, and `sys.modules` injection to force ImportError for the graceful-
degradation branches, since telemetry.py is designed to work either way."""

from __future__ import annotations

import sys

import pytest

import responsibleai.dashboard.telemetry as telemetry


@pytest.fixture(autouse=True)
def reset_telemetry_globals():
    """telemetry.py caches state in module globals guarded by `_initialized`
    -- reset around every test so setup_telemetry's early-return branch
    doesn't leak state between tests."""
    telemetry._tracer = None
    telemetry._meter = None
    telemetry._initialized = False
    yield
    telemetry._tracer = None
    telemetry._meter = None
    telemetry._initialized = False


class TestSetupTelemetry:
    def test_already_initialized_returns_early(self):
        telemetry._initialized = True
        telemetry._tracer = "sentinel"
        telemetry.setup_telemetry("svc", None)
        assert telemetry._tracer == "sentinel"

    def test_initializes_without_otlp_endpoint(self):
        telemetry.setup_telemetry("svc", None)
        assert telemetry._initialized is True
        assert telemetry._tracer is not None
        assert telemetry._meter is not None

    def test_initializes_with_otlp_endpoint_and_headers(self):
        telemetry.setup_telemetry(
            "svc", "http://localhost:4318", otlp_headers={"x-api-key": "secret"}
        )
        assert telemetry._initialized is True

    def test_initializes_with_otlp_endpoint_no_headers(self):
        telemetry.setup_telemetry("svc", "http://localhost:4318")
        assert telemetry._initialized is True

    def test_import_error_falls_back_gracefully(self, monkeypatch, caplog):
        monkeypatch.setitem(sys.modules, "opentelemetry", None)
        telemetry.setup_telemetry("svc", None)
        assert telemetry._initialized is False


class TestRegisterFastapiInstrumentation:
    def test_succeeds_when_packages_installed(self):
        telemetry._register_fastapi_instrumentation()  # must not raise

    def test_fastapi_instrumentor_import_error_is_swallowed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.fastapi", None)
        telemetry._register_fastapi_instrumentation()  # must not raise

    def test_httpx_instrumentor_import_error_is_swallowed(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "opentelemetry.instrumentation.httpx", None)
        telemetry._register_fastapi_instrumentation()  # must not raise


class TestGetTracer:
    def test_returns_cached_tracer_when_set(self):
        telemetry._tracer = "cached"
        assert telemetry.get_tracer() == "cached"

    def test_returns_real_tracer_when_opentelemetry_available(self):
        tracer = telemetry.get_tracer()
        assert tracer is not None
        assert not isinstance(tracer, telemetry._NoOpTracer)

    def test_returns_noop_tracer_when_opentelemetry_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "opentelemetry", None)
        tracer = telemetry.get_tracer()
        assert isinstance(tracer, telemetry._NoOpTracer)

    def test_noop_tracer_span_context_manager_and_attributes(self):
        tracer = telemetry._NoOpTracer()
        with tracer.start_as_current_span("x") as span:
            span.set_attribute("k", "v")
            span.set_status("ok")


class TestGetMeter:
    def test_returns_cached_meter_when_set(self):
        telemetry._meter = "cached"
        assert telemetry.get_meter() == "cached"

    def test_returns_real_meter_when_opentelemetry_available(self):
        meter = telemetry.get_meter()
        assert meter is not None
        assert not isinstance(meter, telemetry._NoOpMeter)

    def test_returns_noop_meter_when_opentelemetry_unavailable(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "opentelemetry", None)
        meter = telemetry.get_meter()
        assert isinstance(meter, telemetry._NoOpMeter)

    def test_noop_meter_instruments_are_silent(self):
        meter = telemetry._NoOpMeter()
        meter.create_histogram("x").record(1.0)
        meter.create_counter("y").add(1)
        meter.create_gauge("z")


class TestRecordEvaluation:
    def test_succeeds_with_real_tracer_and_meter(self):
        telemetry.record_evaluation("gpt-4o", "openai", 0.9, "A")  # must not raise

    def test_span_failure_is_swallowed(self, monkeypatch):
        def _boom():
            raise RuntimeError("tracer broke")

        monkeypatch.setattr(telemetry, "get_tracer", _boom)
        telemetry.record_evaluation("gpt-4o", "openai", 0.9, "A")  # must not raise

    def test_metric_failure_is_swallowed(self, monkeypatch):
        def _boom():
            raise RuntimeError("meter broke")

        monkeypatch.setattr(telemetry, "get_meter", _boom)
        telemetry.record_evaluation("gpt-4o", "openai", 0.9, "A")  # must not raise


class TestRecordGuardrailScan:
    def test_succeeds_with_real_meter(self):
        telemetry.record_guardrail_scan(True, 2)  # must not raise

    def test_failure_is_swallowed(self, monkeypatch):
        def _boom():
            raise RuntimeError("meter broke")

        monkeypatch.setattr(telemetry, "get_meter", _boom)
        telemetry.record_guardrail_scan(False, 0)  # must not raise


class TestRecordCost:
    def test_succeeds_with_real_meter(self):
        telemetry.record_cost("openai", "gpt-4o", 0.05, 1000)  # must not raise

    def test_failure_is_swallowed(self, monkeypatch):
        def _boom():
            raise RuntimeError("meter broke")

        monkeypatch.setattr(telemetry, "get_meter", _boom)
        telemetry.record_cost("openai", "gpt-4o", 0.05, 1000)  # must not raise
