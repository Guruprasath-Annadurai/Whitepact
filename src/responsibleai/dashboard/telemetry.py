"""OpenTelemetry setup — traces and metrics exported via OTLP."""

from __future__ import annotations

import logging
from typing import Any

_tracer = None
_meter = None
_initialized = False


def setup_telemetry(
    service_name: str,
    otlp_endpoint: str | None,
    otlp_headers: dict[str, str] | None = None,
) -> None:
    """
    Initialize OpenTelemetry SDK.

    When ``otlp_endpoint`` is None, a no-op tracer is used so the rest of
    the application code stays clean of conditionals.
    """
    global _tracer, _meter, _initialized

    if _initialized:
        return

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create({"service.name": service_name, "service.version": "0.6.0"})

        tracer_provider = TracerProvider(resource=resource)
        meter_provider_kwargs: dict[str, Any] = {"resource": resource}

        if otlp_endpoint:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

            headers = otlp_headers or {}
            span_exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint}/v1/traces", headers=headers)
            metric_exporter = OTLPMetricExporter(endpoint=f"{otlp_endpoint}/v1/metrics", headers=headers)

            tracer_provider.add_span_processor(BatchSpanProcessor(span_exporter))
            meter_provider_kwargs["metric_readers"] = [
                PeriodicExportingMetricReader(metric_exporter, export_interval_millis=30_000)
            ]

        trace.set_tracer_provider(tracer_provider)
        meter_provider = MeterProvider(**meter_provider_kwargs)
        metrics.set_meter_provider(meter_provider)

        _tracer = trace.get_tracer(service_name)
        _meter = metrics.get_meter(service_name)

        _register_fastapi_instrumentation()
        _initialized = True

    except ImportError:
        logging.getLogger("responsibleai.telemetry").warning(
            "opentelemetry packages not installed — telemetry disabled. "
            "pip install 'biasbuster[telemetry]'"
        )


def _register_fastapi_instrumentation() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass


def get_tracer():
    """Return the active tracer (no-op if OTEL not configured)."""
    if _tracer is not None:
        return _tracer
    try:
        from opentelemetry import trace
        return trace.get_tracer("responsibleai")
    except ImportError:
        return _NoOpTracer()


def get_meter():
    """Return the active meter (no-op if OTEL not configured)."""
    if _meter is not None:
        return _meter
    try:
        from opentelemetry import metrics
        return metrics.get_meter("responsibleai")
    except ImportError:
        return _NoOpMeter()


def record_evaluation(model: str, provider: str, score: float, grade: str) -> None:
    """Emit a trust score evaluation span + metric."""
    try:
        tracer = get_tracer()
        with tracer.start_as_current_span("evaluate_model") as span:
            span.set_attribute("ai.model", model)
            span.set_attribute("ai.provider", provider)
            span.set_attribute("ai.trust_score", score)
            span.set_attribute("ai.grade", grade)
    except Exception:
        pass

    try:
        meter = get_meter()
        histogram = meter.create_histogram(
            "ai.trust_score",
            description="Distribution of model trust scores",
            unit="score",
        )
        histogram.record(score, {"provider": provider, "grade": grade})
    except Exception:
        pass


def record_guardrail_scan(is_blocked: bool, pii_count: int) -> None:
    """Emit a guardrails scan metric."""
    try:
        meter = get_meter()
        counter = meter.create_counter(
            "ai.guardrail.scans",
            description="Total guardrail scans",
        )
        counter.add(1, {"blocked": str(is_blocked), "has_pii": str(pii_count > 0)})
    except Exception:
        pass


def record_cost(provider: str, model: str, total_cost_usd: float, tokens: int) -> None:
    """Emit token cost metrics."""
    try:
        meter = get_meter()
        cost_counter = meter.create_counter(
            "ai.cost.usd",
            description="Cumulative AI spend in USD",
            unit="USD",
        )
        token_counter = meter.create_counter(
            "ai.tokens.total",
            description="Cumulative tokens consumed",
        )
        cost_counter.add(total_cost_usd, {"provider": provider, "model": model})
        token_counter.add(tokens, {"provider": provider, "model": model})
    except Exception:
        pass


class _NoOpTracer:
    def start_as_current_span(self, name: str, **_):
        from contextlib import contextmanager

        @contextmanager
        def _ctx():
            yield _NoOpSpan()

        return _ctx()


class _NoOpSpan:
    def set_attribute(self, *_): pass
    def set_status(self, *_): pass


class _NoOpMeter:
    def create_histogram(self, *_, **__): return _NoOpInstrument()
    def create_counter(self, *_, **__): return _NoOpInstrument()
    def create_gauge(self, *_, **__): return _NoOpInstrument()


class _NoOpInstrument:
    def record(self, *_, **__): pass
    def add(self, *_, **__): pass
