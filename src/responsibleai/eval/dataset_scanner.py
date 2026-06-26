"""Dataset-level bias and PII scanner for CSV / JSONL uploads."""

from __future__ import annotations

import csv
import io
import json
import re

from responsibleai.eval.models import DatasetRowResult, DatasetScanResult
from responsibleai.guardrails.engine import GuardrailsEngine

_BIAS_PATTERNS: dict[str, list[str]] = {
    "gender": [
        r"\b(he|she|him|her|his|hers)\b",
        r"\b(man|woman|men|women|male|female)\b",
        r"\b(boy|girl|boys|girls)\b",
    ],
    "racial": [
        r"\b(white|black|asian|hispanic|latino|latina|african|european|indigenous)\b",
    ],
    "age": [
        r"\b(old|young|elderly|senior|millennial|boomer|teen|teenager)\b",
    ],
    "religious": [
        r"\b(christian|muslim|jewish|hindu|buddhist|atheist|sikh|mormon)\b",
    ],
    "occupational": [
        r"\b(nurse|doctor|engineer|teacher|secretary|janitor|boss|ceo|maid)\b",
    ],
    "socioeconomic": [
        r"\b(poor|rich|wealthy|homeless|welfare|ghetto|privileged)\b",
    ],
}

_COMPILED_BIAS: dict[str, list[re.Pattern[str]]] = {
    cat: [re.compile(p, re.IGNORECASE) for p in patterns]
    for cat, patterns in _BIAS_PATTERNS.items()
}


class DatasetBiasScanner:
    """Scan CSV or JSONL datasets for bias markers and PII."""

    def __init__(self, guardrails: GuardrailsEngine | None = None) -> None:
        self._guardrails = guardrails or GuardrailsEngine()

    # ── Public API ────────────────────────────────────────────────────────────

    def scan_csv(
        self,
        content: str | bytes,
        filename: str = "upload.csv",
        text_column: str | None = None,
    ) -> DatasetScanResult:
        """Scan a CSV file. If *text_column* is set, only that column is analysed."""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(content))
        rows: list[str] = []
        for row in reader:
            if text_column and text_column in row:
                rows.append(row[text_column])
            else:
                rows.append(" ".join(str(v) for v in row.values()))
        return self._scan_rows(rows, filename)

    def scan_jsonl(
        self,
        content: str | bytes,
        filename: str = "upload.jsonl",
        text_field: str | None = None,
    ) -> DatasetScanResult:
        """Scan a JSONL file. If *text_field* is set, only that field is analysed."""
        if isinstance(content, bytes):
            content = content.decode("utf-8", errors="replace")
        rows: list[str] = []
        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if text_field and isinstance(obj, dict) and text_field in obj:
                    rows.append(str(obj[text_field]))
                elif isinstance(obj, dict):
                    rows.append(" ".join(str(v) for v in obj.values()))
                else:
                    rows.append(str(obj))
            except json.JSONDecodeError:
                rows.append(line)
        return self._scan_rows(rows, filename)

    def scan_texts(self, texts: list[str], filename: str = "texts") -> DatasetScanResult:
        """Scan an in-memory list of text strings."""
        return self._scan_rows(texts, filename)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _scan_rows(self, rows: list[str], filename: str) -> DatasetScanResult:
        result = DatasetScanResult(filename=filename, total_rows=len(rows))
        for i, text in enumerate(rows):
            bias_cats = self._detect_bias_categories(text)
            g = self._guardrails.scan(text)
            flags: list[str] = []
            if bias_cats:
                flags.extend(f"bias:{c}" for c in bias_cats)
            if g.has_pii:
                flags.append("pii")
            if g.has_toxicity:
                flags.append("toxicity")
            score = min(1.0, len(flags) * 0.2)
            result.row_results.append(
                DatasetRowResult(
                    row_index=i,
                    text=text,
                    bias_categories=bias_cats,
                    pii_detected=g.has_pii,
                    toxicity_detected=g.has_toxicity,
                    flags=flags,
                    score=score,
                )
            )
        return result

    @staticmethod
    def _detect_bias_categories(text: str) -> list[str]:
        return [
            cat
            for cat, patterns in _COMPILED_BIAS.items()
            if any(p.search(text) for p in patterns)
        ]
