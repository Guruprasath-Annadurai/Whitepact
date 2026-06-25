"""Governance Dashboard — production FastAPI application (v0.7.0)."""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from responsibleai.compliance.engine import ComplianceEngine
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.router import ModelRouter
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
from responsibleai.dashboard.prometheus import (
    get_metrics_output,
    observe_cost,
    observe_drift_alert,
    observe_guardrail,
    observe_request,
    observe_trust_score,
    observe_webhook_delivery,
    observe_websocket_connections,
)
from responsibleai.dashboard.telemetry import (
    record_cost,
    record_evaluation,
    record_guardrail_scan,
    setup_telemetry,
)
from responsibleai.dashboard.websocket_manager import ConnectionManager
from responsibleai.db import CostRepository, TrustRepository, create_engine
from responsibleai.db.engine import DatabaseEngine
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine
from responsibleai.webhooks import WebhookConfig, WebhookEvent, WebhookManager, WebhookProvider

_START_TIME = time.monotonic()
_REQUEST_COUNTER: dict[str, int] = {"total": 0, "errors": 0}

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)
logger = get_logger("app")

# ── Rate limiter ───────────────────────────────────────────────────────────────
_limiter_kwargs: dict[str, Any] = {
    "key_func": get_remote_address,
    "default_limits": [settings.rate_limit_default],
}
if settings.redis_url:
    _limiter_kwargs["storage_uri"] = settings.redis_url

limiter = Limiter(**_limiter_kwargs)

# ── Module singletons ──────────────────────────────────────────────────────────
_trust_engine: TrustScoreEngine | None = None
_passport_gen: PassportGenerator | None = None
_guardrails: GuardrailsEngine | None = None
_hallucination: HallucinationDetector | None = None
_compliance: ComplianceEngine | None = None
_cost_repo: CostRepository | None = None
_cost_analyzer: CostAnalyzer | None = None
_router: ModelRouter | None = None
_trust_repo: TrustRepository | None = None
_db_engine: DatabaseEngine | None = None
_ws_manager: ConnectionManager = ConnectionManager()
_webhook_manager: WebhookManager = WebhookManager()


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _trust_engine, _passport_gen, _guardrails, _hallucination
    global _compliance, _cost_repo, _cost_analyzer, _router, _trust_repo, _db_engine

    setup_telemetry(
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_endpoint,
        otlp_headers=settings.otel_headers_dict,
    )

    _db_engine = create_engine(settings.effective_db_url)
    await _db_engine.init()

    policy = BudgetPolicy(monthly_limit_usd=settings.monthly_budget_usd)
    _cost_repo    = CostRepository(_db_engine, policy=policy)
    _trust_repo   = TrustRepository(_db_engine, alert_threshold=settings.alert_threshold)
    _trust_engine = TrustScoreEngine()
    _passport_gen = PassportGenerator()
    _guardrails   = GuardrailsEngine()
    _hallucination = HallucinationDetector()
    _compliance   = ComplianceEngine()
    _cost_analyzer = CostAnalyzer()
    _router       = ModelRouter()

    _ws_manager.start()

    auth_status = "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled"
    db_backend   = "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    rl_backend   = "redis" if settings.redis_url else "memory"
    logger.info(
        "startup_complete",
        version="0.7.0",
        db_backend=db_backend,
        rate_limit_backend=rl_backend,
        otel=bool(settings.otel_endpoint),
        auth=auth_status,
    )

    yield

    _ws_manager.stop()
    if _db_engine:
        await _db_engine.close()
    logger.info("shutdown_complete")


# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="ResponsibleAI Governance Platform",
    description=(
        "Enterprise AI Governance API — Trust Scoring, Compliance, Guardrails, "
        "Hallucination Detection, Red Team, Cost Intelligence, Drift Monitoring, "
        "WebSocket live dashboard, Webhooks, Prometheus metrics."
    ),
    version="0.7.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={"name": "Guruprasath Annadurai", "email": "milchcreamfoods@gmail.com"},
    license_info={"name": "MIT"},
)

# ── Exception handlers ─────────────────────────────────────────────────────────
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={"error": "validation_error", "detail": exc.errors()},
    )


# ── Middleware ─────────────────────────────────────────────────────────────────
origins = ["*"] if settings.allow_all_origins else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.state.limiter = limiter
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Static files ───────────────────────────────────────────────────────────────
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

# ── Auth dependency ────────────────────────────────────────────────────────────
_require_auth = build_api_key_dependency(settings.api_keys, settings.auth_enabled)


# ── Request / Response models ──────────────────────────────────────────────────

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


class WebhookCreateRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048)
    events: list[str] = Field(..., min_length=1)
    provider: str = Field("generic", pattern="^(slack|teams|pagerduty|generic)$")
    secret: str = Field("", max_length=256)
    description: str = Field("", max_length=500)
    max_retries: int = Field(3, ge=1, le=5)


# ── Root / HTML ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    index = _static_dir / "index.html"
    return HTMLResponse(content=index.read_text())


# ── Health & Ops ───────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["ops"])
async def health() -> dict[str, Any]:
    db_ok = True
    try:
        if _cost_repo:
            await _cost_repo.request_count()
    except Exception:
        db_ok = False

    db_backend = "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    rl_backend = "redis" if settings.redis_url else "memory"

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "0.7.0",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "db_backend": db_backend,
            "rate_limit_backend": rl_backend,
            "otel": "enabled" if settings.otel_endpoint else "disabled",
            "auth": "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled",
            "websocket_connections": _ws_manager.connection_count,
            "webhooks_registered": len(_webhook_manager.list()),
        },
        "modules": [
            "trust_score", "ai_passport", "guardrails", "hallucination",
            "compliance", "redteam", "cost_tracker", "cost_analyzer",
            "model_router", "drift_monitor", "websockets", "webhooks", "prometheus",
        ],
    }


@app.get("/api/metrics", tags=["ops"])
@limiter.limit("60/minute")
async def metrics(request: Request, _auth=Depends(_require_auth)) -> dict[str, Any]:
    total_requests = _REQUEST_COUNTER["total"]
    errors = _REQUEST_COUNTER["errors"]
    total_cost = await _cost_repo.total_cost(30) if _cost_repo else 0.0
    return {
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "total_requests": total_requests,
        "error_count": errors,
        "error_rate_pct": round(errors / max(total_requests, 1) * 100, 2),
        "db_backend": "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite",
        "rate_limit_backend": "redis" if settings.redis_url else "memory",
        "otel_enabled": bool(settings.otel_endpoint),
        "auth_enabled": settings.auth_enabled and bool(settings.api_keys),
        "alert_threshold": settings.alert_threshold,
        "monthly_budget_usd": settings.monthly_budget_usd,
        "monthly_spend_usd": round(total_cost, 4),
        "websocket_connections": _ws_manager.connection_count,
        "webhooks_registered": len(_webhook_manager.list()),
        "webhook_deliveries": _webhook_manager.total_deliveries,
        "webhook_failures": _webhook_manager.failed_deliveries,
    }


@app.get("/metrics", tags=["ops"], include_in_schema=False)
async def prometheus_metrics() -> Response:
    """Prometheus-compatible scrape endpoint. Mount at port 9090 in production."""
    observe_websocket_connections(_ws_manager.connection_count)
    body, content_type = get_metrics_output()
    return Response(content=body, media_type=content_type)


# ── WebSocket live dashboard ───────────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    """Live dashboard WebSocket.

    Connect with: ws://host:8765/ws/dashboard?token=<api-key>

    Events pushed by server:
        {"type": "trust_score",  "data": {...}}
        {"type": "drift_alert",  "data": {...}}
        {"type": "cost_update",  "data": {...}}
        {"type": "guardrail",    "data": {...}}
        {"type": "ping",         "connections": N}
    """
    # Auth — reject unauthenticated connections when auth is enabled
    if settings.auth_enabled and settings.api_keys:
        if token not in settings.api_keys:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    api_key = token or "anonymous"
    await _ws_manager.connect(websocket, api_key)
    observe_websocket_connections(_ws_manager.connection_count)

    try:
        # Send initial state snapshot
        snapshot: dict[str, Any] = {"type": "connected", "version": "0.7.0"}
        if _cost_repo:
            snapshot["monthly_spend_usd"] = round(await _cost_repo.total_cost(30), 4)
        if _trust_repo:
            snapshot["models"] = await _trust_repo.all_models()
        await websocket.send_json(snapshot)

        # Keep alive — client should send pong or any message
        while True:
            await websocket.receive_text()

    except WebSocketDisconnect:
        pass
    finally:
        _ws_manager.disconnect(websocket, api_key)
        observe_websocket_connections(_ws_manager.connection_count)


# ── Webhooks CRUD ──────────────────────────────────────────────────────────────

@app.post("/api/webhooks", tags=["webhooks"])
@limiter.limit("30/minute")
async def create_webhook(
    request: Request,
    req: WebhookCreateRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    try:
        events = [WebhookEvent(e) for e in req.events]
    except ValueError as exc:
        raise HTTPException(400, f"Invalid event type: {exc}") from exc

    config = WebhookConfig(
        url=req.url,
        events=events,
        provider=WebhookProvider(req.provider),
        secret=req.secret,
        description=req.description,
        max_retries=req.max_retries,
    )
    _webhook_manager.register(config)
    return config.to_dict()


@app.get("/api/webhooks", tags=["webhooks"])
@limiter.limit("60/minute")
async def list_webhooks(
    request: Request,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    return {"webhooks": [c.to_dict() for c in _webhook_manager.list()]}


@app.delete("/api/webhooks/{webhook_id}", tags=["webhooks"])
@limiter.limit("30/minute")
async def delete_webhook(
    request: Request,
    webhook_id: str,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    removed = _webhook_manager.remove(webhook_id)
    if not removed:
        raise HTTPException(404, "Webhook not found")
    return {"deleted": webhook_id}


@app.get("/api/webhooks/deliveries", tags=["webhooks"])
@limiter.limit("60/minute")
async def webhook_deliveries(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    return {
        "deliveries": _webhook_manager.delivery_log(limit),
        "total": _webhook_manager.total_deliveries,
        "failed": _webhook_manager.failed_deliveries,
    }


@app.post("/api/webhooks/test/{webhook_id}", tags=["webhooks"])
@limiter.limit("10/minute")
async def test_webhook(
    request: Request,
    webhook_id: str,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    cfg = _webhook_manager.get(webhook_id)
    if cfg is None:
        raise HTTPException(404, "Webhook not found")
    deliveries = await _webhook_manager.fire(
        WebhookEvent.TRUST_SCORE_CHANGED,
        {"model": "test-model", "provider": "test", "score": 85.0, "test": True},
    )
    result = next((d for d in deliveries if d.webhook_id == webhook_id), None)
    if result is None:
        return {"success": False, "error": "No matching delivery"}
    return result.to_dict()


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
    drift_alert = None
    if req.record_drift:
        drift_alert = await _trust_repo.record(req.model_name, req.provider, score)

    # Prometheus + OTEL instrumentation
    observe_trust_score(req.model_name, req.provider, score.overall)
    record_evaluation(req.model_name, req.provider, score.overall, score.grade)

    # Push live update to connected WebSocket clients
    await _ws_manager.broadcast({
        "type": "trust_score",
        "data": {
            "model": req.model_name,
            "provider": req.provider,
            "score": score.overall,
            "grade": score.grade,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    # Fire webhooks on drift alert
    if drift_alert:
        observe_drift_alert(drift_alert.get("severity", "LOW"))
        deliveries = await _webhook_manager.fire(
            WebhookEvent.DRIFT_ALERT,
            {
                "model": req.model_name,
                "provider": req.provider,
                "delta": drift_alert.get("delta"),
                "severity": drift_alert.get("severity"),
                "score": score.overall,
            },
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.DRIFT_ALERT.value, d.success)

        await _ws_manager.broadcast({
            "type": "drift_alert",
            "data": {**drift_alert, "model": req.model_name, "provider": req.provider},
        })

    logger.info(
        "evaluation",
        model=req.model_name, provider=req.provider,
        score=score.overall, grade=score.grade,
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
        "drift_alert": drift_alert,
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
    history = await _trust_repo.history(model_name, provider, limit=limit)
    trend = await _trust_repo.trend(model_name, provider)
    return {"model": model_name, "provider": provider, "history": history, "trend": trend}


@app.get("/api/models", tags=["trust"])
@limiter.limit("120/minute")
async def list_models(request: Request, _auth=Depends(_require_auth)) -> dict[str, Any]:
    return {"models": await _trust_repo.all_models()}


# ── Guardrails ─────────────────────────────────────────────────────────────────

@app.post("/api/scan", tags=["guardrails"])
@limiter.limit("200/minute")
async def scan_text(
    request: Request,
    req: ScanTextRequest,
    _auth=Depends(_require_auth),
) -> dict[str, Any]:
    result = _guardrails.scan(req.text)
    blocked = result.is_blocked

    observe_guardrail(blocked)
    record_guardrail_scan(blocked, len(result.pii_findings))

    # Push to WebSocket clients
    if blocked:
        await _ws_manager.broadcast({
            "type": "guardrail",
            "data": {
                "blocked": True,
                "pii_count": len(result.pii_findings),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        })
        deliveries = await _webhook_manager.fire(
            WebhookEvent.GUARDRAIL_TRIGGERED,
            {
                "pii_count": len(result.pii_findings),
                "block_reasons": result.block_reasons,
            },
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.GUARDRAIL_TRIGGERED.value, d.success)

    return {
        "is_blocked": blocked,
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
    cost_record = await _cost_repo.record(usage)

    observe_cost(req.model, req.provider, cost_record.total_cost, req.input_tokens, req.output_tokens)
    record_cost(req.provider, req.model, cost_record.total_cost, req.input_tokens + req.output_tokens)

    # Push cost update to WebSocket clients
    await _ws_manager.broadcast({
        "type": "cost_update",
        "data": {
            "model": req.model,
            "provider": req.provider,
            "cost_usd": cost_record.total_cost,
            "tokens": req.input_tokens + req.output_tokens,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    })

    # Fire budget webhook if exceeded
    budget = await _cost_repo.check_budget()
    if budget.is_exceeded:
        deliveries = await _webhook_manager.fire(
            WebhookEvent.BUDGET_EXCEEDED,
            {
                "monthly_limit_usd": budget.monthly_limit_usd,
                "total_spent_usd": budget.total_spent_usd,
                "overage_usd": round(budget.total_spent_usd - budget.monthly_limit_usd, 4),
            },
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.BUDGET_EXCEEDED.value, d.success)

    return cost_record.to_dict()


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
        "total_cost_usd": await _cost_repo.total_cost(days),
        "total_tokens": await _cost_repo.total_tokens(days),
        "model_breakdown": await _cost_repo.get_model_breakdown(days),
        "team_breakdown": await _cost_repo.get_team_breakdown(days),
        "daily_costs": await _cost_repo.get_daily_costs(days),
        "budget_status": (await _cost_repo.check_budget()).to_dict(),
        "request_count": await _cost_repo.request_count(days),
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
    trend = await _trust_repo.trend(model_name, provider)
    history = await _trust_repo.history(model_name, provider, limit=10)
    return {"trend": trend, "recent_history": history}
