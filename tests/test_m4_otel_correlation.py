# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 OTEL correlation proof — nested spans without secret attributes."""

from __future__ import annotations

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SENSITIVE = frozenset({"api_key", "totp", "authorization", "password", "secret"})


def test_nested_spans_share_trace_and_omit_secrets() -> None:
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("whitepact-m4")

    with tracer.start_as_current_span("http_request") as root:
        root.set_attribute("http.route", "/governance/evaluate")
        root.set_attribute("org.id", "org-1")
        with tracer.start_as_current_span("policy_judgment") as child:
            child.set_attribute("decision", "REQUIRE_APPROVAL")

    spans = exporter.get_finished_spans()
    assert len(spans) == 2
    child, parent = spans[0], spans[1]
    assert child.parent is not None
    assert child.context.trace_id == parent.context.trace_id
    for span in spans:
        for key in span.attributes or {}:
            assert not any(s in key.lower() for s in SENSITIVE)
