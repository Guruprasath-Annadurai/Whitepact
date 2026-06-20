"""
Guardrails Engine — PII detection, toxicity filtering, and policy enforcement.

Scans LLM outputs for sensitive data and harmful content before delivery to users.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PIICategory(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"


class ToxicityCategory(str, Enum):
    HATE_SPEECH = "hate_speech"
    VIOLENCE = "violence"
    SELF_HARM = "self_harm"
    SEXUAL_EXPLICIT = "sexual_explicit"


_PII_PATTERNS: dict[PIICategory, str] = {
    PIICategory.EMAIL: r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
    PIICategory.PHONE: r'\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
    PIICategory.SSN: r'\b\d{3}[- ]\d{2}[- ]\d{4}\b',
    PIICategory.CREDIT_CARD: r'\b(?:\d{4}[-\s]?){3}\d{4}\b',
    PIICategory.IP_ADDRESS: (
        r'\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}'
        r'(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b'
    ),
    PIICategory.DATE_OF_BIRTH: (
        r'\b(?:DOB|Date\s+of\s+Birth|Born)\s*:?\s*\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}\b'
    ),
}

_TOXICITY_PATTERNS: dict[ToxicityCategory, list[str]] = {
    ToxicityCategory.HATE_SPEECH: [
        r'\b(?:racial\s+slur|bigot|neo.?nazi|white\s+supremac|antisemit)\b',
    ],
    ToxicityCategory.VIOLENCE: [
        r'\b(?:kill\s+yourself|i\s+will\s+kill\s+you|bomb\s+threat|shoot\s+up|mass\s+shooting)\b',
    ],
    ToxicityCategory.SELF_HARM: [
        r'\b(?:how\s+to\s+commit\s+suicide|step.by.step.*self.harm|instructions.*self.harm)\b',
    ],
    ToxicityCategory.SEXUAL_EXPLICIT: [
        r'\b(?:sexual\s+content\s+involving\s+minor|child\s+sexual\s+abuse\s+material|csam)\b',
    ],
}


@dataclass
class GuardrailsPolicy:
    """Policy configuration for GuardrailsEngine."""

    block_pii: bool = True
    block_toxicity: bool = True
    pii_categories: list[PIICategory] = field(
        default_factory=lambda: list(PIICategory)
    )
    toxicity_categories: list[ToxicityCategory] = field(
        default_factory=lambda: list(ToxicityCategory)
    )
    custom_blocked_patterns: list[str] = field(default_factory=list)
    redact_pii: bool = True


@dataclass
class PIIFinding:
    category: str
    match: str
    start: int
    end: int


@dataclass
class ToxicityFinding:
    category: str
    match: str


@dataclass
class GuardrailsResult:
    text: str
    is_blocked: bool
    pii_findings: list[PIIFinding]
    toxicity_findings: list[ToxicityFinding]
    custom_pattern_matches: list[str]
    redacted_text: str | None
    block_reasons: list[str]

    @property
    def has_pii(self) -> bool:
        return len(self.pii_findings) > 0

    @property
    def has_toxicity(self) -> bool:
        return len(self.toxicity_findings) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_blocked": self.is_blocked,
            "has_pii": self.has_pii,
            "has_toxicity": self.has_toxicity,
            "pii_findings": [
                {"category": f.category, "start": f.start, "end": f.end}
                for f in self.pii_findings
            ],
            "toxicity_findings": [
                {"category": f.category, "match": f.match}
                for f in self.toxicity_findings
            ],
            "custom_pattern_matches": self.custom_pattern_matches,
            "block_reasons": self.block_reasons,
            "redacted_text": self.redacted_text,
        }


class GuardrailsEngine:
    """
    Scan LLM output for PII, toxicity, and custom policy violations.

    Design intent: acts as the final output filter before responses reach
    end users. Optionally redacts detected PII in-place rather than blocking
    the response entirely.
    """

    def __init__(self, policy: GuardrailsPolicy | None = None) -> None:
        self._policy = policy or GuardrailsPolicy()

        self._compiled_pii: dict[PIICategory, re.Pattern[str]] = {
            cat: re.compile(pattern, re.IGNORECASE)
            for cat, pattern in _PII_PATTERNS.items()
            if cat in self._policy.pii_categories
        }
        self._compiled_toxicity: dict[ToxicityCategory, list[re.Pattern[str]]] = {
            cat: [re.compile(p, re.IGNORECASE) for p in patterns]
            for cat, patterns in _TOXICITY_PATTERNS.items()
            if cat in self._policy.toxicity_categories
        }
        self._compiled_custom: list[re.Pattern[str]] = [
            re.compile(p, re.IGNORECASE)
            for p in self._policy.custom_blocked_patterns
        ]

    def scan(self, text: str) -> GuardrailsResult:
        """
        Scan *text* against the configured policy.

        Returns a GuardrailsResult describing what was found and whether
        the text should be blocked or redacted.
        """
        pii_findings: list[PIIFinding] = []
        toxicity_findings: list[ToxicityFinding] = []
        custom_matches: list[str] = []
        block_reasons: list[str] = []

        if self._policy.block_pii:
            for cat, pattern in self._compiled_pii.items():
                for m in pattern.finditer(text):
                    pii_findings.append(
                        PIIFinding(
                            category=cat.value,
                            match=m.group(),
                            start=m.start(),
                            end=m.end(),
                        )
                    )
            if pii_findings:
                cats = sorted({f.category for f in pii_findings})
                block_reasons.append(f"PII detected: {', '.join(cats)}")

        if self._policy.block_toxicity:
            for cat, compiled_patterns in self._compiled_toxicity.items():
                for cp in compiled_patterns:
                    for m in cp.finditer(text):
                        toxicity_findings.append(
                            ToxicityFinding(category=cat.value, match=m.group())
                        )
            if toxicity_findings:
                cats = sorted({f.category for f in toxicity_findings})
                block_reasons.append(f"Toxicity detected: {', '.join(cats)}")

        for cp in self._compiled_custom:
            for m in cp.finditer(text):
                custom_matches.append(m.group())
        if custom_matches:
            block_reasons.append(
                f"Custom policy violation: {len(custom_matches)} match(es)"
            )

        redacted: str | None = None
        if self._policy.redact_pii and pii_findings:
            redacted = text
            for finding in sorted(pii_findings, key=lambda f: f.start, reverse=True):
                redacted = (
                    redacted[: finding.start] + "[REDACTED]" + redacted[finding.end :]
                )

        return GuardrailsResult(
            text=text,
            is_blocked=bool(block_reasons),
            pii_findings=pii_findings,
            toxicity_findings=toxicity_findings,
            custom_pattern_matches=custom_matches,
            redacted_text=redacted,
            block_reasons=block_reasons,
        )
