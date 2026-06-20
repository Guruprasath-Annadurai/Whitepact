"""
Hallucination Detector — estimate factual reliability of LLM outputs.

Three independent signals:
1. Self-consistency  — how much do multiple candidate responses agree?
2. Hedging           — how much uncertain language does the text contain?
3. Unsupported claims — specific factual claims without source attribution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

_HEDGING_PATTERNS: list[str] = [
    r"\bi\s+(?:think|believe|assume|suspect)\b",
    r"\bi'?m\s+not\s+(?:sure|certain|100%)\b",
    r"\b(?:possibly|perhaps|maybe|might\s+be|could\s+be)\b",
    r"\bit\s+(?:seems|appears|looks\s+like)\b",
    r"\b(?:allegedly|reportedly|supposedly)\b",
    r"\b(?:some\s+sources\s+say|it\s+is\s+(?:possible|unclear|uncertain))\b",
]

_FACTUAL_CLAIM_PATTERNS: list[str] = [
    r"\b\d{4}\b",
    r"\b\d[\d,]*\.?\d*\s*(?:percent|%|million|billion|thousand|trillion)\b",
    r"\b(?:according\s+to|research\s+shows|studies\s+show|scientists\s+found|data\s+shows|experts\s+say)\b",
    r"\bon\s+[A-Z][a-z]+\s+\d+,?\s+\d{4}\b",
    r"\bin\s+(?:19|20)\d{2}\b",
]

_ATTRIBUTION_PATTERNS: list[str] = [
    r"\b(?:according\s+to|source:|cited\s+in|from\s+the\s+study|reference:|see\s+also)\b",
    r"\[[\d,]+\]",  # academic citation markers like [1] or [1,2]
    r"\([\w\s]+,\s*\d{4}\)",  # APA-style (Author, Year)
]

_COMPILED_HEDGING = [re.compile(p, re.IGNORECASE) for p in _HEDGING_PATTERNS]
_COMPILED_FACTUAL = [re.compile(p, re.IGNORECASE) for p in _FACTUAL_CLAIM_PATTERNS]
_COMPILED_ATTRIBUTION = [re.compile(p, re.IGNORECASE) for p in _ATTRIBUTION_PATTERNS]


def _risk_level(score: float) -> str:
    if score < 0.25:
        return "low"
    if score < 0.50:
        return "medium"
    if score < 0.75:
        return "high"
    return "critical"


@dataclass(frozen=True)
class HallucinationResult:
    text: str
    consistency_score: float
    hedging_score: float
    unsupported_claims: list[str]
    hallucination_risk: float
    risk_level: str
    num_candidates: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "hallucination_risk": round(self.hallucination_risk, 4),
            "risk_level": self.risk_level,
            "consistency_score": round(self.consistency_score, 4),
            "hedging_score": round(self.hedging_score, 4),
            "unsupported_claims_count": len(self.unsupported_claims),
            "unsupported_claims_sample": self.unsupported_claims[:5],
            "num_candidates": self.num_candidates,
        }


class HallucinationDetector:
    """
    Estimate hallucination risk in LLM output.

    Parameters
    ----------
    consistency_weight : float
        Weight for self-consistency signal (default 0.40).
    hedging_weight : float
        Weight for hedging language signal (default 0.30).
    unsupported_weight : float
        Weight for unsupported factual claims signal (default 0.30).
    """

    def __init__(
        self,
        consistency_weight: float = 0.40,
        hedging_weight: float = 0.30,
        unsupported_weight: float = 0.30,
    ) -> None:
        total = consistency_weight + hedging_weight + unsupported_weight
        if not (0.999 < total < 1.001):
            raise ValueError(
                f"Weights must sum to 1.0; got {total:.4f}"
            )
        self._w_consistency = consistency_weight
        self._w_hedging = hedging_weight
        self._w_unsupported = unsupported_weight

    def analyze(
        self,
        text: str,
        candidates: list[str] | None = None,
    ) -> HallucinationResult:
        """
        Analyze *text* for hallucination risk.

        Parameters
        ----------
        text : str
            The primary LLM response to evaluate.
        candidates : list[str] | None
            Additional responses to the same prompt used for consistency
            scoring. If None, consistency is treated as unknown (0.5).
        """
        if candidates:
            consistency = self._consistency_score([text] + candidates)
        else:
            consistency = 0.5

        hedging = self._hedging_score(text)
        unsupported = self._extract_unsupported_claims(text)
        unsupported_risk = min(len(unsupported) / 5.0, 1.0)

        # Invert consistency: low agreement → high risk
        risk = (
            self._w_consistency * (1.0 - consistency)
            + self._w_hedging * hedging
            + self._w_unsupported * unsupported_risk
        )

        return HallucinationResult(
            text=text,
            consistency_score=round(float(consistency), 4),
            hedging_score=round(float(hedging), 4),
            unsupported_claims=unsupported,
            hallucination_risk=round(float(risk), 4),
            risk_level=_risk_level(risk),
            num_candidates=len(candidates) if candidates else 0,
        )

    def _consistency_score(self, texts: list[str]) -> float:
        if len(texts) < 2:
            return 1.0
        try:
            vec = TfidfVectorizer(stop_words="english", min_df=1)
            tfidf = vec.fit_transform(texts)
            sims = cosine_similarity(tfidf[0:1], tfidf[1:]).flatten()
            return float(np.clip(np.mean(sims), 0.0, 1.0))
        except ValueError:
            return 0.5

    def _hedging_score(self, text: str) -> float:
        words = max(len(text.split()), 1)
        matches = sum(len(p.findall(text)) for p in _COMPILED_HEDGING)
        # Normalise by expected hedging density (1 hedge per 20 words is high)
        return float(np.clip(matches / max(words / 20.0, 1.0), 0.0, 1.0))

    def _extract_unsupported_claims(self, text: str) -> list[str]:
        sentences = [s.strip() for s in re.split(r"[.!?]", text) if s.strip()]
        unsupported: list[str] = []
        for sentence in sentences:
            has_factual = any(p.search(sentence) for p in _COMPILED_FACTUAL)
            has_attribution = any(p.search(sentence) for p in _COMPILED_ATTRIBUTION)
            if has_factual and not has_attribution:
                unsupported.append(sentence[:150])
        return unsupported
