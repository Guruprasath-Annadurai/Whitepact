"""Governance Dashboard — production FastAPI application (v1.0.0)."""

from __future__ import annotations

import asyncio
import secrets
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
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
from starlette.middleware.base import BaseHTTPMiddleware

from responsibleai.auth.oidc import OIDCProvider
from responsibleai.compliance.engine import ComplianceEngine
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.router import ModelRouter
from responsibleai.dashboard.config import get_settings
from responsibleai.dashboard.logging_config import configure_logging, get_logger
from responsibleai.dashboard.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    global_exception_handler,
    http_exception_handler,
)
from responsibleai.dashboard.prometheus import (
    get_metrics_output,
    observe_cost,
    observe_drift_alert,
    observe_guardrail,
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
from responsibleai.db import (
    AuditRepository,
    CostRepository,
    EvalRepository,
    OrgRepository,
    TrustRepository,
    WebhookDeliveryRepository,
    create_engine,
)
from responsibleai.db.engine import DatabaseEngine
from responsibleai.eval import (
    BenchmarkRunner,
    BenchmarkSuite,
    DatasetBiasScanner,
    EvalPrompt,
    ModelComparator,
    ModelResponse,
    RegressionDetector,
)
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.rbac import AuditEntry, OrgContext, Role, has_permission, role_from_str
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine
from responsibleai.webhooks import WebhookConfig, WebhookEvent, WebhookManager, WebhookProvider

_START_TIME = time.monotonic()
_REQUEST_COUNTER: dict[str, int] = {"total": 0, "errors": 0}

settings = get_settings()
configure_logging(level=settings.log_level, json_logs=settings.log_json)
logger = get_logger("app")

# ── Per-org rate limiter ───────────────────────────────────────────────────────

def _get_rate_limit_key(request: Request) -> str:
    """Rate limit by API key (per org / per key) when present, IP address otherwise.

    Using the API key as the bucket key means each organisation gets its own
    quota rather than sharing a pool with all other tenants on the same IP
    (common in cloud-hosted or NAT environments).
    """
    import hashlib as _hashlib
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:].strip()
        if token:
            return "key:" + _hashlib.sha256(token.encode()).hexdigest()[:24]
    return get_remote_address(request)


_limiter_kwargs: dict[str, Any] = {
    "key_func": _get_rate_limit_key,
    "default_limits": [settings.rate_limit_default],
}
if settings.redis_url:
    _limiter_kwargs["storage_uri"] = settings.redis_url

limiter = Limiter(**_limiter_kwargs)

# ── ContextVar for audit log (scoped per-request in async) ────────────────────
_audit_ctx: ContextVar[dict[str, Any] | None] = ContextVar("audit_ctx", default=None)

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
_org_repo: OrgRepository | None = None
_audit_repo: AuditRepository | None = None
_db_engine: DatabaseEngine | None = None
_ws_manager: ConnectionManager = ConnectionManager()
_webhook_manager: WebhookManager = WebhookManager()
_eval_repo: EvalRepository | None = None
_comparator: ModelComparator | None = None
_benchmark_runner: BenchmarkRunner | None = None
_regression_detector: RegressionDetector = RegressionDetector()
_dataset_scanner: DatasetBiasScanner | None = None
_oidc_provider: OIDCProvider | None = None
_oidc_state_store: dict[str, float] = {}  # state → issued_at; cleared on use


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _trust_engine, _passport_gen, _guardrails, _hallucination
    global _compliance, _cost_repo, _cost_analyzer, _router, _trust_repo
    global _org_repo, _audit_repo, _db_engine
    global _eval_repo, _comparator, _benchmark_runner, _dataset_scanner
    global _oidc_provider

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
    _org_repo     = OrgRepository(_db_engine)
    _audit_repo   = AuditRepository(_db_engine)
    _trust_engine = TrustScoreEngine()
    _passport_gen = PassportGenerator()
    _guardrails   = GuardrailsEngine()
    _hallucination = HallucinationDetector()
    _compliance   = ComplianceEngine()
    _cost_analyzer = CostAnalyzer()
    _router       = ModelRouter()
    _eval_repo    = EvalRepository(_db_engine)
    _comparator   = ModelComparator(
        trust_engine=_trust_engine,
        guardrails=_guardrails,
        hallucination=_hallucination,
    )
    _benchmark_runner = BenchmarkRunner(guardrails=_guardrails)
    _dataset_scanner  = DatasetBiasScanner(guardrails=_guardrails)

    if settings.oidc_issuer:
        _oidc_provider = OIDCProvider(
            issuer=settings.oidc_issuer,
            client_id=settings.oidc_client_id,
            jwks_uri=settings.oidc_jwks_uri,
            skip_verification=settings.oidc_skip_verification,
        )

    # Attach DB-backed delivery log + start persistent retry worker
    _webhook_delivery_repo = WebhookDeliveryRepository(_db_engine)
    _webhook_manager.set_repository(_webhook_delivery_repo)
    _webhook_manager.start_retry_worker()

    _ws_manager.start()

    auth_status = "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled"
    db_backend   = "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    rl_backend   = "redis" if settings.redis_url else "memory"
    logger.info(
        "startup_complete",
        version="1.1.0",
        db_backend=db_backend,
        rate_limit_backend=rl_backend,
        otel=bool(settings.otel_endpoint),
        auth=auth_status,
    )

    yield

    _webhook_manager.stop_retry_worker()
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
        "WebSocket live dashboard, Webhooks, Prometheus metrics, "
        "Multi-tenant RBAC, Org management, Audit log, "
        "Model Evaluation Framework (A/B compare, benchmarks, regression, dataset scan), "
        "Single Sign-On (OAuth2/OIDC), versioned stable API."
    ),
    version="1.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    contact={"name": "Guruprasath Annadurai", "email": "milchcreamfoods@gmail.com"},
    license_info={"name": "MIT"},
)


# ── Audit log middleware ───────────────────────────────────────────────────────

class AuditLogMiddleware(BaseHTTPMiddleware):
    """Capture every HTTP request as an audit log entry.

    - Skips /metrics and /static (noise)
    - Uses _audit_ctx ContextVar to get org/key context set by auth dep
    - Writes to DB non-blockingly (asyncio.ensure_future)
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        start = time.monotonic()
        _audit_ctx.set({})

        response = await call_next(request)

        path = request.url.path
        if path.startswith("/static") or path == "/metrics":
            return response

        duration_ms = round((time.monotonic() - start) * 1000, 2)
        ctx_data = _audit_ctx.get() or {}

        if _audit_repo:
            entry = AuditEntry(
                endpoint=path,
                method=request.method,
                timestamp=datetime.now(UTC).isoformat(),
                org_id=ctx_data.get("org_id"),
                key_id=ctx_data.get("key_id"),
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                request_id=getattr(request.state, "request_id", None),
                duration_ms=duration_ms,
                user_agent=(request.headers.get("user-agent", "")[:512] or None),
            )
            # Non-blocking write — don't delay the response
            asyncio.ensure_future(_audit_repo.write(entry))

        return response


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


# ── API version header middleware ─────────────────────────────────────────────

class APIVersionMiddleware(BaseHTTPMiddleware):
    """Stamps every response with X-API-Version and routes /api/v1/* → /api/*."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        # Transparent rewrite: /api/v1/foo → /api/foo
        path = request.url.path
        if path.startswith("/api/v1/"):
            new_path = "/api/" + path[len("/api/v1/"):]
            request.scope["path"] = new_path
            request.scope["raw_path"] = new_path.encode()

        response = await call_next(request)
        response.headers["X-API-Version"] = "1.1.0"
        response.headers["X-API-Min-Version"] = "1.0.0"
        return response


# ── Middleware (outermost first) ───────────────────────────────────────────────
origins = ["*"] if settings.allow_all_origins else settings.allowed_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
app.state.limiter = limiter
app.add_middleware(AuditLogMiddleware)
app.add_middleware(APIVersionMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)

# ── Static files ───────────────────────────────────────────────────────────────
_static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


# ── Auth / RBAC dependencies ───────────────────────────────────────────────────

async def get_org_context(request: Request) -> OrgContext:
    """Resolve the API key to an OrgContext.

    Resolution order:
    1. Auth disabled → anonymous OWNER (dev mode)
    2. Flat RAI_API_KEYS (legacy) → OWNER
    3. DB-backed org key → role from DB
    4. No match → 401
    """
    if not settings.auth_enabled:
        ctx = OrgContext(key_id="anon", role=Role.OWNER, is_legacy=True)
        _audit_ctx.set({"org_id": None, "key_id": "anon"})
        return ctx

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, detail="Missing or invalid Authorization header")

    token = auth_header[7:].strip()

    if settings.api_keys and token in settings.api_keys:
        ctx = OrgContext(key_id="legacy", role=Role.OWNER, is_legacy=True)
        _audit_ctx.set({"org_id": None, "key_id": "legacy"})
        return ctx

    if _org_repo:
        ctx = await _org_repo.authenticate(token)
        if ctx:
            _audit_ctx.set({"org_id": ctx.org_id, "key_id": ctx.key_id})
            return ctx

    raise HTTPException(401, detail="Invalid API key")


def require_role(min_role: Role):
    """FastAPI dependency factory — enforces minimum role level."""
    async def _dep(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
        if not has_permission(ctx.role, min_role):
            raise HTTPException(
                403,
                detail=f"Requires {min_role.value} role or higher. Your role: {ctx.role.value}",
            )
        return ctx
    return _dep


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


class EvalCompareRequest(BaseModel):
    model_a: str = Field(..., min_length=1, max_length=100)
    model_b: str = Field(..., min_length=1, max_length=100)
    provider_a: str = Field("unknown", max_length=50)
    provider_b: str = Field("unknown", max_length=50)
    prompts: list[dict[str, str]] = Field(..., min_length=1, max_length=50)
    responses_a: list[dict[str, str]] = Field(..., min_length=1, max_length=50)
    responses_b: list[dict[str, str]] = Field(..., min_length=1, max_length=50)


class EvalBenchmarkRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=100)
    provider: str = Field("unknown", max_length=50)
    suite: str = Field(..., pattern="^(truthfulqa|bbq|hellaswag)$")
    responses: dict[str, str] = Field(...)
    set_as_baseline: bool = Field(False)


class EvalDatasetScanRequest(BaseModel):
    texts: list[str] = Field(..., min_length=1, max_length=5000)
    filename: str = Field("upload", max_length=200)


class CreateOrgRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r"^[a-z0-9\-]+$")
    monthly_budget_usd: float = Field(10_000.0, ge=0.0)


class CreateKeyRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    role: str = Field("ANALYST", pattern="^(OWNER|ADMIN|ANALYST|VIEWER)$")


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
    orgs_count = len(await _org_repo.list_orgs()) if _org_repo else 0

    return {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.1.0",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "db_backend": db_backend,
            "rate_limit_backend": rl_backend,
            "otel": "enabled" if settings.otel_endpoint else "disabled",
            "auth": "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled",
            "websocket_connections": _ws_manager.connection_count,
            "webhooks_registered": len(_webhook_manager.list()),
            "orgs": orgs_count,
        },
        "modules": [
            "trust_score", "ai_passport", "guardrails", "hallucination",
            "compliance", "redteam", "cost_tracker", "cost_analyzer",
            "model_router", "drift_monitor", "websockets", "webhooks",
            "prometheus", "rbac", "orgs", "audit_log",
            "eval_compare", "eval_benchmarks", "eval_regression", "dataset_scan",
            "sso_oidc", "api_versioning", "support", "mcp_server", "billing",
        ],
        "api_versions": ["1.0", "1.1"],
        "stable_since": "1.0.0",
    }


@app.get("/api/metrics", tags=["ops"])
@limiter.limit("60/minute")
async def metrics(request: Request, _auth: OrgContext = Depends(require_role(Role.ANALYST))) -> dict[str, Any]:
    total_requests = _REQUEST_COUNTER["total"]
    errors = _REQUEST_COUNTER["errors"]
    total_cost = await _cost_repo.total_cost(30) if _cost_repo else 0.0
    audit_count = await _audit_repo.count(30) if _audit_repo else 0
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
        "audit_entries_30d": audit_count,
    }


@app.get("/metrics", tags=["ops"], include_in_schema=False)
async def prometheus_metrics() -> Response:
    observe_websocket_connections(_ws_manager.connection_count)
    body, content_type = get_metrics_output()
    return Response(content=body, media_type=content_type)


# ── Organizations & RBAC ───────────────────────────────────────────────────────

@app.post("/api/orgs", tags=["rbac"], status_code=201)
@limiter.limit("10/minute")
async def create_org(
    request: Request,
    req: CreateOrgRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    existing = await _org_repo.get_org_by_slug(req.slug)
    if existing:
        raise HTTPException(409, f"Slug '{req.slug}' is already taken")
    org = await _org_repo.create_org(req.name, req.slug, req.monthly_budget_usd)
    return org.to_dict()


@app.get("/api/orgs", tags=["rbac"])
@limiter.limit("60/minute")
async def list_orgs(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    orgs = await _org_repo.list_orgs()
    return {"orgs": [o.to_dict() for o in orgs], "count": len(orgs)}


@app.get("/api/orgs/{org_id}", tags=["rbac"])
@limiter.limit("120/minute")
async def get_org(
    request: Request,
    org_id: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    org = await _org_repo.get_org(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    return org.to_dict()


@app.delete("/api/orgs/{org_id}", tags=["rbac"])
@limiter.limit("10/minute")
async def delete_org(
    request: Request,
    org_id: str,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    deleted = await _org_repo.delete_org(org_id)
    if not deleted:
        raise HTTPException(404, "Organization not found")
    return {"deleted": org_id}


@app.post("/api/orgs/{org_id}/keys", tags=["rbac"], status_code=201)
@limiter.limit("20/minute")
async def create_api_key(
    request: Request,
    org_id: str,
    req: CreateKeyRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    org = await _org_repo.get_org(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    role = role_from_str(req.role)
    key_rec, raw_key = await _org_repo.create_key(org_id, req.name, role)
    return key_rec.to_dict(include_key=raw_key)


@app.get("/api/orgs/{org_id}/keys", tags=["rbac"])
@limiter.limit("60/minute")
async def list_api_keys(
    request: Request,
    org_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    keys = await _org_repo.list_keys(org_id)
    return {"keys": [k.to_dict() for k in keys]}


@app.delete("/api/orgs/{org_id}/keys/{key_id}", tags=["rbac"])
@limiter.limit("20/minute")
async def revoke_api_key(
    request: Request,
    org_id: str,
    key_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    revoked = await _org_repo.revoke_key(key_id)
    if not revoked:
        raise HTTPException(404, "Key not found")
    return {"revoked": key_id}


# ── Model Evaluation Framework ────────────────────────────────────────────────

@app.post("/api/eval/compare", tags=["eval"], status_code=201)
@limiter.limit("20/minute")
async def eval_compare(
    request: Request,
    req: EvalCompareRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    prompts = [
        EvalPrompt(
            id=p.get("id", ""),
            prompt=p.get("prompt", ""),
            expected=p.get("expected", ""),
            category=p.get("category", ""),
        )
        for p in req.prompts
    ]
    ra = [
        ModelResponse(
            prompt_id=r.get("prompt_id", ""),
            model=req.model_a,
            provider=req.provider_a,
            response=r.get("response", ""),
        )
        for r in req.responses_a
    ]
    rb = [
        ModelResponse(
            prompt_id=r.get("prompt_id", ""),
            model=req.model_b,
            provider=req.provider_b,
            response=r.get("response", ""),
        )
        for r in req.responses_b
    ]
    result = _comparator.compare(
        prompts=prompts,
        responses_a=ra,
        responses_b=rb,
        model_a=req.model_a,
        model_b=req.model_b,
        provider_a=req.provider_a,
        provider_b=req.provider_b,
    )
    payload = result.to_dict()
    if _eval_repo:
        await _eval_repo.save_run(
            run_type="comparison",
            model=f"{req.model_a}|{req.model_b}",
            payload=payload,
            provider=f"{req.provider_a}|{req.provider_b}",
            org_id=_auth.org_id,
        )
    return payload


@app.post("/api/eval/benchmark", tags=["eval"], status_code=201)
@limiter.limit("10/minute")
async def eval_benchmark(
    request: Request,
    req: EvalBenchmarkRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    suite = BenchmarkSuite(req.suite)
    result = _benchmark_runner.run(
        model=req.model,
        provider=req.provider,
        suite=suite,
        responses=req.responses,
    )
    payload = result.to_dict()
    if _eval_repo:
        await _eval_repo.save_run(
            run_type="benchmark",
            model=req.model,
            payload=payload,
            provider=req.provider,
            suite=req.suite,
            org_id=_auth.org_id,
        )
    if req.set_as_baseline:
        _regression_detector.set_baseline(req.model, result)
        if _eval_repo:
            for metric in ("accuracy", "bias_rate", "overall_score"):
                score = getattr(result, metric)
                await _eval_repo.set_baseline(
                    model=req.model,
                    suite=req.suite,
                    metric=metric,
                    score=score,
                    org_id=_auth.org_id,
                )
    regressions = _regression_detector.check(req.model, result)
    payload["regressions"] = [r.to_dict() for r in regressions]
    return payload


@app.get("/api/eval/benchmark/prompts/{suite}", tags=["eval"])
@limiter.limit("60/minute")
async def eval_benchmark_prompts(
    request: Request,
    suite: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    try:
        s = BenchmarkSuite(suite)
    except ValueError:
        raise HTTPException(400, f"Unknown suite: {suite}. Valid: truthfulqa, bbq, hellaswag") from None
    prompts = _benchmark_runner.get_prompts(s)
    return {"suite": suite, "prompts": prompts, "count": len(prompts)}


@app.get("/api/eval/regression/{model}", tags=["eval"])
@limiter.limit("60/minute")
async def eval_regression(
    request: Request,
    model: str,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    baselines = _regression_detector.get_baselines(model)
    db_baselines: dict[str, float] = {}
    if _eval_repo:
        db_baselines = await _eval_repo.get_baselines(model)
    return {
        "model": model,
        "in_memory_baselines": baselines,
        "db_baselines": db_baselines,
        "has_baseline": bool(baselines or db_baselines),
    }


@app.post("/api/eval/dataset-scan", tags=["eval"], status_code=201)
@limiter.limit("10/minute")
async def eval_dataset_scan(
    request: Request,
    req: EvalDatasetScanRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    result = _dataset_scanner.scan_texts(req.texts, filename=req.filename)
    payload = result.to_dict()
    if _eval_repo:
        await _eval_repo.save_run(
            run_type="dataset_scan",
            model="dataset",
            payload=payload,
            org_id=_auth.org_id,
        )
    return payload


@app.get("/api/eval/results", tags=["eval"])
@limiter.limit("30/minute")
async def eval_results(
    request: Request,
    run_type: str | None = Query(default=None),
    model: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    if not _eval_repo:
        return {"runs": [], "count": 0}
    runs = await _eval_repo.list_runs(
        run_type=run_type,
        model=model,
        org_id=_auth.org_id,
        limit=limit,
        offset=offset,
    )
    return {"runs": runs, "count": len(runs)}


# ── Audit log ─────────────────────────────────────────────────────────────────

@app.get("/api/audit-log", tags=["rbac"])
@limiter.limit("30/minute")
async def query_audit_log(
    request: Request,
    days: int = Query(default=7, ge=1, le=90),
    org_id: str | None = Query(default=None),
    endpoint: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    entries = await _audit_repo.query(
        org_id=org_id, endpoint=endpoint, days=days, limit=limit, offset=offset
    )
    total = await _audit_repo.count(days=days, org_id=org_id)
    summary = await _audit_repo.endpoint_summary(days=days)
    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "endpoint_summary": summary,
    }


# ── WebSocket live dashboard ───────────────────────────────────────────────────

@app.websocket("/ws/dashboard")
async def websocket_dashboard(
    websocket: WebSocket,
    token: str = Query(default=""),
) -> None:
    if settings.auth_enabled and settings.api_keys:
        if token not in settings.api_keys:
            await websocket.close(code=4001, reason="Unauthorized")
            return

    api_key = token or "anonymous"
    await _ws_manager.connect(websocket, api_key)
    observe_websocket_connections(_ws_manager.connection_count)

    try:
        snapshot: dict[str, Any] = {"type": "connected", "version": "0.9.0"}
        if _cost_repo:
            snapshot["monthly_spend_usd"] = round(await _cost_repo.total_cost(30), 4)
        if _trust_repo:
            snapshot["models"] = await _trust_repo.all_models()
        if _org_repo:
            snapshot["org_count"] = len(await _org_repo.list_orgs())
        await websocket.send_json(snapshot)

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
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    try:
        events = [WebhookEvent(e) for e in req.events]
    except ValueError as exc:
        raise HTTPException(400, f"Invalid event type: {exc}") from exc
    config = WebhookConfig(
        url=req.url, events=events,
        provider=WebhookProvider(req.provider),
        secret=req.secret, description=req.description,
        max_retries=req.max_retries,
    )
    _webhook_manager.register(config)
    return config.to_dict()


@app.get("/api/webhooks", tags=["webhooks"])
@limiter.limit("60/minute")
async def list_webhooks(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    return {"webhooks": [c.to_dict() for c in _webhook_manager.list()]}


@app.delete("/api/webhooks/{webhook_id}", tags=["webhooks"])
@limiter.limit("30/minute")
async def delete_webhook(
    request: Request,
    webhook_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    if not _webhook_manager.remove(webhook_id):
        raise HTTPException(404, "Webhook not found")
    return {"deleted": webhook_id}


@app.get("/api/webhooks/deliveries", tags=["webhooks"])
@limiter.limit("60/minute")
async def webhook_deliveries(
    request: Request,
    limit: int = Query(default=50, ge=1, le=500),
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
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
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    cfg = _webhook_manager.get(webhook_id)
    if cfg is None:
        raise HTTPException(404, "Webhook not found")
    deliveries = await _webhook_manager.fire(
        WebhookEvent.TRUST_SCORE_CHANGED,
        {"model": "test-model", "provider": "test", "score": 85.0, "test": True},
    )
    result = next((d for d in deliveries if d.webhook_id == webhook_id), None)
    return result.to_dict() if result else {"success": False, "error": "no delivery"}


# ── Trust & Evaluation ─────────────────────────────────────────────────────────

@app.post("/api/evaluate", tags=["trust"])
@limiter.limit(settings.rate_limit_evaluate)
async def evaluate_model(
    request: Request,
    req: EvaluateRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
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

    observe_trust_score(req.model_name, req.provider, score.overall)
    record_evaluation(req.model_name, req.provider, score.overall, score.grade)

    await _ws_manager.broadcast({
        "type": "trust_score",
        "data": {
            "model": req.model_name, "provider": req.provider,
            "score": score.overall, "grade": score.grade,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    })

    if drift_alert:
        observe_drift_alert(drift_alert.get("severity", "LOW"))
        deliveries = await _webhook_manager.fire(
            WebhookEvent.DRIFT_ALERT,
            {"model": req.model_name, "provider": req.provider,
             "delta": drift_alert.get("delta"), "severity": drift_alert.get("severity"),
             "score": score.overall},
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.DRIFT_ALERT.value, d.success)
        await _ws_manager.broadcast({
            "type": "drift_alert",
            "data": {**drift_alert, "model": req.model_name, "provider": req.provider},
        })

    logger.info("evaluation", model=req.model_name, provider=req.provider,
                score=score.overall, grade=score.grade)
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
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    if limit < 1 or limit > 365:
        raise HTTPException(400, "limit must be between 1 and 365")
    history = await _trust_repo.history(model_name, provider, limit=limit)
    trend = await _trust_repo.trend(model_name, provider)
    return {"model": model_name, "provider": provider, "history": history, "trend": trend}


@app.get("/api/models", tags=["trust"])
@limiter.limit("120/minute")
async def list_models(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    return {"models": await _trust_repo.all_models()}


# ── Guardrails ─────────────────────────────────────────────────────────────────

@app.post("/api/scan", tags=["guardrails"])
@limiter.limit("200/minute")
async def scan_text(
    request: Request,
    req: ScanTextRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    result = _guardrails.scan(req.text)
    blocked = result.is_blocked
    observe_guardrail(blocked)
    record_guardrail_scan(blocked, len(result.pii_findings))

    if blocked:
        await _ws_manager.broadcast({
            "type": "guardrail",
            "data": {"blocked": True, "pii_count": len(result.pii_findings),
                     "timestamp": datetime.now(UTC).isoformat()},
        })
        deliveries = await _webhook_manager.fire(
            WebhookEvent.GUARDRAIL_TRIGGERED,
            {"pii_count": len(result.pii_findings), "block_reasons": result.block_reasons},
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
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
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
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    usage = TokenUsage.create(
        provider=req.provider, model=req.model,
        input_tokens=req.input_tokens, output_tokens=req.output_tokens,
        team=req.team, application=req.application,
    )
    cost_record = await _cost_repo.record(usage)
    observe_cost(req.model, req.provider, cost_record.total_cost, req.input_tokens, req.output_tokens)
    record_cost(req.provider, req.model, cost_record.total_cost, req.input_tokens + req.output_tokens)

    await _ws_manager.broadcast({
        "type": "cost_update",
        "data": {"model": req.model, "provider": req.provider,
                 "cost_usd": cost_record.total_cost,
                 "tokens": req.input_tokens + req.output_tokens,
                 "timestamp": datetime.now(UTC).isoformat()},
    })

    budget = await _cost_repo.check_budget()
    if budget.is_exceeded:
        deliveries = await _webhook_manager.fire(
            WebhookEvent.BUDGET_EXCEEDED,
            {"monthly_limit_usd": budget.monthly_limit_usd,
             "total_spent_usd": budget.total_spent_usd,
             "overage_usd": round(budget.total_spent_usd - budget.monthly_limit_usd, 4)},
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.BUDGET_EXCEEDED.value, d.success)

    return cost_record.to_dict()


@app.get("/api/cost/summary", tags=["cost"])
@limiter.limit("60/minute")
async def cost_summary(
    request: Request,
    days: int = 30,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
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
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
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
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    decision = _router.route(req.task_description, req.quality_requirement)
    return decision.to_dict()


@app.get("/api/cost/models", tags=["cost"])
@limiter.limit("60/minute")
async def model_pricing(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    return {"models": _router.provider_comparison()}


# ── Drift ──────────────────────────────────────────────────────────────────────

@app.get("/api/drift/{model_name}/{provider}", tags=["drift"])
@limiter.limit("120/minute")
async def get_drift_trend(
    request: Request,
    model_name: str,
    provider: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    trend = await _trust_repo.trend(model_name, provider)
    history = await _trust_repo.history(model_name, provider, limit=10)
    return {"trend": trend, "recent_history": history}


# ── API versioning ─────────────────────────────────────────────────────────────

@app.get("/api/version", tags=["ops"])
async def api_version() -> dict[str, Any]:
    """Return full version and stability metadata."""
    return {
        "version": "1.1.0",
        "major": 1,
        "minor": 1,
        "patch": 0,
        "stable": True,
        "api_versions": ["1.0", "1.1"],
        "current_api_prefix": "/api/v1",
        "deprecated_prefixes": [],
        "release_date": "2026-06-26",
        "changelog_url": "https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/CHANGELOG.md",
    }


# ── SSO / OAuth2 / OIDC ───────────────────────────────────────────────────────

@app.get("/api/auth/providers", tags=["auth"])
async def list_auth_providers() -> dict[str, Any]:
    """List configured authentication providers."""
    providers = []
    if settings.oidc_issuer:
        providers.append({
            "id": "oidc",
            "type": "oidc",
            "issuer": settings.oidc_issuer,
            "client_id": settings.oidc_client_id,
            "login_url": "/api/auth/login/oidc",
        })
    providers.append({
        "id": "api_key",
        "type": "api_key",
        "description": "Static API key via Authorization: Bearer <key>",
    })
    return {"providers": providers, "count": len(providers)}


@app.get("/api/auth/login/{provider_id}", tags=["auth"])
async def auth_login(provider_id: str, redirect_uri: str = "") -> JSONResponse:
    """Initiate OAuth2 authorization code flow."""
    if provider_id != "oidc" or not _oidc_provider:
        raise HTTPException(404, f"Unknown or unconfigured provider: {provider_id!r}")

    state = secrets.token_urlsafe(32)
    _oidc_state_store[state] = time.monotonic()

    target_redirect = redirect_uri or settings.oidc_redirect_uri
    url = _oidc_provider.authorization_url(
        redirect_uri=target_redirect,
        state=state,
        scopes=settings.oidc_scopes,
    )
    return JSONResponse({"authorization_url": url, "state": state})


@app.get("/api/auth/callback", tags=["auth"])
async def auth_callback(
    code: str = Query(...),
    state: str = Query(...),
) -> dict[str, Any]:
    """Handle the OAuth2 callback — exchange code for tokens and return claims."""
    if not _oidc_provider:
        raise HTTPException(501, "OIDC not configured")

    issued_at = _oidc_state_store.pop(state, None)
    if issued_at is None:
        raise HTTPException(400, "Invalid or expired OAuth2 state parameter")
    if time.monotonic() - issued_at > 300:
        raise HTTPException(400, "OAuth2 state has expired (>5 min)")

    try:
        tokens = await _oidc_provider.exchange_code(
            code=code,
            redirect_uri=settings.oidc_redirect_uri,
            client_secret=settings.oidc_client_secret,
        )
    except ValueError as e:
        raise HTTPException(400, f"Token exchange failed: {e}") from None

    id_token = tokens.get("id_token") or tokens.get("access_token", "")
    try:
        claims = await _oidc_provider.validate_token(id_token)
    except ValueError as e:
        raise HTTPException(401, f"Token validation failed: {e}") from None

    return {
        "sub": claims.sub,
        "email": claims.email,
        "name": claims.name,
        "roles": claims.roles,
        "org_id": claims.org_id,
        "access_token": tokens.get("access_token"),
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_in": tokens.get("expires_in"),
    }


@app.post("/api/auth/logout", tags=["auth"])
async def auth_logout(
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Invalidate the current session (client should discard its token)."""
    return {"logged_out": True, "timestamp": datetime.now(UTC).isoformat()}


# ── Support tier ───────────────────────────────────────────────────────────────

@app.get("/api/support", tags=["support"])
async def support_info() -> dict[str, Any]:
    """Return SLA tiers and support contact information."""
    return {
        "tiers": [
            {
                "name": "Standard",
                "uptime_sla": "99.0%",
                "response_time": "Next business day",
                "channels": ["email"],
                "price": "Included",
            },
            {
                "name": "Professional",
                "uptime_sla": "99.5%",
                "response_time": "4 business hours",
                "channels": ["email", "slack"],
                "price": "Contact sales",
            },
            {
                "name": "Enterprise",
                "uptime_sla": "99.9%",
                "response_time": "1 hour (24/7)",
                "channels": ["email", "slack", "phone", "dedicated TAM"],
                "price": "Contact sales",
            },
        ],
        "contact": {
            "email": "milchcreamfoods@gmail.com",
            "docs": "https://github.com/Guruprasath-Annadurai/ResponsibleAi",
            "issues": "https://github.com/Guruprasath-Annadurai/ResponsibleAi/issues",
        },
        "platform_version": "1.1.0",
    }


@app.get("/api/support/status", tags=["support"])
async def platform_status() -> dict[str, Any]:
    """Public platform status — no auth required."""
    db_ok = True
    try:
        if _cost_repo:
            await _cost_repo.request_count()
    except Exception:
        db_ok = False
    return {
        "platform": "ResponsibleAI Governance Platform",
        "version": "1.1.0",
        "status": "operational" if db_ok else "degraded",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ── Audit log ──────────────────────────────────────────────────────────────────

@app.get("/api/audit", tags=["audit"])
async def list_audit_entries(
    org_id: str | None = Query(None, description="Filter by organisation ID"),
    endpoint: str | None = Query(None, description="Filter by endpoint path"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Query the governance audit log with optional filters."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    rows = await _audit_repo.query(org_id=org_id, endpoint=endpoint, days=days, limit=limit, offset=offset)
    total = await _audit_repo.count(days=days, org_id=org_id)
    return {
        "entries": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "days": days,
    }


@app.get("/api/audit/export", tags=["audit"])
async def export_audit_log(
    org_id: str | None = Query(None),
    days: int = Query(30, ge=1, le=365),
    _auth: OrgContext = Depends(get_org_context),
) -> Response:
    """Export audit log as CSV."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    rows = await _audit_repo.query(org_id=org_id, days=days, limit=10000)
    headers_row = "id,timestamp,org_id,key_id,endpoint,method,status_code,ip_address,request_id,duration_ms\n"
    lines = [headers_row]
    for r in rows:
        lines.append(",".join([
            str(r.get("id", "")),
            str(r.get("timestamp", "")),
            str(r.get("org_id", "")),
            str(r.get("key_id", "")),
            str(r.get("endpoint", "")),
            str(r.get("method", "")),
            str(r.get("status_code", "")),
            str(r.get("ip_address", "")),
            str(r.get("request_id", "")),
            str(r.get("duration_ms", "")),
        ]) + "\n")
    return Response(
        content="".join(lines),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit-{days}d.csv"},
    )


@app.get("/api/audit/summary", tags=["audit"])
async def audit_endpoint_summary(
    days: int = Query(7, ge=1, le=90),
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Top endpoints by request count and average latency."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    summary = await _audit_repo.endpoint_summary(days=days)
    return {"days": days, "endpoints": summary}


# ── Red team ───────────────────────────────────────────────────────────────────

@app.get("/api/redteam/payloads", tags=["redteam"])
async def get_redteam_payloads(
    categories: list[str] | None = Query(None, description="Filter by attack category"),
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Return all adversarial attack payloads, optionally filtered by category."""
    sim = RedTeamSimulator()
    payloads = sim.get_attack_payloads()
    if categories:
        payloads = [p for p in payloads if p["category"] in categories]
    return {
        "count": len(payloads),
        "payloads": payloads,
        "categories": list({p["category"] for p in payloads}),
    }


class RedTeamAnalyzeRequest(BaseModel):
    model_name: str = Field(..., description="Name of the model under test")
    provider: str = Field(..., description="Model provider")
    responses: dict[str, str] = Field(..., description="Map of attack_name → model_response_text")


@app.post("/api/redteam/analyze", tags=["redteam"])
async def analyze_redteam_responses(
    body: RedTeamAnalyzeRequest,
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Analyse model responses to red team payloads and return a security report."""
    sim = RedTeamSimulator()
    report = sim.analyze_responses(body.model_name, body.provider, body.responses)
    return report.to_dict()


# ── Billing / revenue metering ─────────────────────────────────────────────────

@app.get("/api/billing/usage", tags=["billing"])
async def billing_usage(
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Return usage and cost summary for billing and revenue reporting."""
    if not _cost_repo:
        raise HTTPException(503, "Cost repository not initialised")
    total_cost = await _cost_repo.total_cost(days=days)
    total_tokens = await _cost_repo.total_tokens(days=days)
    request_count = await _cost_repo.request_count(days=days)
    model_breakdown = await _cost_repo.get_model_breakdown(days=days)
    return {
        "period_days": days,
        "total_cost_usd": round(total_cost, 6),
        "total_requests": request_count,
        "total_tokens": total_tokens,
        "cost_by_model": {k: round(v, 6) for k, v in model_breakdown.items()},
        "timestamp": datetime.now(UTC).isoformat(),
    }
