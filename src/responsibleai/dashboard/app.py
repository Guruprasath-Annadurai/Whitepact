"""Governance Dashboard — production FastAPI application."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from responsibleai.compliance.engine import ComplianceEngine
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.router import ModelRouter
from responsibleai.cost.tracker import CostTracker
from responsibleai.dashboard.config import Settings, get_settings
from responsibleai.dashboard.logging_config import configure_logging, get_logger
from responsibleai.dashboard.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    build_api_key_dependency,
    global_exception_handler,
    http_exception_handler,
)
from responsibleai.drift.monitor import TrustDriftMonitor
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine

_START_TIME = time.monotonic()
_REQUEST_COUNTER: dict[str, int] = {"total": 0, "errors": 0}

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)
logger = get_logger("app")

# ── Rate limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit_default])

# ── Module singletons (initialised once at startup) ──────────────────────────
_trust_engine: TrustScoreEngine | None = None
_passport_gen: PassportGenerator | None = None
_guardrails: GuardrailsEngine | None = None
_hallucination: HallucinationDetector | None = None
_compliance: ComplianceEngine | None = None
_cost_tracker: CostTracker | None = None
_cost_analyzer: CostAnalyzer | None = None
_router: ModelRouter | None = None
_drift_monitor: TrustDriftMonitor | None = None


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _trust_engine, _passport_gen, _guardrails, _hallucination
    global _compliance, _cost_tracker, _cost_analyzer, _router, _drift_monitor

    policy = BudgetPolicy(monthly_limit_usd=settings.monthly_budget_usd)
    _trust_engine = TrustScoreEngine()
    _passport_gen = PassportGenerator()
    _guardrails = GuardrailsEngine()
    _hallucination = HallucinationDetector()
    _compliance = ComplianceEngine()
    _cost_tracker = CostTracker(db_path=settings.db_path, policy=policy)
    _cost_analyzer = CostAnalyzer()
    _router = ModelRouter()
    _drift_monitor = TrustDriftMonitor(
        db_path=settings.db_path,
        alert_threshold=settings.alert_threshold,
    )

    auth_status = "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled"
    logger.info(
        "startup_complete",
        version="0.5.0",
        db_path=settings.db_path,
        auth=auth_status,
        rate_limit=settings.rate_limit_default,
    )

    yield

    if _cost_tracker:
        _cost_tracker.close()
    if _drift_monitor:
        _drift_monitor.close()
    logger.info("shutdown_complete")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ResponsibleAI Governance Platform",
    description=(
        "Enterprise AI Governance API — Trust Scoring, Compliance, Guardrails, "
        "Hallucination Detection, Red Team, Cost Intelligence, Drift Monitoring."
    ),
    version="0.5.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={"name": "Guruprasath Annadurai", "email": "milchcreamfoods@gmail.com"},
    license_info={"name": "MIT"},
)

# ── Exception handlers ────────────────────────────────────────────────────────
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors()},
    )


# ── Middleware (order matters: outermost first) ───────────────────────────────
origins = ["*"] if settings.allow_all_origins else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.state.limiter = limiter
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Static files ──────────────────────────────────────────────────────────────
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ── Auth dependency ───────────────────────────────────────────────────────────
_require_auth = build_api_key_dependency(settings.api_keys, settings.auth_enabled)


# ── Request / Response models ─────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=100)
    fairness: float = Field(0.75, ge=0.0, le=1.0)
    privacy: float = Field(0.80, ge=0.0, le=1.0)
    security: float = Field(0.70, ge=0.0, le=1.0)
    robustness: float = Field(0.75, ge=0.0, le=1.0)
    compliance: float = Field(0.80, ge=0.0, le=1.0)
    authenticity: float = Field(0.85, ge=0.0, le=1.0)
    use_case: str = Field("general", max_length=50)
    record_drift: bool = Field(True)


class ScanTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=50_000)


class AnalyzePromptRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=100_000)
    response: str = Field("", max_length=100_000)
    provider: str = Field("openai", max_length=50)
    model: str = Field("gpt-4o", max_length=100)
    monthly_requests: int = Field(10_000, ge=1, le=100_000_000)


class RouteTaskRequest(BaseModel):
    task_description: str = Field(..., min_length=1, max_length=2000)
    quality_requirement: str = Field("balanced", pattern="^(balanced|maximum|cheapest)$")


class RecordUsageRequest(BaseModel):
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    input_tokens: int = Field(..., ge=0, le=10_000_000)
    output_tokens: int = Field(..., ge=0, le=10_000_000)
    team: str = Field("default", max_length=100)
    application: str = Field("default", max_length=100)


# ── Root / HTML ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    index = _static_dir / "index.html"
    return HTMLResponse(content=index.read_text())


# ── Health & Metrics ───────────────────────────────────────────────────────────

@app.get("/api/health", tags=["ops"])
async def health() -> dict[str, Any]:
    db_ok = True
    try:
        if _cost_tracker:
            _cost_tracker.request_count()
    except Exception:
        db_ok = False

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "0.5.0",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "auth": "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled",
        },
        "modules": [
            "trust_score", "ai_passport", "guardrails",
            "hallucination", "compliance", "redteam",
            "cost_tracker", "cost_analyzer", "model_router", "drift_monitor",
        ],
    }


@app.get("/api/metrics", tags=["ops"])
@limiter.limit("60/minute")
async def metrics(request: Request, _auth=Depends(_require_auth)) -> dict[str, Any]:
    total_requests = _REQUEST_COUNTER["total"]
    errors = _REQUEST_COUNTER["errors"]
    return {
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "total_requests": total_requests,
        "error_count": errors,
        "error_rate_pct": round(errors / max(total_requests, 1) * 100, 2),
        "db_path": settings.db_path,
        "auth_enabled": settings.auth_enabled and bool(settings.api_keys),
        "alert_threshold": settings.alert_threshold,
        "monthly_budget_usd": settings.monthly_budget_usd,
    }


# ── Trust & Evaluation ─────────────────────────────────────────────────────────

@app.post("/api/evaluate", tags=["trust"])
@limiter.limit(settings.rate_limit_evaluate)
async def evaluate_model(
    request: Request,
    req: EvaluateRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    score = _trust_engine.compute(
        fairness=req.fairness, privacy=req.privacy, security=req.security,
        robustness=req.robustness, compliance=req.compliance, authenticity=req.authenticity,
    )
    compliance_report = _compliance.evaluate(
        fairness_score=req.fairness, privacy_score=req.privacy,
        security_score=req.security, robustness_score=req.robustness,
        compliance_maturity=req.compliance, use_case=req.use_case,
    )
    passport = _passport_gen.generate(
        model_name=req.model_name, provider=req.provider, trust_score=score,
        compliance_summary={"overall": round(compliance_report.compliance_score * 100, 1)},
    )
    alert = None
    if req.record_drift:
        alert = _drift_monitor.record(req.model_name, req.provider, score)

    logger.info(
        "evaluation",
        model=req.model_name, provider=req.provider,
        score=score.overall, grade=score.grade,
        passport_id=passport.passport_id,
    )
    return {
        "trust_score": score.to_dict(),
        "compliance": {
            "overall_score": round(compliance_report.compliance_score * 100, 2),
            "eu_ai_act_tier": compliance_report.eu_ai_act_tier.value if compliance_report.eu_ai_act_tier else None,
            "violations": len(compliance_report.violations),
            "frameworks_evaluated": len(compliance_report.frameworks),
        },
        "passport_id": passport.passport_id,
        "passport_hash": passport.verification_hash[:16] + "...",
        "drift_alert": alert.to_dict() if alert else None,
    }


@app.get("/api/trust-score/{model_name}/{provider}", tags=["trust"])
@limiter.limit("120/minute")
async def get_trust_history(
    request: Request,
    model_name: str,
    provider: str,
    limit: int = 30,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    if limit < 1 or limit > 365:
        raise HTTPException(400, "limit must be between 1 and 365")
    history = _drift_monitor.history(model_name, provider, limit=limit)
    trend = _drift_monitor.trend(model_name, provider)
    return {"model": model_name, "provider": provider, "history": history, "trend": trend}


@app.get("/api/models", tags=["trust"])
@limiter.limit("120/minute")
async def list_models(request: Request, _auth=Depends(_require_auth)) -> dict[str, Any]:
    return {"models": _drift_monitor.all_models()}


# ── Guardrails ─────────────────────────────────────────────────────────────────

@app.post("/api/scan", tags=["guardrails"])
@limiter.limit("200/minute")
async def scan_text(
    request: Request,
    req: ScanTextRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
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


# ── Hallucination ──────────────────────────────────────────────────────────────

@app.post("/api/hallucination", tags=["hallucination"])
@limiter.limit("100/minute")
async def analyze_hallucination(
    request: Request,
    body: dict[str, Any],
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    text = str(body.get("text", ""))[:50_000]
    if not text:
        raise HTTPException(400, "text field is required")
    candidates_raw = body.get("candidates", None)
    candidates = [str(c)[:10_000] for c in candidates_raw] if candidates_raw else None
    result = _hallucination.analyze(text, candidates=candidates)
    return {
        "hallucination_risk": round(result.hallucination_risk, 3),
        "risk_level": result.risk_level.upper(),
        "consistency_score": round(result.consistency_score, 3),
        "hedging_score": round(result.hedging_score, 3),
        "unsupported_claims": result.unsupported_claims[:20],
    }


# ── Cost Intelligence ──────────────────────────────────────────────────────────

@app.post("/api/cost/record", tags=["cost"])
@limiter.limit("500/minute")
async def record_usage(
    request: Request,
    req: RecordUsageRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    usage = TokenUsage.create(
        provider=req.provider, model=req.model,
        input_tokens=req.input_tokens, output_tokens=req.output_tokens,
        team=req.team, application=req.application,
    )
    record = _cost_tracker.record(usage)
    return record.to_dict()


@app.get("/api/cost/summary", tags=["cost"])
@limiter.limit("60/minute")
async def cost_summary(
    request: Request,
    days: int = 30,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    if days < 1 or days > 365:
        raise HTTPException(400, "days must be between 1 and 365")
    return {
        "total_cost_usd": _cost_tracker.total_cost(days),
        "total_tokens": _cost_tracker.total_tokens(days),
        "model_breakdown": _cost_tracker.get_model_breakdown(days),
        "team_breakdown": _cost_tracker.get_team_breakdown(days),
        "daily_costs": _cost_tracker.get_daily_costs(days),
        "budget_status": _cost_tracker.check_budget().to_dict(),
        "request_count": _cost_tracker.request_count(days),
    }


@app.post("/api/cost/analyze", tags=["cost"])
@limiter.limit("60/minute")
async def analyze_prompt(
    request: Request,
    req: AnalyzePromptRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    result = _cost_analyzer.analyze_prompt_efficiency(
        prompt=req.prompt, response=req.response,
        provider=req.provider, model=req.model,
        monthly_requests=req.monthly_requests,
    )
    return result.to_dict()


@app.post("/api/cost/route", tags=["cost"])
@limiter.limit("120/minute")
async def route_task(
    request: Request,
    req: RouteTaskRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    decision = _router.route(req.task_description, req.quality_requirement)
    return decision.to_dict()


@app.get("/api/cost/models", tags=["cost"])
@limiter.limit("60/minute")
async def model_pricing(request: Request, _auth=Depends(_require_auth)) -> dict[str, Any]:
    return {"models": _router.provider_comparison()}


# ── Drift ──────────────────────────────────────────────────────────────────────

@app.get("/api/drift/{model_name}/{provider}", tags=["drift"])
@limiter.limit("120/minute")
async def get_drift_trend(
    request: Request,
    model_name: str,
    provider: str,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    trend = _drift_monitor.trend(model_name, provider)
    history = _drift_monitor.history(model_name, provider, limit=10)
    return {"trend": trend, "recent_history": history}
