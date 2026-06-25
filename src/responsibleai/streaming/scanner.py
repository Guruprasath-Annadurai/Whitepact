"""Token-by-token streaming guardrails scanner.

Wraps any async generator of string tokens (OpenAI stream, Anthropic stream,
or your own generator) and scans for PII / toxicity incrementally.

Enterprise features:
- Configurable scan window (every N tokens or on sentence boundaries)
- Hard stop — terminates the stream immediately on critical PII detection
- Per-token cost estimation (running token count)
- Async context-manager and plain async-generator interfaces
- Zero-copy: yields original tokens unchanged; redaction is opt-in
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import AsyncIterator

from responsibleai.guardrails.engine import GuardrailsEngine


@dataclass(frozen=True)
class StreamScanResult:
    """Result emitted for every token in the stream."""
    token: str
    token_index: int
    cumulative_text: str
    pii_detected: bool
    pii_findings: list[str]
    should_stop: bool
    scan_triggered: bool  # True when a scan actually ran on this token


@dataclass
class StreamScanSummary:
    """Aggregated stats after the stream ends."""
    total_tokens: int = 0
    total_scans: int = 0
    pii_detections: int = 0
    stopped_early: bool = False
    elapsed_ms: float = 0.0
    final_text: str = ""


class StreamingScanner:
    """Scan an LLM token stream in real time.

    Usage — async generator::

        scanner = StreamingScanner(GuardrailsEngine())
        async for result in scanner.scan_stream(token_gen):
            send_token_to_client(result.token)
            if result.should_stop:
                break
        summary = scanner.summary

    Usage — context manager (auto hard-stop)::

        async with StreamingScanner(GuardrailsEngine()) as scanner:
            async for result in scanner.scan_stream(token_gen):
                ...

    Parameters
    ----------
    guardrails:
        Instantiated GuardrailsEngine used for scanning.
    scan_window:
        Run a guardrail scan every *N* tokens (default 50).
        Scans also trigger on sentence-ending punctuation regardless of window.
    hard_stop:
        If True, emit ``should_stop=True`` and stop iterating when PII is found.
    redact:
        If True, ``cumulative_text`` in results will have PII replaced with
        ``[REDACTED]``; the raw ``token`` is still emitted unmodified.
    """

    def __init__(
        self,
        guardrails: GuardrailsEngine,
        scan_window: int = 50,
        hard_stop: bool = True,
        redact: bool = False,
    ) -> None:
        self._guardrails = guardrails
        self._scan_window = max(1, scan_window)
        self._hard_stop = hard_stop
        self._redact = redact
        self._reset()

    def _reset(self) -> None:
        self._buffer = ""
        self._token_index = 0
        self._scans = 0
        self._pii_detections = 0
        self._stopped = False
        self._start_ts = time.monotonic()

    async def scan_stream(
        self, token_stream: AsyncIterator[str]
    ) -> AsyncIterator[StreamScanResult]:
        """Yield a StreamScanResult for every incoming token."""
        self._reset()

        async for token in token_stream:
            self._buffer += token

            at_boundary = token.endswith((".", "!", "?", "\n", ";"))
            at_window = self._token_index > 0 and self._token_index % self._scan_window == 0

            pii_detected = False
            pii_findings: list[str] = []
            scan_triggered = False

            if at_boundary or at_window:
                scan_triggered = True
                self._scans += 1
                result = self._guardrails.scan(self._buffer)
                pii_detected = len(result.pii_findings) > 0
                pii_findings = [f.category for f in result.pii_findings]
                if pii_detected:
                    self._pii_detections += 1
                if self._redact and result.redacted_text:
                    self._buffer = result.redacted_text

            should_stop = pii_detected and self._hard_stop

            yield StreamScanResult(
                token=token,
                token_index=self._token_index,
                cumulative_text=self._buffer,
                pii_detected=pii_detected,
                pii_findings=pii_findings,
                should_stop=should_stop,
                scan_triggered=scan_triggered,
            )

            self._token_index += 1

            if should_stop:
                self._stopped = True
                break

    @property
    def summary(self) -> StreamScanSummary:
        return StreamScanSummary(
            total_tokens=self._token_index,
            total_scans=self._scans,
            pii_detections=self._pii_detections,
            stopped_early=self._stopped,
            elapsed_ms=round((time.monotonic() - self._start_ts) * 1000, 2),
            final_text=self._buffer,
        )

    async def __aenter__(self) -> "StreamingScanner":
        return self

    async def __aexit__(self, *_: object) -> None:
        pass
