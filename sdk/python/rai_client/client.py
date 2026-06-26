"""Async HTTP client for the ResponsibleAI Governance Platform API."""

from __future__ import annotations

from typing import Any

import httpx

from .models import (
    ComplianceReport,
    CostRecord,
    EvalCompareResult,
    GuardrailScan,
    HallucinationAnalysis,
    TrustScore,
)

_DEFAULT_BASE = "http://localhost:8765"
_API_VERSION  = "v1"


class RAIClient:
    """Async client for the ResponsibleAI Governance Platform.

    Usage::

        async with RAIClient(api_key="rai-xxx", base_url="https://rai.example.com") as client:
            score = await client.evaluate(
                model_name="gpt-4o", provider="openai",
                fairness=0.85, privacy=0.90, security=0.80,
                robustness=0.75, compliance=0.88, authenticity=0.92,
            )
            print(score.grade)
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = _DEFAULT_BASE,
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key  = api_key
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    def _headers(self) -> dict[str, str]:
        h = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._key:
            h["Authorization"] = f"Bearer {self._key}"
        return h

    def _url(self, path: str) -> str:
        return f"{self._base}/api/{_API_VERSION}/{path.lstrip('/')}"

    async def __aenter__(self) -> RAIClient:
        self._client = httpx.AsyncClient(
            headers=self._headers(),
            timeout=self._timeout,
        )
        return self

    async def __aexit__(self, *_: object) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        c = self._client or httpx.AsyncClient(headers=self._headers(), timeout=self._timeout)
        resp = await c.post(self._url(path), json=body)
        resp.raise_for_status()
        return resp.json()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        c = self._client or httpx.AsyncClient(headers=self._headers(), timeout=self._timeout)
        resp = await c.get(self._url(path), params=params or {})
        resp.raise_for_status()
        return resp.json()

    # ── Trust Scoring ──────────────────────────────────────────────────────────

    async def evaluate(
        self,
        model_name: str,
        provider: str,
        fairness: float = 0.75,
        privacy: float = 0.80,
        security: float = 0.70,
        robustness: float = 0.75,
        compliance: float = 0.80,
        authenticity: float = 0.85,
        use_case: str = "general",
        record_drift: bool = True,
    ) -> TrustScore:
        """Compute and record a trust score for a model."""
        data = await self._post("evaluate", {
            "model_name": model_name,
            "provider": provider,
            "fairness": fairness,
            "privacy": privacy,
            "security": security,
            "robustness": robustness,
            "compliance": compliance,
            "authenticity": authenticity,
            "use_case": use_case,
            "record_drift": record_drift,
        })
        return TrustScore.from_dict(data)

    # ── Guardrails ─────────────────────────────────────────────────────────────

    async def scan(self, text: str) -> GuardrailScan:
        """Scan text for PII, toxicity, and policy violations."""
        data = await self._post("guardrails/scan", {"text": text})
        return GuardrailScan.from_dict(data)

    # ── Hallucination ──────────────────────────────────────────────────────────

    async def analyze_hallucination(
        self,
        text: str,
        candidates: list[str] | None = None,
    ) -> HallucinationAnalysis:
        """Assess hallucination risk in a model response."""
        body: dict[str, Any] = {"text": text}
        if candidates:
            body["candidates"] = candidates
        data = await self._post("hallucination/analyze", body)
        return HallucinationAnalysis.from_dict(data)

    # ── Compliance ─────────────────────────────────────────────────────────────

    async def compliance_check(
        self,
        model_name: str,
        provider: str,
        use_case: str = "general",
        frameworks: list[str] | None = None,
    ) -> ComplianceReport:
        """Run compliance checks against NIST AI RMF, EU AI Act, ISO 42001."""
        body: dict[str, Any] = {
            "model_name": model_name,
            "provider": provider,
            "use_case": use_case,
        }
        if frameworks:
            body["frameworks"] = frameworks
        data = await self._post("compliance/check", body)
        return ComplianceReport.from_dict(data)

    # ── Cost ───────────────────────────────────────────────────────────────────

    async def record_usage(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        team: str = "default",
        application: str = "default",
    ) -> CostRecord:
        """Record token usage and retrieve cost breakdown."""
        data = await self._post("cost/record", {
            "provider": provider,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "team": team,
            "application": application,
        })
        return CostRecord.from_dict(data)

    async def cost_summary(self, days: int = 30) -> dict[str, Any]:
        """Retrieve cost summary for the last N days."""
        return await self._get("cost/summary", {"days": days})

    # ── Model Evaluation ───────────────────────────────────────────────────────

    async def compare_models(
        self,
        model_a: str,
        model_b: str,
        prompts: list[dict[str, str]],
        responses_a: list[dict[str, str]],
        responses_b: list[dict[str, str]],
        provider_a: str = "unknown",
        provider_b: str = "unknown",
    ) -> EvalCompareResult:
        """A/B compare two models across a set of prompts."""
        data = await self._post("eval/compare", {
            "model_a": model_a,
            "model_b": model_b,
            "provider_a": provider_a,
            "provider_b": provider_b,
            "prompts": prompts,
            "responses_a": responses_a,
            "responses_b": responses_b,
        })
        return EvalCompareResult.from_dict(data)

    # ── Health ─────────────────────────────────────────────────────────────────

    async def health(self) -> dict[str, Any]:
        """Check platform health status."""
        return await self._get("health")
