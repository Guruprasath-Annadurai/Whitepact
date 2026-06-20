"""Governance Dashboard — FastAPI backend."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from responsibleai.compliance.engine import ComplianceEngine
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import TokenUsage
from responsibleai.cost.router import ModelRouter
from responsibleai.cost.tracker import CostTracker
from responsibleai.drift.monitor import TrustDriftMonitor
from responsibleai.guardrails.engine import GuardrailsEngine, GuardrailsPolicy
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine

app = FastAPI(
    title="ResponsibleAI Governance Dashboard",
    description="Enterprise AI Governance Platform — Trust, Safety, Cost Intelligence",
    version="0.4.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# Module singletons (in-memory for demo; swap db_path for persistence)
_trust_engine = TrustScoreEngine()
_passport_gen = PassportGenerator()
_guardrails = GuardrailsEngine()
_hallucination = HallucinationDetector()
_compliance = ComplianceEngine()
_cost_tracker = CostTracker()
_cost_analyzer = CostAnalyzer()
_router = ModelRouter()
_drift_monitor = TrustDriftMonitor()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class EvaluateRequest(BaseModel):
    model_name: str = Field(..., example="gpt-4o")
    provider: str = Field(..., example="openai")
    fairness: float = Field(0.75, ge=0.0, le=1.0)
    privacy: float = Field(0.80, ge=0.0, le=1.0)
    security: float = Field(0.70, ge=0.0, le=1.0)
    robustness: float = Field(0.75, ge=0.0, le=1.0)
    compliance: float = Field(0.80, ge=0.0, le=1.0)
    authenticity: float = Field(0.85, ge=0.0, le=1.0)
    use_case: str = Field("general", example="medical")
    record_drift: bool = Field(True)


class ScanTextRequest(BaseModel):
    text: str = Field(..., example="Call me at 555-123-4567 or user@example.com")


class AnalyzePromptRequest(BaseModel):
    prompt: str
    response: str = ""
    provider: str = "openai"
    model: str = "gpt-4o"
    monthly_requests: int = 10_000


class RouteTaskRequest(BaseModel):
    task_description: str
    quality_requirement: str = "balanced"


class RecordUsageRequest(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    team: str = "default"
    application: str = "default"


# ---------------------------------------------------------------------------
# HTML root
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    index = _static_dir / "index.html"
    return HTMLResponse(content=index.read_text())


# ---------------------------------------------------------------------------
# Trust & Evaluation
# ---------------------------------------------------------------------------

@app.post("/api/evaluate")
async def evaluate_model(req: EvaluateRequest) -> dict[str, Any]:
    score = _trust_engine.compute(
        fairness=req.fairness,
        privacy=req.privacy,
        security=req.security,
        robustness=req.robustness,
        compliance=req.compliance,
        authenticity=req.authenticity,
    )
    compliance_report = _compliance.evaluate(
        fairness_score=req.fairness,
        privacy_score=req.privacy,
        security_score=req.security,
        robustness_score=req.robustness,
        compliance_maturity=req.compliance,
        use_case=req.use_case,
    )
    passport = _passport_gen.generate(
        model_name=req.model_name,
        provider=req.provider,
        trust_score=score,
        compliance_summary={"overall": compliance_report.overall_score},
    )
    if req.record_drift:
        alert = _drift_monitor.record(req.model_name, req.provider, score)
    else:
        alert = None

    return {
        "trust_score": score.to_dict(),
        "compliance": {
            "overall_score": round(compliance_report.compliance_score * 100, 2),
            "frameworks_evaluated": len(compliance_report.frameworks),
        },
        "passport_id": passport.passport_id,
        "drift_alert": alert.to_dict() if alert else None,
    }


@app.get("/api/trust-score/{model_name}/{provider}")
async def get_trust_history(model_name: str, provider: str, limit: int = 30) -> dict[str, Any]:
    history = _drift_monitor.history(model_name, provider, limit=limit)
    trend = _drift_monitor.trend(model_name, provider)
    return {"model": model_name, "provider": provider, "history": history, "trend": trend}


@app.get("/api/models")
async def list_models() -> dict[str, Any]:
    return {"models": _drift_monitor.all_models()}


# ---------------------------------------------------------------------------
# Guardrails
# ---------------------------------------------------------------------------

@app.post("/api/scan")
async def scan_text(req: ScanTextRequest) -> dict[str, Any]:
    result = _guardrails.scan(req.text)
    return {
        "is_blocked": result.is_blocked,
        "pii_count": len(result.pii_findings),
        "toxicity_count": len(result.toxicity_findings),
        "block_reasons": result.block_reasons,
        "redacted_text": result.redacted_text,
        "pii_findings": [
            {"category": f.category, "start": f.start, "end": f.end}
            for f in result.pii_findings
        ],
    }


# ---------------------------------------------------------------------------
# Hallucination
# ---------------------------------------------------------------------------

@app.post("/api/hallucination")
async def analyze_hallucination(body: dict[str, Any]) -> dict[str, Any]:
    text = body.get("text", "")
    candidates = body.get("candidates", None)
    result = _hallucination.analyze(text, candidates=candidates)
    return {
        "hallucination_risk": round(result.hallucination_risk, 3),
        "risk_level": result.risk_level,
        "consistency_score": round(result.consistency_score, 3),
        "hedging_score": round(result.hedging_score, 3),
        "unsupported_claims": result.unsupported_claims,
    }


# ---------------------------------------------------------------------------
# Cost Intelligence
# ---------------------------------------------------------------------------

@app.post("/api/cost/record")
async def record_usage(req: RecordUsageRequest) -> dict[str, Any]:
    usage = TokenUsage.create(
        provider=req.provider,
        model=req.model,
        input_tokens=req.input_tokens,
        output_tokens=req.output_tokens,
        team=req.team,
        application=req.application,
    )
    record = _cost_tracker.record(usage)
    return record.to_dict()


@app.get("/api/cost/summary")
async def cost_summary(days: int = 30) -> dict[str, Any]:
    return {
        "total_cost_usd": _cost_tracker.total_cost(days),
        "total_tokens": _cost_tracker.total_tokens(days),
        "model_breakdown": _cost_tracker.get_model_breakdown(days),
        "team_breakdown": _cost_tracker.get_team_breakdown(days),
        "daily_costs": _cost_tracker.get_daily_costs(days),
        "budget_status": _cost_tracker.check_budget().to_dict(),
        "request_count": _cost_tracker.request_count(days),
    }


@app.post("/api/cost/analyze")
async def analyze_prompt(req: AnalyzePromptRequest) -> dict[str, Any]:
    result = _cost_analyzer.analyze_prompt_efficiency(
        prompt=req.prompt,
        response=req.response,
        provider=req.provider,
        model=req.model,
        monthly_requests=req.monthly_requests,
    )
    return result.to_dict()


@app.post("/api/cost/route")
async def route_task(req: RouteTaskRequest) -> dict[str, Any]:
    decision = _router.route(req.task_description, req.quality_requirement)
    return decision.to_dict()


@app.get("/api/cost/models")
async def model_pricing() -> dict[str, Any]:
    return {"models": _router.provider_comparison()}


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------

@app.get("/api/drift/{model_name}/{provider}")
async def get_drift_trend(model_name: str, provider: str) -> dict[str, Any]:
    trend = _drift_monitor.trend(model_name, provider)
    history = _drift_monitor.history(model_name, provider, limit=10)
    return {"trend": trend, "recent_history": history}


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {
        "status": "healthy",
        "version": "0.4.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "modules": [
            "trust_score", "ai_passport", "guardrails",
            "hallucination", "compliance", "redteam",
            "cost_tracker", "cost_analyzer", "model_router", "drift_monitor",
        ],
    }
