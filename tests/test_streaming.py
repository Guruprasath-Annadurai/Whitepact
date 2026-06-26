"""Tests for the StreamingScanner token-by-token guardrail engine."""

from __future__ import annotations

import pytest

from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.streaming.scanner import StreamingScanner, StreamScanResult, StreamScanSummary


async def _gen(*tokens: str):
    for t in tokens:
        yield t


@pytest.fixture()
def scanner() -> StreamingScanner:
    return StreamingScanner(GuardrailsEngine(), scan_window=5, hard_stop=True)


@pytest.fixture()
def scanner_no_stop() -> StreamingScanner:
    return StreamingScanner(GuardrailsEngine(), scan_window=5, hard_stop=False)


# ── Basic behaviour ────────────────────────────────────────────────────────────

class TestStreamingScanner:
    async def test_yields_all_tokens_clean_stream(self, scanner):
        tokens = ["Hello", " world", "!"]
        results = [r async for r in scanner.scan_stream(_gen(*tokens))]
        assert len(results) == 3
        assert [r.token for r in results] == tokens

    async def test_token_index_increments(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("a", "b", "c"))]
        assert [r.token_index for r in results] == [0, 1, 2]

    async def test_cumulative_text_builds(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("Hello", " world"))]
        assert results[-1].cumulative_text == "Hello world"

    async def test_result_is_frozen_dataclass(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("hi"))]
        assert isinstance(results[0], StreamScanResult)

    async def test_scan_triggers_on_sentence_boundary(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("Hello", "."))]
        boundary_result = results[1]
        assert boundary_result.scan_triggered is True

    async def test_scan_triggers_at_window(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=3, hard_stop=False)
        tokens = ["a"] * 6
        results = [r async for r in s.scan_stream(_gen(*tokens))]
        # tokens 3 and 6 (indices 2, 5) should trigger
        triggered = [r for r in results if r.scan_triggered]
        assert len(triggered) >= 1

    async def test_no_pii_in_clean_text(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("The weather is great today."))]
        assert not any(r.pii_detected for r in results)

    async def test_pii_detected_and_hard_stop(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=1, hard_stop=True)
        tokens = ["My", " SSN", " is", " 123-45-6789", " and", " more", "."]
        results = [r async for r in s.scan_stream(_gen(*tokens))]
        assert any(r.pii_detected for r in results)
        assert any(r.should_stop for r in results)
        # stream stops early
        assert len(results) < len(tokens)

    async def test_no_hard_stop_when_disabled(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=1, hard_stop=False)
        tokens = ["SSN", ":", " 123-45-6789", " done."]
        results = [r async for r in s.scan_stream(_gen(*tokens))]
        # All tokens yielded even if PII found
        assert len(results) == len(tokens)
        assert all(r.should_stop is False for r in results)

    async def test_summary_after_clean_stream(self, scanner):
        async for _ in scanner.scan_stream(_gen("hello", " world")):
            pass
        s = scanner.summary
        assert isinstance(s, StreamScanSummary)
        assert s.total_tokens == 2
        assert s.stopped_early is False
        assert s.elapsed_ms >= 0

    async def test_summary_stopped_early(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=1, hard_stop=True)
        tokens = ["a"] * 3 + ["SSN 123-45-6789."] + ["b"] * 10
        async for _ in s.scan_stream(_gen(*tokens)):
            pass
        assert s.summary.stopped_early is True
        assert s.summary.total_tokens < len(tokens)

    async def test_empty_stream(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen())]
        assert results == []
        assert scanner.summary.total_tokens == 0

    async def test_context_manager(self):
        async with StreamingScanner(GuardrailsEngine()) as s:
            results = [r async for r in s.scan_stream(_gen("safe", " text"))]
        assert len(results) == 2

    async def test_reset_on_new_scan(self, scanner):
        async for _ in scanner.scan_stream(_gen("hello")):
            pass
        async for _ in scanner.scan_stream(_gen("world", "!")):
            pass
        # second scan starts fresh
        assert scanner.summary.total_tokens == 2

    async def test_pii_findings_list_populated(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=1, hard_stop=False)
        tokens = ["email@example.com."]
        results = [r async for r in s.scan_stream(_gen(*tokens))]
        pii_results = [r for r in results if r.pii_detected]
        assert len(pii_results) >= 1
        assert isinstance(pii_results[0].pii_findings, list)

    async def test_newline_triggers_scan(self, scanner):
        results = [r async for r in scanner.scan_stream(_gen("line1", "\n"))]
        assert results[1].scan_triggered is True

    async def test_summary_pii_detections_count(self):
        s = StreamingScanner(GuardrailsEngine(), scan_window=1, hard_stop=False)
        tokens = ["SSN 123-45-6789.", " email@test.com."]
        async for _ in s.scan_stream(_gen(*tokens)):
            pass
        assert s.summary.pii_detections >= 1
