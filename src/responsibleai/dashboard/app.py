"""Governance Dashboard — production FastAPI application (v1.0.0)."""

from __future__ import annotations

import asyncio
import secrets
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import quote

from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
    Response,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from responsibleai.auth import mfa
from responsibleai.auth.oidc import OIDCProvider
from responsibleai.billing import StripeBillingError, StripeNotConfiguredError, StripeService
from responsibleai.compliance.engine import ComplianceEngine
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.models import BudgetPolicy, TokenUsage
from responsibleai.cost.router import ModelRouter
from responsibleai.dashboard.config import get_settings, multi_replica_problems
from responsibleai.dashboard.logging_config import configure_logging, get_logger
from responsibleai.dashboard.middleware import (
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    global_exception_handler,
    http_exception_handler,
)
from responsibleai.dashboard.plan_rate_limiter import PlanRateLimiter
from responsibleai.dashboard.prometheus import (
    get_metrics_output,
    observe_cost,
    observe_drift_alert,
    observe_governance_approval,
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
    ApprovalActionMismatchError,
    ApprovalAlreadyResolvedError,
    ApprovalExpiredError,
    ApprovalNotApprovedError,
    ApprovalNotFoundError,
    ApprovalRepository,
    AuditRepository,
    CostRepository,
    EvalRepository,
    EvidenceRepository,
    IncidentRepository,
    LeaderboardRepository,
    McpUsageRepository,
    OrgRepository,
    PassportRepository,
    PolicyRepository,
    PolicyRuleNotFoundError,
    PublicIncidentRepository,
    SelfApprovalError,
    SSORequiredError,
    TrustRepository,
    UpstreamServerNotFoundError,
    UpstreamServerRepository,
    WebhookConfigRepository,
    WebhookDeliveryRepository,
    create_engine,
)
from responsibleai.db.engine import DatabaseEngine
from responsibleai.db.migrate import MigrationError, run_migrations_or_raise
from responsibleai.eval import (
    BenchmarkRunner,
    BenchmarkSuite,
    DatasetBiasScanner,
    EvalPrompt,
    ModelComparator,
    ModelResponse,
    RegressionDetector,
)
from responsibleai.governance.approval import ApprovalStatus
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier
from responsibleai.governance.upstream import UnsafeUpstreamServerURLError
from responsibleai.governance.upstream_executor import (
    UpstreamMCPExecutor,
    UpstreamServerNotAvailableError,
)
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.incidents.logic import build_incident_record
from responsibleai.leaderboard.models import METHODOLOGY_VERSION
from responsibleai.leaderboard.providers import ProviderNotConfiguredError, get_adapter
from responsibleai.leaderboard.runner import LeaderboardRunner
from responsibleai.mcp.governance_integration import resume_approval
from responsibleai.mcp.licensing import monthly_quota, plan_catalog
from responsibleai.mcp.upstream_dispatch import apply_upstream_governance
from responsibleai.rbac import (
    AuditEntry,
    OrgContext,
    Plan,
    Role,
    has_permission,
    has_plan,
    role_from_str,
)
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.supplychain import McpServerManifest, McpToolDescriptor, SupplyChainScanner
from responsibleai.trust.badge import render_badge_svg
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine
from responsibleai.webhooks import (
    UnsafeWebhookURLError,
    WebhookConfig,
    WebhookEvent,
    WebhookManager,
    WebhookProvider,
    validate_webhook_url,
)

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

# ── Audit log org/key attribution ──────────────────────────────────────────────
# Deliberately NOT a ContextVar: AuditLogMiddleware is a BaseHTTPMiddleware,
# and Starlette runs the downstream app (including every dependency, e.g.
# get_org_context below) in a separate task via its internal task group so
# StreamingResponse/background-task support works correctly. A ContextVar
# set inside that inner task does not propagate back to the middleware's
# own scope after `call_next()` returns — its mutations are invisible one
# task boundary up, so every audit entry silently recorded org_id=None
# regardless of the real caller. `request.state` sidesteps this because
# it's an attribute on the same `Request` object instance shared across
# that task boundary, not a per-task context var — see AuditLogMiddleware
# and get_org_context below for where it's read/written.

# ── Module singletons ──────────────────────────────────────────────────────────
_trust_engine: TrustScoreEngine | None = None
_passport_gen: PassportGenerator | None = None
_passport_repo: PassportRepository | None = None
_public_incident_repo: PublicIncidentRepository | None = None
_guardrails: GuardrailsEngine | None = None
_hallucination: HallucinationDetector | None = None
_compliance: ComplianceEngine | None = None
_cost_repo: CostRepository | None = None
_cost_analyzer: CostAnalyzer | None = None
_router: ModelRouter | None = None
_trust_repo: TrustRepository | None = None
_org_repo: OrgRepository | None = None
_audit_repo: AuditRepository | None = None
_incident_repo: IncidentRepository | None = None
_leaderboard_repo: LeaderboardRepository | None = None
_leaderboard_runner: LeaderboardRunner | None = None
_mcp_usage_repo: McpUsageRepository | None = None
_evidence_repo: EvidenceRepository | None = None
_approval_repo: ApprovalRepository | None = None
_policy_repo: PolicyRepository | None = None
_upstream_registry: UpstreamServerRepository | None = None
_upstream_gateway: WhitePactRuntimeGateway = WhitePactRuntimeGateway()
_db_engine: DatabaseEngine | None = None
_ws_manager: ConnectionManager = ConnectionManager()
_webhook_manager: WebhookManager = WebhookManager()
_supplychain_scanner: SupplyChainScanner = SupplyChainScanner()
_eval_repo: EvalRepository | None = None
_comparator: ModelComparator | None = None
_benchmark_runner: BenchmarkRunner | None = None
_regression_detector: RegressionDetector = RegressionDetector()
_dataset_scanner: DatasetBiasScanner | None = None
_oidc_provider: OIDCProvider | None = None
_oidc_state_store: dict[str, float] = {}  # state → issued_at; cleared on use
_OIDC_STATE_TTL = 300.0  # seconds — matches callback expiry window
_stripe_service: StripeService | None = None
_plan_rate_limiter: PlanRateLimiter | None = None
_pending_audit_writes: set[asyncio.Task[Any]] = set()

_T = TypeVar("_T")


def _ready(value: _T | None) -> _T:
    """Narrow a lifespan-initialized singleton for type checkers.

    These singletons are always assigned during the `lifespan` startup phase
    before any route can receive traffic. A None here means a route ran
    before startup completed — a programming/wiring error, not a runtime
    condition callers should handle gracefully.
    """
    assert value is not None, "accessed before application startup completed"
    return value


async def _oidc_state_cleanup() -> None:
    """Periodic task: evict OIDC states that were never exchanged (abandoned logins)."""
    while True:
        await asyncio.sleep(60)
        now = asyncio.get_event_loop().time()
        stale = [k for k, t in list(_oidc_state_store.items()) if now - t > _OIDC_STATE_TTL]
        for k in stale:
            _oidc_state_store.pop(k, None)


@asynccontextmanager
async def lifespan(application: FastAPI):
    global _trust_engine, _passport_gen, _guardrails, _hallucination
    global _compliance, _cost_repo, _cost_analyzer, _router, _trust_repo
    global _org_repo, _audit_repo, _incident_repo, _leaderboard_repo, _leaderboard_runner
    global _passport_repo, _public_incident_repo, _db_engine, _mcp_usage_repo
    global _evidence_repo, _approval_repo, _policy_repo, _upstream_registry
    global _eval_repo, _comparator, _benchmark_runner, _dataset_scanner
    global _oidc_provider, _stripe_service, _plan_rate_limiter

    setup_telemetry(
        service_name=settings.otel_service_name,
        otlp_endpoint=settings.otel_endpoint,
        otlp_headers=settings.otel_headers_dict,
    )

    if settings.auto_migrate:
        try:
            await run_migrations_or_raise(settings.effective_db_url)
        except MigrationError as exc:
            logger.error("db_migration_failed", error=str(exc))
            raise RuntimeError(
                "Startup aborted: database migrations failed. Fix the "
                "underlying issue (see log above) or set RAI_AUTO_MIGRATE=false "
                "and run `alembic upgrade head` manually. Refusing to serve "
                "traffic against a schema that may be missing columns the "
                "code expects."
            ) from exc

    _db_engine = create_engine(settings.effective_db_url)
    await _db_engine.init()
    _plan_rate_limiter = PlanRateLimiter(redis_url=settings.redis_url)

    policy = BudgetPolicy(monthly_limit_usd=settings.monthly_budget_usd)
    _cost_repo    = CostRepository(_db_engine, policy=policy)
    _trust_repo   = TrustRepository(_db_engine, alert_threshold=settings.alert_threshold)
    _org_repo     = OrgRepository(_db_engine)
    _audit_repo   = AuditRepository(_db_engine)
    _incident_repo = IncidentRepository(_db_engine)
    _leaderboard_repo = LeaderboardRepository(_db_engine)
    _leaderboard_runner = LeaderboardRunner()
    _mcp_usage_repo = McpUsageRepository(_db_engine)
    _trust_engine = TrustScoreEngine()
    _passport_gen = PassportGenerator()
    _passport_repo = PassportRepository(_db_engine)
    _public_incident_repo = PublicIncidentRepository(_db_engine)
    _evidence_repo = EvidenceRepository(_db_engine)
    _approval_repo = ApprovalRepository(_db_engine)
    _policy_repo = PolicyRepository(_db_engine)
    _upstream_registry = UpstreamServerRepository(_db_engine)
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

    if settings.stripe_secret_key:
        try:
            _stripe_service = StripeService(
                secret_key=settings.stripe_secret_key,
                webhook_secret=settings.stripe_webhook_secret,
                price_ids={
                    Plan.PRO: settings.stripe_price_id_pro or "",
                    Plan.ENTERPRISE: settings.stripe_price_id_enterprise or "",
                },
            )
        except StripeNotConfiguredError as exc:
            logger.warning("stripe_init_skipped", reason=str(exc))

    # Attach DB-backed delivery log + start persistent retry worker
    _webhook_delivery_repo = WebhookDeliveryRepository(_db_engine)
    _webhook_manager.set_repository(_webhook_delivery_repo)
    # Attach DB-backed config storage and reload any previously registered
    # webhooks — without this they only ever lived in memory and vanished
    # on every restart (see db/webhook_repository.py:WebhookConfigRepository).
    _webhook_config_repo = WebhookConfigRepository(_db_engine)
    _webhook_manager.set_config_repository(_webhook_config_repo)
    loaded_webhooks = await _webhook_manager.load_configs()
    _webhook_manager.start_retry_worker()
    _oidc_cleanup_task = asyncio.create_task(_oidc_state_cleanup())

    _ws_manager.start()

    auth_status = "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled"
    db_backend   = "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    rl_backend   = "redis" if settings.redis_url else "memory"
    logger.info(
        "startup_complete",
        version="1.2.0",
        db_backend=db_backend,
        rate_limit_backend=rl_backend,
        otel=bool(settings.otel_endpoint),
        auth=auth_status,
        webhooks_loaded=loaded_webhooks,
    )

    if settings.multi_replica:
        problems = multi_replica_problems(db_backend, rl_backend)
        if problems:
            logger.warning(
                "multi_replica_misconfigured",
                replica_declared=True,
                problems=problems,
                guidance=(
                    "RAI_MULTI_REPLICA=true was set but this instance's "
                    "backends can't safely be shared across replicas. See "
                    "DEPLOY_RUNBOOK.md's multi-region/HA section."
                ),
            )

    yield

    _oidc_cleanup_task.cancel()
    _webhook_manager.stop_retry_worker()
    _ws_manager.stop()
    if _plan_rate_limiter:
        await _plan_rate_limiter.close()
    if _pending_audit_writes:
        # Drain fire-and-forget audit writes before the engine (and this
        # event loop) go away — see AuditLogMiddleware's docstring.
        await asyncio.gather(*_pending_audit_writes, return_exceptions=True)
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
    contact={"name": "Guruprasath Annadurai", "email": "annaduraiguruprasath7@gmail.com"},
    license_info={"name": "MIT"},
)


# ── Audit log middleware ───────────────────────────────────────────────────────

class AuditLogMiddleware(BaseHTTPMiddleware):
    """Capture every HTTP request as an audit log entry.

    - Skips /metrics and /static (noise)
    - Reads request.state.audit_org_id/audit_key_id, set by get_org_context
      (the auth dependency) — deliberately request.state, not a ContextVar,
      since BaseHTTPMiddleware runs the downstream app in a separate task
      and a ContextVar set there doesn't propagate back to this scope.
    - Writes to DB non-blockingly (asyncio.ensure_future), but the task is
      tracked in _pending_audit_writes and drained during shutdown -- an
      untracked fire-and-forget task can still be running (or queued on
      aiosqlite's background worker thread) when the app's event loop
      closes, which surfaces as "Cannot operate on a closed database" /
      "Event loop is closed" from a thread trying to signal completion
      back to a loop that no longer exists. Real, previously-latent bug:
      rare under normal request volume, reliable under the fast
      request-then-shutdown cycle every test in the suite performs.
    """

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        start = time.monotonic()

        response = await call_next(request)

        path = request.url.path
        if path.startswith("/static") or path == "/metrics":
            return response

        duration_ms = round((time.monotonic() - start) * 1000, 2)

        if _audit_repo:
            entry = AuditEntry(
                endpoint=path,
                method=request.method,
                timestamp=datetime.now(UTC).isoformat(),
                org_id=getattr(request.state, "audit_org_id", None),
                key_id=getattr(request.state, "audit_key_id", None),
                status_code=response.status_code,
                ip_address=request.client.host if request.client else None,
                request_id=getattr(request.state, "request_id", None),
                duration_ms=duration_ms,
                user_agent=(request.headers.get("user-agent", "")[:512] or None),
            )
            # Non-blocking write — don't delay the response. Tracked (not a
            # bare ensure_future) so shutdown can drain it — see class
            # docstring for why an untracked task is a real bug, not just
            # defensive caution.
            task = asyncio.ensure_future(_ready(_audit_repo).write(entry))
            _pending_audit_writes.add(task)
            task.add_done_callback(_pending_audit_writes.discard)

        return response


# ── Exception handlers ─────────────────────────────────────────────────────────
# Starlette's add_exception_handler stub requires Callable[[Request, Exception], ...],
# but the standard FastAPI/Starlette convention is handlers typed to their specific
# exception class — Starlette dispatches by the registered type, so this is safe.
app.add_exception_handler(Exception, global_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


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
        response.headers["X-API-Version"] = "1.2.0"
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

async def _resolve_oidc_context(token: str) -> OrgContext | None:
    """Validate an OIDC-issued Bearer JWT and map its claims to an OrgContext.

    Static API keys are prefixed "rai_"; anything else is attempted as a JWT
    when an OIDC provider is configured. This is what makes SSO login
    actually usable as an API credential — previously /api/auth/callback
    returned claims but nothing accepted the resulting token afterward.
    """
    if _oidc_provider is None or token.startswith("rai_"):
        return None
    try:
        claims = await _oidc_provider.validate_token(token)
    except ValueError:
        return None

    org = await _org_repo.get_org(claims.org_id) if (_org_repo and claims.org_id) else None
    role = Role.VIEWER
    for raw_role in claims.roles:
        candidate = role_from_str(raw_role)
        if candidate.value == raw_role.upper():
            role = candidate
            break

    return OrgContext(
        key_id=f"oidc:{claims.sub}",
        role=role,
        org_id=claims.org_id,
        org_name=org.name if org else None,
        is_legacy=False,
        plan=org.plan if org else Plan.FREE,
    )


async def get_org_context(request: Request) -> OrgContext:
    """Resolve the presented Bearer credential to an OrgContext.

    Resolution order:
    1. Auth disabled → anonymous OWNER (dev mode)
    2. Flat RAI_API_KEYS (legacy) → OWNER
    3. OIDC-issued JWT (when SSO configured) → role/org from token claims
    4. DB-backed org key → role from DB, rejected if the org enforces SSO
    5. No match → 401
    """
    if not settings.auth_enabled:
        ctx = OrgContext(key_id="anon", role=Role.OWNER, is_legacy=True)
        request.state.audit_org_id = None
        request.state.audit_key_id = "anon"
        return ctx

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(401, detail="Missing or invalid Authorization header")

    token = auth_header[7:].strip()

    if settings.api_keys and token in settings.api_keys:
        ctx = OrgContext(key_id="legacy", role=Role.OWNER, is_legacy=True)
        request.state.audit_org_id = None
        request.state.audit_key_id = "legacy"
        return ctx

    oidc_ctx = await _resolve_oidc_context(token)
    if oidc_ctx is not None:
        if _plan_rate_limiter:
            await _plan_rate_limiter.check(oidc_ctx.org_id, oidc_ctx.plan)
        request.state.audit_org_id = oidc_ctx.org_id
        request.state.audit_key_id = oidc_ctx.key_id
        return oidc_ctx

    if _org_repo:
        try:
            resolved_ctx = await _ready(_org_repo).authenticate(token)
        except SSORequiredError as exc:
            raise HTTPException(
                403,
                detail=(
                    f"Organization {exc.org_id} requires SSO login. "
                    "Static API keys are disabled — authenticate via /api/auth/login/oidc."
                ),
            ) from None
        if resolved_ctx:
            if _plan_rate_limiter:
                await _plan_rate_limiter.check(resolved_ctx.org_id, resolved_ctx.plan)
            request.state.audit_org_id = resolved_ctx.org_id
            request.state.audit_key_id = resolved_ctx.key_id
            return resolved_ctx

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


def require_plan(min_plan: Plan):
    """FastAPI dependency factory — enforces minimum billing plan.

    Used to gate paid content (the leaderboard diagnostic deep-dive) rather
    than an endpoint's RBAC role — a VIEWER on an ENTERPRISE org can read the
    diagnostic, an OWNER on a FREE org cannot.
    """
    async def _dep(ctx: OrgContext = Depends(get_org_context)) -> OrgContext:
        if not has_plan(ctx.plan, min_plan):
            raise HTTPException(
                402,
                detail=(
                    f"Requires {min_plan.value} plan or higher. Your plan: {ctx.plan.value}. "
                    "Upgrade at /api/v1/billing/checkout."
                ),
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


class IncidentCreateRequest(BaseModel):
    incident_type: str = Field(
        "other",
        pattern="^(pii_leak|jailbreak_attempt|bias_trigger|hallucination|policy_violation|cost_overrun|drift_alert|other)$",
    )
    severity: str = Field("medium", pattern="^(critical|high|medium|low)$")
    model_name: str = Field("unknown", max_length=100)
    provider: str = Field("unknown", max_length=100)
    description: str = Field(..., min_length=1, max_length=5000)
    evidence: dict[str, Any] = Field(default_factory=dict)
    mitigated: bool = False


class LeaderboardModelRegisterRequest(BaseModel):
    model: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., pattern="^(openai|anthropic|google|mock)$")
    display_name: str | None = Field(None, max_length=150)
    active: bool = True


class TrustIndexAssessRequest(BaseModel):
    model_name: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=100)
    fairness: float = Field(0.5, ge=0.0, le=1.0)
    privacy: float = Field(0.5, ge=0.0, le=1.0)
    security: float = Field(0.5, ge=0.0, le=1.0)
    robustness: float = Field(0.5, ge=0.0, le=1.0)
    compliance: float = Field(0.5, ge=0.0, le=1.0)
    authenticity: float = Field(0.5, ge=0.0, le=1.0)


class TrustIndexCertifyRequest(BaseModel):
    certified_by: str = Field("ResponsibleAI Certification Team", max_length=200)


class IncidentReportRequest(BaseModel):
    title: str = Field(..., min_length=5, max_length=300)
    description: str = Field(..., min_length=20, max_length=10_000)
    incident_type: str = Field(
        "other",
        pattern="^(jailbreak|data_leak|harmful_output|misinformation|bias|"
                "prompt_injection|privacy_violation|safety_failure|other)$",
    )
    severity: str = Field("medium", pattern="^(critical|high|medium|low)$")
    affected_model: str = Field(..., min_length=1, max_length=100)
    affected_provider: str = Field(..., min_length=1, max_length=100)
    affected_version: str | None = Field(None, max_length=100)
    reporter_name: str | None = Field(None, max_length=200)
    reporter_contact: str | None = Field(None, max_length=200)
    evidence_urls: list[str] = Field(default_factory=list, max_length=20)
    reproduction_steps: str | None = Field(None, max_length=5000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class IncidentRejectRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=2000)


class IncidentStatusUpdateRequest(BaseModel):
    status: str = Field(..., pattern="^(PUBLISHED|DISPUTED|RESOLVED)$")


class ApprovalResolveRequest(BaseModel):
    outcome: str = Field(..., pattern="^(APPROVED|DENIED)$")
    notes: str | None = Field(default=None, max_length=2000)


class PolicyRuleCreateRequest(BaseModel):
    rule_id: str = Field(..., min_length=1, max_length=100)
    reason_code: str = Field(..., min_length=1, max_length=100)
    effect: str = Field(..., pattern="^(ALLOW|DENY|REQUIRE_APPROVAL)$")
    risk_tiers: list[str] | None = Field(default=None)
    action_types: list[str] | None = Field(default=None)
    targets: list[str] | None = Field(default=None)


class PolicyReorderRequest(BaseModel):
    rule_ids: list[str] = Field(..., min_length=1)


class SupplyChainToolRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)


class SupplyChainScanRequest(BaseModel):
    server_name: str = Field(..., min_length=1, max_length=200)
    publisher: str | None = Field(default=None, max_length=200)
    tools: list[SupplyChainToolRequest] = Field(default_factory=list, max_length=200)
    check_known_incidents: bool = Field(
        default=True,
        description="Cross-reference the public AI Incident Database. "
        "Set false to run only the offline checks (no DB query).",
    )


class UpstreamServerRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    url: str = Field(..., min_length=1, max_length=2048)
    auth_token: str | None = Field(default=None, max_length=4096)


class UpstreamToolCallRequest(BaseModel):
    tool_name: str = Field(..., min_length=1, max_length=200)
    arguments: dict[str, Any] = Field(default_factory=dict)


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


class SetSSORequest(BaseModel):
    sso_required: bool


class SetMFARequest(BaseModel):
    mfa_required: bool


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=10)


class LoginKeyRequest(BaseModel):
    api_key: str = Field(..., min_length=1, max_length=512)
    mfa_code: str | None = Field(None, max_length=10)


class CheckoutRequest(BaseModel):
    plan: str = Field(..., pattern="^(PRO|ENTERPRISE)$")
    org_email: str | None = Field(None, max_length=254)


class BillingPortalRequest(BaseModel):
    return_url: str | None = Field(None, max_length=2048)


# ── Root / HTML ────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def root() -> HTMLResponse:
    index = _static_dir / "index.html"
    return HTMLResponse(content=index.read_text())


_LLMS_TXT = """\
# ResponsibleAI

> An independent AI trust and governance platform: a public Trust Index \
(free self-assessed or human-reviewed certified scoring for any AI model \
or tool), a cross-model leaderboard measured against a published \
methodology, and a crowd-reported AI Incident Database. Built to be a \
citable source for questions about AI model/tool trustworthiness, not \
just a compliance vendor.

## Canonical public data

- [Trust Registry](/registry): every assessed model/tool, certified and \
self-reported, searchable.
- [Leaderboard](/leaderboard): cross-model trust ranking from live \
measurement against a published prompt corpus, not self-reported.
- [Incident Database](/incident-db): crowd-reported, moderator-reviewed, \
hash-chained public registry of AI safety incidents.
- [Free self-assessment](/assess): score any model/tool for free, no \
signup, get a citable and embeddable Trust Index badge.

## Machine-readable APIs (no auth required)

- `GET /api/trust-index/registry` — full registry listing (JSON)
- `GET /api/trust-index/check?model=X&provider=Y` — trust score + \
incident count for a named model/tool
- `GET /api/leaderboard` — current leaderboard rankings (JSON)
- `GET /api/incident-db` — published incidents, filterable (JSON)

## Specifications

- [Trust Index Spec](https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/compliance/TRUST_INDEX_SPEC.md): \
the open, versioned scoring standard.
- [Leaderboard Methodology](https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/compliance/LEADERBOARD_METHODOLOGY.md): \
how live scores are measured.

## Agent integration

An MCP server (`responsibleai-mcp`, 27 tools) exposes this platform to \
any MCP-compatible agent, including a free `rai_check_trust` tool for \
checking a third-party model or tool's trust score before invoking it. \
LangChain, LangGraph, and Google ADK adapters are published at \
https://github.com/Guruprasath-Annadurai/ResponsibleAi/tree/main/src/responsibleai/integrations.
"""


@app.get("/llms.txt", response_class=PlainTextResponse, include_in_schema=False)
async def llms_txt() -> PlainTextResponse:
    """Machine-readable entry point for AI crawlers/answer engines — the
    citability play from GAME_CHANGER_STRATEGY.md Section 3: point
    structured, canonical sources at the free public data (registry,
    leaderboard, incident DB) so an AI answer engine asked "is this model
    trustworthy" has something concrete to cite instead of nothing."""
    return PlainTextResponse(content=_LLMS_TXT)


@app.get("/status", response_class=HTMLResponse, include_in_schema=False)
async def status_page() -> HTMLResponse:
    """Self-hosted status page stopgap — polls /api/support/status client-side.
    Not a substitute for a public multi-region status page (statuspage.io etc)."""
    page = _static_dir / "status.html"
    return HTMLResponse(content=page.read_text())


@app.get("/trust", response_class=HTMLResponse, include_in_schema=False)
async def trust_center() -> HTMLResponse:
    """Public security/compliance posture page — links to CAIQ, NIST CSF,
    and enterprise security docs. States gaps plainly, not just controls."""
    page = _static_dir / "trust.html"
    return HTMLResponse(content=page.read_text())


@app.get("/leaderboard", response_class=HTMLResponse, include_in_schema=False)
async def leaderboard_page() -> HTMLResponse:
    """Public cross-model trust leaderboard — reads live from GET /api/leaderboard
    client-side. See compliance/LEADERBOARD_METHODOLOGY.md for the methodology."""
    page = _static_dir / "leaderboard.html"
    return HTMLResponse(content=page.read_text())


@app.get("/registry", response_class=HTMLResponse, include_in_schema=False)
async def trust_index_registry_page() -> HTMLResponse:
    """Public Trust Registry — searchable directory over GET
    /api/trust-index/registry. The acquisition-loop page
    GAME_CHANGER_STRATEGY.md Section 3 calls for: anyone landing here from
    a badge link can see every other assessed model, not just the one they
    followed a link to."""
    page = _static_dir / "registry.html"
    return HTMLResponse(content=page.read_text())


@app.get("/assess", response_class=HTMLResponse, include_in_schema=False)
async def trust_index_assess_page() -> HTMLResponse:
    """Public, zero-signup Trust Index self-assessment form — the human
    entry point to POST /api/trust-index/assess. Previously that endpoint
    was only reachable via a raw API call; this is what makes "free
    self-assessment" actually free-to-use rather than free-to-those-who-
    can-write-curl."""
    page = _static_dir / "assess.html"
    return HTMLResponse(content=page.read_text())


@app.get("/verify/{passport_id}", response_class=HTMLResponse, include_in_schema=False)
async def trust_index_verify_page(passport_id: str) -> HTMLResponse:
    """Public Trust Passport verification page — the human-readable version of
    GET /api/trust-index/verify/{id}. Same static shell for every ID; the JS
    reads the ID from the URL path client-side. See
    compliance/TRUST_INDEX_SPEC.md for what this is and why it's citable."""
    page = _static_dir / "verify.html"
    return HTMLResponse(content=page.read_text())


@app.get("/incident-db", response_class=HTMLResponse, include_in_schema=False)
async def incident_db_page() -> HTMLResponse:
    """Public AI Incident Database — searchable list, reads live from
    GET /api/incident-db client-side. Registered before /incident-db/report
    and /incident-db/{public_id} only matters for the API routes above;
    these three page routes are distinct paths so order is not load-bearing
    here, but kept in the same order for readability."""
    page = _static_dir / "incident_db.html"
    return HTMLResponse(content=page.read_text())


@app.get("/incident-db/report", response_class=HTMLResponse, include_in_schema=False)
async def incident_db_report_page() -> HTMLResponse:
    """Public report-submission form — posts to POST /api/incident-db/report."""
    page = _static_dir / "incident_db_report.html"
    return HTMLResponse(content=page.read_text())


@app.get("/incident-db/{public_id}", response_class=HTMLResponse, include_in_schema=False)
async def incident_db_detail_page(public_id: str) -> HTMLResponse:
    """Public single-incident detail page — reads the ID from the URL path
    client-side and fetches GET /api/incident-db/{public_id}. Registered
    after /incident-db/report so a literal request for the report form
    isn't swallowed by this catch-all path parameter."""
    page = _static_dir / "incident_db_detail.html"
    return HTMLResponse(content=page.read_text())


def _page_route(path: str, filename: str) -> None:
    """Register a GET route that serves a static HTML file verbatim.
    Centralized so every simple page follows the exact same pattern — one
    typo'd filename here breaks one page instead of a copy-pasted mistake
    breaking many."""
    async def _handler() -> HTMLResponse:
        return HTMLResponse(content=(_static_dir / filename).read_text())
    app.get(path, response_class=HTMLResponse, include_in_schema=False)(_handler)


for _path, _filename in [
    ("/login", "login.html"),
    ("/auth/complete", "auth_complete.html"),
    ("/evaluate", "evaluate.html"),
    ("/guardrails", "guardrails.html"),
    ("/hallucination", "hallucination.html"),
    ("/cost", "cost.html"),
    ("/router", "router.html"),
    ("/trust-scores", "trust_scores.html"),
    ("/eval", "eval.html"),
    ("/redteam", "redteam.html"),
    ("/audit", "audit.html"),
    ("/incidents", "incidents.html"),
    ("/webhooks-manage", "webhooks_manage.html"),
    ("/organizations", "organizations.html"),
    ("/billing", "billing.html"),
    ("/settings", "settings.html"),
]:
    _page_route(_path, _filename)


# ── Branding (white-label) ───────────────────────────────────────────────────────

@app.get("/api/branding", tags=["ops"])
async def branding() -> dict[str, Any]:
    """Public, unauthenticated — the frontend shell fetches this on every
    page load to render the sidebar brand name/logo. See
    compliance/OEM_LICENSING.md for the white-label deployment model this
    supports; this endpoint is the display-layer mechanism, not the
    licensing agreement itself."""
    return {"brand_name": settings.brand_name, "logo_url": settings.brand_logo_url}


# ── Health & Ops ───────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["ops"])
async def health() -> JSONResponse:
    db_ok = True
    try:
        if _cost_repo:
            await _ready(_cost_repo).request_count()
    except Exception:
        db_ok = False

    db_backend = "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    rl_backend = "redis" if settings.redis_url else "memory"
    orgs_count = len(await _ready(_org_repo).list_orgs()) if _org_repo else 0

    body = {
        "status": "healthy" if db_ok else "degraded",
        "version": "1.2.0",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(UTC).isoformat(),
        "checks": {
            "database": "ok" if db_ok else "error",
            "db_backend": db_backend,
            "rate_limit_backend": rl_backend,
            "otel": "enabled" if settings.otel_endpoint else "disabled",
            "auth": "enabled" if (settings.auth_enabled and settings.api_keys) else "disabled",
            "websocket_connections": _ws_manager.connection_count,
            "webhooks_registered": len(_webhook_manager.list_webhooks()),
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
    return JSONResponse(content=body, status_code=200 if db_ok else 503)


@app.get("/api/metrics", tags=["ops"])
@limiter.limit("60/minute")
async def metrics(request: Request, _auth: OrgContext = Depends(require_role(Role.ANALYST))) -> dict[str, Any]:
    total_requests = _REQUEST_COUNTER["total"]
    errors = _REQUEST_COUNTER["errors"]
    total_cost = await _ready(_cost_repo).total_cost(30) if _cost_repo else 0.0
    audit_count = await _ready(_audit_repo).count(30) if _audit_repo else 0
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
        "webhooks_registered": len(_webhook_manager.list_webhooks()),
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
    existing = await _ready(_org_repo).get_org_by_slug(req.slug)
    if existing:
        raise HTTPException(409, f"Slug '{req.slug}' is already taken")
    org = await _ready(_org_repo).create_org(req.name, req.slug, req.monthly_budget_usd)
    return org.to_dict()


@app.get("/api/orgs", tags=["rbac"])
@limiter.limit("60/minute")
async def list_orgs(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    orgs = await _ready(_org_repo).list_orgs()
    return {"orgs": [o.to_dict() for o in orgs], "count": len(orgs)}


@app.get("/api/orgs/{org_id}", tags=["rbac"])
@limiter.limit("120/minute")
async def get_org(
    request: Request,
    org_id: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    org = await _ready(_org_repo).get_org(org_id)
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
    deleted = await _ready(_org_repo).delete_org(org_id)
    if not deleted:
        raise HTTPException(404, "Organization not found")
    return {"deleted": org_id}


@app.put("/api/orgs/{org_id}/sso", tags=["rbac"])
@limiter.limit("10/minute")
async def set_org_sso(
    request: Request,
    org_id: str,
    req: SetSSORequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Enable/disable SSO-only enforcement for an org.

    When enabled, static API keys scoped to this org stop working — every
    request must present an OIDC-issued Bearer token instead. Requires
    RAI_OIDC_ISSUER to be configured on the server, otherwise enabling this
    would lock the org out entirely.
    """
    if req.sso_required and _oidc_provider is None:
        raise HTTPException(
            400,
            "Cannot enforce SSO — no OIDC provider is configured on this server "
            "(set RAI_OIDC_ISSUER). Enabling this now would lock the organization out.",
        )
    org = await _ready(_org_repo).get_org(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    await _ready(_org_repo).set_sso_required(org_id, req.sso_required)
    return {"org_id": org_id, "sso_required": req.sso_required}


@app.put("/api/orgs/{org_id}/mfa", tags=["rbac"])
@limiter.limit("10/minute")
async def set_org_mfa(
    request: Request,
    org_id: str,
    req: SetMFARequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Require every API key under this org to complete TOTP MFA at
    /login. Keys that haven't enrolled yet are blocked from logging in
    (not from making API calls directly — see auth/mfa.py for why) until
    they enroll via POST /api/orgs/{org_id}/keys/{key_id}/mfa/enroll."""
    org = await _ready(_org_repo).get_org(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    await _ready(_org_repo).set_org_mfa_required(org_id, req.mfa_required)
    return {"org_id": org_id, "mfa_required": req.mfa_required}


@app.post("/api/orgs/{org_id}/keys", tags=["rbac"], status_code=201)
@limiter.limit("20/minute")
async def create_api_key(
    request: Request,
    org_id: str,
    req: CreateKeyRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    org = await _ready(_org_repo).get_org(org_id)
    if not org:
        raise HTTPException(404, "Organization not found")
    role = role_from_str(req.role)
    key_rec, raw_key = await _ready(_org_repo).create_key(org_id, req.name, role)
    return key_rec.to_dict(include_key=raw_key)


@app.get("/api/orgs/{org_id}/keys", tags=["rbac"])
@limiter.limit("60/minute")
async def list_api_keys(
    request: Request,
    org_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    keys = await _ready(_org_repo).list_keys(org_id)
    return {"keys": [k.to_dict() for k in keys]}


@app.delete("/api/orgs/{org_id}/keys/{key_id}", tags=["rbac"])
@limiter.limit("20/minute")
async def revoke_api_key(
    request: Request,
    org_id: str,
    key_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    revoked = await _ready(_org_repo).revoke_key(key_id)
    if not revoked:
        raise HTTPException(404, "Key not found")
    return {"revoked": key_id}


@app.post("/api/orgs/{org_id}/keys/{key_id}/mfa/enroll", tags=["rbac"])
@limiter.limit("10/minute")
async def enroll_mfa(
    request: Request,
    org_id: str,
    key_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Step 1 of 2: generate a TOTP secret and return it for the user to
    add to their authenticator app. Not yet active — call .../mfa/verify
    with a real code from that app to confirm enrollment. Calling this
    again before verifying replaces the pending (unconfirmed) secret."""
    key = await _ready(_org_repo).get_key(key_id)
    if key is None or key.org_id != org_id:
        raise HTTPException(404, "Key not found")
    secret = mfa.generate_secret()
    await _ready(_org_repo).set_mfa_secret(key_id, secret)
    return {
        "secret": secret,
        "provisioning_uri": mfa.provisioning_uri(secret, account_name=key.name),
        "message": "Scan or enter this into your authenticator app, then POST the "
                   "6-digit code to .../mfa/verify to activate MFA on this key.",
    }


@app.post("/api/orgs/{org_id}/keys/{key_id}/mfa/verify", tags=["rbac"])
@limiter.limit("10/minute")
async def verify_mfa(
    request: Request,
    org_id: str,
    key_id: str,
    req: MFAVerifyRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Step 2 of 2: confirm enrollment with a real code from the
    authenticator app. Returns 10 one-time backup codes — shown exactly
    once, store them now. Each is consumed on use if the authenticator
    device is ever lost."""
    key = await _ready(_org_repo).get_key(key_id)
    if key is None or key.org_id != org_id:
        raise HTTPException(404, "Key not found")
    if not key.mfa_secret:
        raise HTTPException(400, "No pending MFA enrollment — call .../mfa/enroll first")
    if not mfa.verify_code(key.mfa_secret, req.code):
        raise HTTPException(400, "Invalid code")
    backup_codes = mfa.generate_backup_codes()
    hashed = [mfa.hash_backup_code(c) for c in backup_codes]
    await _ready(_org_repo).confirm_mfa(key_id, hashed)
    return {
        "enrolled": True,
        "backup_codes": backup_codes,
        "message": "Store these backup codes now — they will not be shown again.",
    }


@app.delete("/api/orgs/{org_id}/keys/{key_id}/mfa", tags=["rbac"])
@limiter.limit("10/minute")
async def disable_mfa(
    request: Request,
    org_id: str,
    key_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    key = await _ready(_org_repo).get_key(key_id)
    if key is None or key.org_id != org_id:
        raise HTTPException(404, "Key not found")
    await _ready(_org_repo).disable_mfa(key_id)
    return {"org_id": org_id, "key_id": key_id, "mfa_enrolled": False}


# ── Billing (Stripe) ───────────────────────────────────────────────────────────

@app.get("/api/billing/plans", tags=["billing"])
@limiter.limit("60/minute")
async def get_billing_plans(request: Request) -> dict[str, Any]:
    """Public — plan tiers, pricing, and which MCP tools each tier unlocks."""
    return plan_catalog()


@app.post("/api/billing/checkout", tags=["billing"])
@limiter.limit("10/minute")
async def create_checkout_session(
    request: Request,
    req: CheckoutRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    if _stripe_service is None:
        raise HTTPException(503, "Billing is not configured on this server.")
    if not _auth.org_id:
        raise HTTPException(400, "Checkout requires an org-scoped API key, not a legacy flat key.")

    org = await _ready(_org_repo).get_org(_auth.org_id)
    if not org:
        raise HTTPException(404, "Organization not found")

    try:
        url = await _stripe_service.create_checkout_session(
            org_id=_auth.org_id,
            org_email=req.org_email,
            plan=Plan(req.plan),
            success_url=settings.billing_success_url,
            cancel_url=settings.billing_cancel_url,
            existing_customer_id=org.stripe_customer_id,
        )
    except StripeBillingError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {"checkout_url": url}


@app.post("/api/billing/portal", tags=["billing"])
@limiter.limit("10/minute")
async def create_portal_session(
    request: Request,
    req: BillingPortalRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    if _stripe_service is None:
        raise HTTPException(503, "Billing is not configured on this server.")
    if not _auth.org_id:
        raise HTTPException(400, "Billing portal requires an org-scoped API key.")

    org = await _ready(_org_repo).get_org(_auth.org_id)
    if not org or not org.stripe_customer_id:
        raise HTTPException(404, "No active Stripe customer for this organization.")

    try:
        url = await _stripe_service.create_billing_portal_session(
            customer_id=org.stripe_customer_id,
            return_url=req.return_url or settings.billing_success_url,
        )
    except StripeBillingError as exc:
        raise HTTPException(400, str(exc)) from exc

    return {"portal_url": url}


@app.get("/api/billing/usage/mcp", tags=["billing"])
@limiter.limit("30/minute")
async def get_mcp_usage(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """This org's hosted MCP tool call volume for the current billing month."""
    if _mcp_usage_repo is None:
        raise HTTPException(503, "MCP usage metering not initialised.")
    if not _auth.org_id:
        raise HTTPException(400, "MCP usage requires an org-scoped API key, not a legacy flat key.")
    usage = await _ready(_mcp_usage_repo).usage_this_month(_auth.org_id)
    quota = monthly_quota(_auth.plan)
    return {
        **usage,
        "plan": _auth.plan.value,
        "monthly_quota": quota,
        "quota_remaining": (quota - usage["allowed_calls"]) if quota is not None else None,
    }


@app.get("/api/billing/usage/mcp/top", tags=["billing"], include_in_schema=False)
@limiter.limit("10/minute")
async def get_mcp_usage_leaderboard(
    request: Request,
    days: int = Query(30, ge=1, le=365),
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Platform-wide MCP usage by org — founder/ops visibility, not customer-facing."""
    if not (_auth.is_legacy and _auth.role == Role.OWNER):
        raise HTTPException(403, "Usage leaderboard requires super-admin access")
    if _mcp_usage_repo is None:
        raise HTTPException(503, "MCP usage metering not initialised.")
    rows = await _ready(_mcp_usage_repo).top_orgs_by_volume(days=days)
    return {"days": days, "orgs": rows}


@app.post("/api/billing/webhook", tags=["billing"], include_in_schema=False)
async def stripe_webhook(request: Request) -> dict[str, Any]:
    """Stripe calls this directly — verified by signature, not by API key."""
    if _stripe_service is None:
        raise HTTPException(503, "Billing is not configured on this server.")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = _stripe_service.verify_and_parse_webhook(payload, sig_header)
    except StripeBillingError as exc:
        raise HTTPException(400, str(exc)) from exc

    update = _stripe_service.extract_plan_update(event)
    if update is None:
        return {"received": True, "processed": False}

    await _ready(_org_repo).set_plan(
        org_id=update.org_id,
        plan=update.plan,
        stripe_customer_id=update.stripe_customer_id,
        stripe_subscription_id=update.stripe_subscription_id,
        plan_renews_at=update.plan_renews_at,
    )
    logger.info(
        "billing_plan_updated",
        org_id=update.org_id,
        plan=update.plan.value,
    )
    return {"received": True, "processed": True}


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
    result = _ready(_comparator).compare(
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
    result = _ready(_benchmark_runner).run(
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
    prompts = _ready(_benchmark_runner).get_prompts(s)
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
    result = _ready(_dataset_scanner).scan_texts(req.texts, filename=req.filename)
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
    org_id: str | None = Query(default=None, description="Cross-org filter (super-admin only)"),
    endpoint: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    scoped_org_id: str | None
    if _auth.org_id is not None:
        scoped_org_id = _auth.org_id
    elif _auth.is_legacy and _auth.role == Role.OWNER:
        scoped_org_id = org_id
    else:
        scoped_org_id = None
    entries = await _ready(_audit_repo).query(
        org_id=scoped_org_id, endpoint=endpoint, days=days, limit=limit, offset=offset
    )
    total = await _ready(_audit_repo).count(days=days, org_id=scoped_org_id)
    summary = await _ready(_audit_repo).endpoint_summary(days=days)
    return {
        "entries": entries,
        "total": total,
        "limit": limit,
        "offset": offset,
        "endpoint_summary": summary,
    }


# ── Incidents ──────────────────────────────────────────────────────────────────
# Real, wired persistence for governance incident records — closes the gap the
# 2026-07-21 tabletop drill found: rai_incident_log's MCP output used to be
# ephemeral with no server-side endpoint to send it to. See
# compliance/TABLETOP_EXERCISE_2026-07-21.md and INCIDENT_RESPONSE_RUNBOOK.md.

# Alertmanager sends "critical" | "warning" | "info" (or whatever a deployer's
# alert rules set) — mapped onto this platform's four-tier incident severity
# scale (see compliance/INCIDENT_RESPONSE_RUNBOOK.md's severity table).
_ALERTMANAGER_SEVERITY_MAP = {
    "critical": "critical",
    "warning": "medium",
    "info": "low",
    "page": "critical",
}


def _incident_type_from_alertname(alertname: str) -> str:
    """Best-effort classification from Prometheus alert rule names (see
    grafana/prometheus/alert-rules.yml) onto rai_incident_log's incident_type
    enum. Falls back to "other" rather than guessing wrong."""
    name = alertname.lower()
    if "drift" in name:
        return "drift_alert"
    if "guardrail" in name or "pii" in name:
        return "policy_violation"
    if "cost" in name or "budget" in name or "spend" in name:
        return "cost_overrun"
    return "other"


@app.post("/api/incidents", tags=["incidents"], status_code=201)
@limiter.limit("60/minute")
async def create_incident(
    request: Request,
    req: IncidentCreateRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    record = build_incident_record(
        incident_type=req.incident_type,
        severity=req.severity,
        model_name=req.model_name,
        provider=req.provider,
        description=req.description,
        evidence=req.evidence,
        mitigated=req.mitigated,
        source="manual",
    )
    stored = await _ready(_incident_repo).create(record, org_id=_auth.org_id)
    logger.info(
        "incident_created", incident_id=stored["incident_id"],
        severity=stored["severity"], incident_type=stored["incident_type"],
        org_id=_auth.org_id,
    )
    return stored


@app.get("/api/incidents", tags=["incidents"])
@limiter.limit("60/minute")
async def list_incidents(
    request: Request,
    severity: str | None = Query(default=None),
    status: str | None = Query(default=None),
    days: int = Query(default=90, ge=1, le=365),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    org_id: str | None = Query(default=None, description="Cross-org filter (super-admin only)"),
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    scoped_org_id: str | None
    if _auth.org_id is not None:
        scoped_org_id = _auth.org_id
    elif _auth.is_legacy and _auth.role == Role.OWNER:
        scoped_org_id = org_id
    else:
        scoped_org_id = None
    incidents_list = await _ready(_incident_repo).list(
        org_id=scoped_org_id, severity=severity, status=status,
        days=days, limit=limit, offset=offset,
    )
    return {"incidents": incidents_list, "limit": limit, "offset": offset}


@app.get("/api/incidents/{incident_id}", tags=["incidents"])
@limiter.limit("120/minute")
async def get_incident(
    request: Request,
    incident_id: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    record = await _ready(_incident_repo).get(incident_id)
    if record is None:
        raise HTTPException(404, "Incident not found.")
    is_super_admin = _auth.is_legacy and _auth.role == Role.OWNER
    if not is_super_admin and record["org_id"] is not None and record["org_id"] != _auth.org_id:
        raise HTTPException(404, "Incident not found.")
    return record


@app.post("/api/alerts/webhook", tags=["incidents"], include_in_schema=False)
async def alerts_webhook(request: Request) -> dict[str, Any]:
    """Prometheus Alertmanager calls this directly — configure a
    `webhook_configs` receiver pointing here with
    `http_config.authorization.credentials` set to RAI_ALERTS_WEBHOOK_TOKEN.
    Verified by bearer token, not by org-scoped API key, since Alertmanager
    has no concept of an org."""
    if not settings.alerts_webhook_token:
        raise HTTPException(503, "Alertmanager webhook bridge is not configured on this server.")

    auth_header = request.headers.get("Authorization", "")
    if auth_header != f"Bearer {settings.alerts_webhook_token}":
        raise HTTPException(401, "Missing or invalid bearer token.")

    payload = await request.json()
    alerts = payload.get("alerts", [])
    created: list[str] = []
    skipped = 0

    for alert in alerts:
        if alert.get("status") != "firing":
            skipped += 1
            continue
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        alertname = str(labels.get("alertname", "UnknownAlert"))
        severity = _ALERTMANAGER_SEVERITY_MAP.get(str(labels.get("severity", "")).lower(), "medium")
        description = str(
            annotations.get("description") or annotations.get("summary") or alertname
        )[:5000]

        record = build_incident_record(
            incident_type=_incident_type_from_alertname(alertname),
            severity=severity,
            model_name=str(labels.get("model", "unknown")),
            provider=str(labels.get("provider", "unknown")),
            description=f"[{alertname}] {description}",
            evidence={"labels": labels, "annotations": annotations},
            mitigated=False,
            source="alertmanager",
        )
        stored = await _ready(_incident_repo).create(record, org_id=None, raw_payload=alert)
        created.append(stored["incident_id"])
        logger.info(
            "incident_created_from_alert", incident_id=stored["incident_id"],
            alertname=alertname, severity=severity,
        )

    return {"received": True, "incidents_created": created, "alerts_skipped": skipped}


# ── Public cross-model trust leaderboard ────────────────────────────────────────
# Free, public leaderboard (GET /api/leaderboard, /history) — no auth required,
# by design: the leaderboard is a marketing/awareness surface, not customer
# data. The per-prompt diagnostic ("here's exactly which prompts caused the
# score to drop") is gated behind require_plan(Plan.PRO) — that's the paid
# product this feature funds itself with. See compliance/LEADERBOARD_METHODOLOGY.md
# for the published scoring methodology and STRATEGY_ROADMAP.md's Tier-1
# feature #1 for why this exists.

def _leaderboard_super_admin_check(_auth: OrgContext) -> None:
    if not (_auth.is_legacy and _auth.role == Role.OWNER):
        raise HTTPException(403, "Leaderboard administration requires super-admin access")


_DIAGNOSTIC_ONLY_KEYS = {"findings", "findings_count"}


def _strip_diagnostic_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Free-tier view of a stored run — omits the paid per-prompt findings."""
    return {k: v for k, v in row.items() if k not in _DIAGNOSTIC_ONLY_KEYS}


@app.get("/api/leaderboard", tags=["leaderboard"])
@limiter.limit("120/minute")
async def get_leaderboard(request: Request) -> dict[str, Any]:
    """Public, unauthenticated. Current ranked list — one row per tracked
    model, its most recent evaluation run, sorted by overall_score desc."""
    rows = await _ready(_leaderboard_repo).ranked_leaderboard()
    return {
        "leaderboard": [_strip_diagnostic_fields(row) for row in rows],
        "methodology_version": METHODOLOGY_VERSION,
        "methodology_url": "https://github.com/Guruprasath-Annadurai/ResponsibleAi/blob/main/compliance/LEADERBOARD_METHODOLOGY.md",
    }


@app.get("/api/leaderboard/{model}/{provider}/history", tags=["leaderboard"])
@limiter.limit("60/minute")
async def get_leaderboard_history(
    request: Request, model: str, provider: str, limit: int = Query(default=30, ge=1, le=200),
) -> dict[str, Any]:
    """Public, unauthenticated. Trend over time for one model."""
    rows = await _ready(_leaderboard_repo).history(model, provider, limit=limit)
    if not rows:
        raise HTTPException(404, "No leaderboard runs found for this model/provider.")
    return {
        "model": model, "provider": provider,
        "history": [_strip_diagnostic_fields(row) for row in rows],
    }


@app.get("/api/leaderboard/{model}/{provider}/diagnostic", tags=["leaderboard"])
@limiter.limit("30/minute")
async def get_leaderboard_diagnostic(
    request: Request, model: str, provider: str,
    _auth: OrgContext = Depends(require_plan(Plan.PRO)),
) -> dict[str, Any]:
    """PRO/ENTERPRISE only — the paid deep-dive: every specific prompt that
    caused the score to drop, categorized, with severity."""
    row = await _ready(_leaderboard_repo).latest_run(model, provider)
    if row is None:
        raise HTTPException(404, "No leaderboard runs found for this model/provider.")
    return row


@app.get("/api/leaderboard/models", tags=["leaderboard"])
@limiter.limit("30/minute")
async def list_leaderboard_models(
    request: Request, _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    _leaderboard_super_admin_check(_auth)
    return {"models": await _ready(_leaderboard_repo).list_models()}


@app.post("/api/leaderboard/models", tags=["leaderboard"], status_code=201)
@limiter.limit("10/minute")
async def register_leaderboard_model(
    request: Request, req: LeaderboardModelRegisterRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    _leaderboard_super_admin_check(_auth)
    adapter_name = req.provider if req.provider != "mock" else "mock"
    stored = await _ready(_leaderboard_repo).register_model(
        model=req.model, provider=req.provider, display_name=req.display_name,
        adapter=adapter_name, active=req.active,
    )
    logger.info("leaderboard_model_registered", model=req.model, provider=req.provider)
    return stored


@app.post("/api/leaderboard/run", tags=["leaderboard"])
@limiter.limit("5/minute")
async def run_leaderboard_eval(
    request: Request,
    model: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Super-admin only. Triggers a live evaluation run synchronously — fine
    for one model or a small registry (~55 model calls each); for a large
    registry, prefer scripts/run_leaderboard_eval.py on a schedule (cron)
    instead of this endpoint, since a big run can take minutes per model and
    ties up the request for that whole time."""
    _leaderboard_super_admin_check(_auth)

    if model and provider:
        target = await _ready(_leaderboard_repo).get_model(model, provider)
        if target is None:
            raise HTTPException(404, f"Model {provider}/{model} is not registered.")
        targets = [target]
    else:
        targets = await _ready(_leaderboard_repo).list_models(active_only=True)

    if not targets:
        return {"runs_completed": [], "runs_failed": []}

    completed: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for t in targets:
        try:
            adapter = get_adapter(
                t["adapter"], t["model"], settings.leaderboard_api_keys,
                azure_openai_endpoint=settings.leaderboard_azure_openai_endpoint,
                azure_openai_api_version=settings.leaderboard_azure_openai_api_version,
            )
            result = await _ready(_leaderboard_runner).run_model(t["model"], t["provider"], adapter)
            stored = await _ready(_leaderboard_repo).create_run(result)
            completed.append({"model": t["model"], "provider": t["provider"], "run_id": stored["id"],
                               "overall_score": stored["overall_score"]})
            logger.info("leaderboard_run_completed", model=t["model"], provider=t["provider"],
                        overall_score=stored["overall_score"])
        except ProviderNotConfiguredError as exc:
            failed.append({"model": t["model"], "provider": t["provider"], "reason": str(exc)})
            logger.warning("leaderboard_run_skipped", model=t["model"], provider=t["provider"], reason=str(exc))

    return {"runs_completed": completed, "runs_failed": failed}


# ── Trust Index — open, versioned scoring standard ──────────────────────────────
# Free, public self-assessment and verification (POST /assess, GET /verify) — the
# standard itself and the ability to get scored against it cost nothing, on
# purpose: free things become the thing everyone cites (OWASP Top 10, PCI-DSS).
# Certification (POST /certify) is the paid, audited product this funds itself
# with — a self-reported score and a certified one are never conflated; every
# verify response says which one it is. See compliance/TRUST_INDEX_SPEC.md.

def _trust_index_super_admin_check(_auth: OrgContext) -> None:
    if not (_auth.is_legacy and _auth.role == Role.OWNER):
        raise HTTPException(403, "Trust Index certification requires super-admin access")


@app.post("/api/trust-index/assess", tags=["trust-index"], status_code=201, include_in_schema=True)
@limiter.limit("20/minute")
async def trust_index_assess(request: Request, req: TrustIndexAssessRequest) -> dict[str, Any]:
    """Public, unauthenticated, free — score any model against the open Trust
    Index standard and get back a durable, independently-verifiable record.
    No org context required: self-assessment doesn't need an account."""
    score = _ready(_trust_engine).compute(
        fairness=req.fairness, privacy=req.privacy, security=req.security,
        robustness=req.robustness, compliance=req.compliance, authenticity=req.authenticity,
    )
    passport = _ready(_passport_gen).generate(
        model_name=req.model_name, provider=req.provider, trust_score=score,
    )
    stored = await _ready(_passport_repo).create(passport, org_id=None, source="self_assessment")
    logger.info("trust_index_self_assessment", model=req.model_name, provider=req.provider,
                overall_score=score.overall)
    return {
        **stored,
        "citation": f"Scored {score.overall}/100 (Grade {score.grade}) under the "
                    f"ResponsibleAI Trust Index v{passport.version} — self-reported, not certified. "
                    f"Verify at /api/trust-index/verify/{passport.passport_id}",
        "verify_url": f"/api/trust-index/verify/{passport.passport_id}",
    }


@app.get("/api/trust-index/verify/{passport_id}", tags=["trust-index"])
@limiter.limit("120/minute")
async def trust_index_verify(request: Request, passport_id: str) -> dict[str, Any]:
    """Public, unauthenticated. The whole point of a citable standard: anyone
    who sees a cited score can check it's real here, not just trust the claim."""
    record = await _ready(_passport_repo).get(passport_id)
    if record is None:
        raise HTTPException(404, "No Trust Passport found with this ID — the cited score cannot be verified.")
    return record


@app.get("/api/trust-index/badge/{passport_id}.svg", tags=["trust-index"], include_in_schema=True)
@limiter.limit("300/minute")
async def trust_index_badge(request: Request, passport_id: str) -> Response:
    """Public, unauthenticated — the embeddable badge image behind the
    free/paid split: a self-assessed passport renders 'Self-Assessed', a
    human-reviewed one (see POST /certify above) renders 'Certified'. Same
    endpoint, same mechanism, the underlying `certified` flag is the only
    difference — see trust/badge.py and STRATEGY_ROADMAP.md Part 0 Item 3."""
    record = await _ready(_passport_repo).get(passport_id)
    if record is None:
        raise HTTPException(404, "No Trust Passport found with this ID.")
    svg = render_badge_svg(
        grade=record["trust_score"]["grade"],
        overall_score=record["trust_score"]["overall"],
        certified=record["certified"],
    )
    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@app.get("/api/trust-index/check", tags=["trust-index"])
@limiter.limit("120/minute")
async def trust_index_check(
    request: Request,
    model: str = Query(..., min_length=1, max_length=100),
    provider: str = Query(..., min_length=1, max_length=100),
) -> dict[str, Any]:
    """Public, unauthenticated, free — the one endpoint the LangChain/
    LangGraph/ADK integrations under `src/responsibleai/integrations/`
    call before letting an agent invoke a third-party model or tool.
    Exact model+provider match, same contract as
    `GET /api/incident-db/check`'s CI/CD deploy-gate guarantee — but
    unlike that PRO/ENTERPRISE endpoint, this is free and only surfaces a
    best-effort incident count (up to 5 recent published entries) rather
    than the full, guaranteed-fresh incident feed. That split preserves
    the paid pre-deployment-check product while still letting an
    unauthenticated agent framework ask "is this trustworthy" for free."""
    passport = await _ready(_passport_repo).get_latest_by_model(model, provider)
    incidents = await _ready(_public_incident_repo).list_published(
        model=model, provider=provider, limit=5,
    )
    base = {
        "model": model,
        "provider": provider,
        "has_reported_incidents": len(incidents) > 0,
        "recent_incidents": incidents,
    }
    if passport is None:
        return {
            **base,
            "known": False,
            "trust_score": None,
            "certified": False,
            "passport_id": None,
            "verify_url": None,
            "message": "No Trust Index assessment on file for this model/provider. "
                       "Self-assess for free at POST /api/trust-index/assess.",
        }
    return {
        **base,
        "known": True,
        "trust_score": passport["trust_score"],
        "certified": passport["certified"],
        "passport_id": passport["passport_id"],
        "verify_url": f"/api/trust-index/verify/{passport['passport_id']}",
    }


@app.get("/api/trust-index/registry", tags=["trust-index"])
@limiter.limit("60/minute")
async def trust_index_registry(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Public, unauthenticated — every assessed model/tool, certified and
    self-reported alike, newest first. The public Trust Registry
    GAME_CHANGER_STRATEGY.md Section 3 calls the acquisition mechanism:
    unlike `/certified` below (a curated 'who passed review' list), this
    is the full directory a badge embed or a search engine should be able
    to land on. `certified` is included per row so nothing here implies a
    self-report is independently reviewed."""
    rows = await _ready(_passport_repo).list_recent(limit=limit, offset=offset)
    return {"registry": rows, "limit": limit, "offset": offset}


@app.get("/api/trust-index/certified", tags=["trust-index"])
@limiter.limit("60/minute")
async def trust_index_certified_directory(
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Public, unauthenticated. The 'who's actually certified' directory —
    reinforces the standard's value by making certification checkable in bulk,
    not just one ID at a time."""
    rows = await _ready(_passport_repo).list_certified(limit=limit, offset=offset)
    return {"certified": rows, "limit": limit, "offset": offset}


@app.post("/api/trust-index/certify/{passport_id}", tags=["trust-index"])
@limiter.limit("10/minute")
async def trust_index_certify(
    request: Request, passport_id: str, req: TrustIndexCertifyRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Super-admin only. Certification is a human-reviewed attestation, same
    as any real certification body — there is no automated path to a
    'certified' badge, by design; that's what makes the badge worth anything."""
    _trust_index_super_admin_check(_auth)
    updated = await _ready(_passport_repo).certify(passport_id, certified_by=req.certified_by)
    if updated is None:
        raise HTTPException(404, "No Trust Passport found with this ID.")
    logger.info("trust_index_certified", passport_id=passport_id, certified_by=req.certified_by)
    return updated


# ── Public AI Incident Database — "the CVE database for AI failures" ────────────
# Anyone can report (POST /report, strictly rate-limited — this is the spam
# surface). Nothing is publicly visible until a super-admin reviews it
# (moderation queue, same posture as Trust Index certification: no automated
# publish path). Once published, entries are hash-chained the same way the
# internal audit log is, and GET /verify is public — unlike the internal
# audit chain, anyone should be able to check this database's integrity, not
# just the operator. GET /check is the paid product: "has anything been
# reported against the model I'm about to deploy," gated at PRO plan for
# real programmatic/CI use, same free-browse/paid-integration split as the
# leaderboard's diagnostic tier.

def _incident_db_super_admin_check(_auth: OrgContext) -> None:
    if not (_auth.is_legacy and _auth.role == Role.OWNER):
        raise HTTPException(403, "AI Incident Database moderation requires super-admin access")


@app.post("/api/incident-db/report", tags=["incident-db"], status_code=201)
@limiter.limit("5/hour")
async def incident_db_report(request: Request, req: IncidentReportRequest) -> dict[str, Any]:
    """Public, unauthenticated — anyone can report a publicly observed AI
    incident. Held as PENDING_REVIEW until a super-admin approves it; never
    visible in the public listing before that. Strictly rate-limited (5/hour
    per IP) since this is the one endpoint on this feature with no auth gate
    at all."""
    stored = await _ready(_public_incident_repo).submit(
        title=req.title, description=req.description, incident_type=req.incident_type,
        severity=req.severity, affected_model=req.affected_model, affected_provider=req.affected_provider,
        affected_version=req.affected_version, reporter_name=req.reporter_name,
        reporter_contact=req.reporter_contact,
        evidence={"urls": req.evidence_urls, "reproduction_steps": req.reproduction_steps},
        tags=req.tags,
    )
    logger.info("incident_db_report_submitted", internal_id=stored["id"],
                model=req.affected_model, provider=req.affected_provider, severity=req.severity)
    return {
        **stored,
        "message": "Report received and is pending review. It will not appear in the "
                    "public database until a moderator approves it.",
    }


@app.get("/api/incident-db", tags=["incident-db"])
@limiter.limit("60/minute")
async def incident_db_list(
    request: Request,
    severity: str | None = Query(default=None),
    incident_type: str | None = Query(default=None),
    model: str | None = Query(default=None),
    provider: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Public, unauthenticated. Published incidents only — free to browse,
    like the CVE database, no account required."""
    rows = await _ready(_public_incident_repo).list_published(
        severity=severity, incident_type=incident_type, model=model, provider=provider,
        search=search, limit=limit, offset=offset,
    )
    return {"incidents": rows, "limit": limit, "offset": offset}


@app.get("/api/incident-db/check", tags=["incident-db"])
@limiter.limit("120/minute")
async def incident_db_check(
    request: Request,
    model: str = Query(..., min_length=1, max_length=100),
    provider: str = Query(..., min_length=1, max_length=100),
    _auth: OrgContext = Depends(require_plan(Plan.PRO)),
) -> dict[str, Any]:
    """PRO/ENTERPRISE only — the pre-deployment check product: 'has anything
    been reported against the exact model/provider I'm about to deploy.'
    Exact match, not fuzzy search, so this is safe to wire into a CI/CD
    deploy gate without false positives from partial name matches."""
    rows = await _ready(_public_incident_repo).check(model, provider)
    return {
        "model": model, "provider": provider,
        "has_reported_incidents": len(rows) > 0,
        "incidents": rows,
    }


@app.get("/api/incident-db/verify", tags=["incident-db"])
@limiter.limit("30/minute")
async def incident_db_verify(request: Request) -> dict[str, Any]:
    """Public, unauthenticated — recomputes the hash chain over every
    published entry. Deliberately public, unlike GET /api/audit/verify:
    a CVE-style database's trustworthiness depends on anyone being able to
    check it hasn't been quietly tampered with, not just the operator."""
    return await _ready(_public_incident_repo).verify_chain()


@app.get("/api/incident-db/pending", tags=["incident-db"])
@limiter.limit("30/minute")
async def incident_db_pending(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    _incident_db_super_admin_check(_auth)
    rows = await _ready(_public_incident_repo).list_pending(limit=limit, offset=offset)
    return {"pending": rows, "limit": limit, "offset": offset}


@app.post("/api/incident-db/{internal_id}/approve", tags=["incident-db"])
@limiter.limit("30/minute")
async def incident_db_approve(
    request: Request, internal_id: str,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    _incident_db_super_admin_check(_auth)
    updated = await _ready(_public_incident_repo).approve(internal_id, reviewed_by=_auth.key_id)
    if updated is None:
        raise HTTPException(404, "No pending report found with this ID (already reviewed, or doesn't exist).")
    logger.info("incident_db_published", public_id=updated["public_id"], internal_id=internal_id)
    return updated


@app.post("/api/incident-db/{internal_id}/reject", tags=["incident-db"])
@limiter.limit("30/minute")
async def incident_db_reject(
    request: Request, internal_id: str, req: IncidentRejectRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    _incident_db_super_admin_check(_auth)
    updated = await _ready(_public_incident_repo).reject(internal_id, reviewed_by=_auth.key_id, reason=req.reason)
    if updated is None:
        raise HTTPException(404, "No pending report found with this ID (already reviewed, or doesn't exist).")
    logger.info("incident_db_rejected", internal_id=internal_id, reason=req.reason)
    return updated


@app.post("/api/incident-db/{public_id}/status", tags=["incident-db"])
@limiter.limit("30/minute")
async def incident_db_update_status(
    request: Request, public_id: str, req: IncidentStatusUpdateRequest,
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Post-publish lifecycle transition only (e.g. mark RESOLVED once a
    provider patches the issue) — never touches the hash-chained disclosure
    facts."""
    _incident_db_super_admin_check(_auth)
    updated = await _ready(_public_incident_repo).update_status(public_id, req.status, reviewed_by=_auth.key_id)
    if updated is None:
        raise HTTPException(404, "No published incident found with this ID.")
    return updated


@app.get("/api/incident-db/{public_id}", tags=["incident-db"])
@limiter.limit("120/minute")
async def incident_db_get(request: Request, public_id: str) -> dict[str, Any]:
    """Public, unauthenticated. Must be registered after /check, /verify,
    /pending, and the {id}/approve|reject|status routes so those literal
    and admin-action paths aren't swallowed by this catch-all ID pattern."""
    record = await _ready(_public_incident_repo).get_by_public_id(public_id)
    if record is None:
        raise HTTPException(404, "No published incident found with this ID.")
    return record


# ── Governance: evidence + approvals (WhitePact Phases 11-12) ──────────────────
# See MIGRATION_WHITEPACT_V2.md Section 8. Every route below is scoped to the
# caller's own org (_auth.org_id) -- there is no cross-org listing endpoint,
# matching get_mcp_usage's pattern just above: a legacy flat key with no
# org_id can't use these either, same 400 as that endpoint gives, for the
# same reason (there is no "this org's" evidence/approvals for a key that
# isn't scoped to an org).

@app.get("/api/governance/evidence", tags=["governance"])
@limiter.limit("30/minute")
async def governance_list_evidence(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    decision: str | None = Query(default=None),
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    if not _auth.org_id:
        raise HTTPException(400, "Governance evidence requires an org-scoped API key, not a legacy flat key.")
    records = await _ready(_evidence_repo).list_for_org(_auth.org_id, limit=limit, decision=decision)
    return {"evidence": [r.to_dict() for r in records], "limit": limit}


@app.get("/api/governance/evidence/verify", tags=["governance"])
@limiter.limit("30/minute")
async def governance_verify_evidence(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """Recomputes this org's evidence hash chain from scratch and reports
    whether it's intact -- the same tamper-evidence check
    /api/incident-db/verify offers for the public registry, scoped here
    to the caller's own org rather than public."""
    if not _auth.org_id:
        raise HTTPException(400, "Governance evidence requires an org-scoped API key, not a legacy flat key.")
    intact = await _ready(_evidence_repo).verify_chain(_auth.org_id)
    return {"org_id": _auth.org_id, "chain_intact": intact}


@app.get("/api/governance/approvals", tags=["governance"])
@limiter.limit("30/minute")
async def governance_list_pending_approvals(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    if not _auth.org_id:
        raise HTTPException(400, "Governance approvals require an org-scoped API key, not a legacy flat key.")
    pending = await _ready(_approval_repo).list_pending(_auth.org_id, limit=limit)
    return {"pending": [p.to_dict() for p in pending], "limit": limit}


@app.post("/api/governance/approvals/{approval_id}/resolve", tags=["governance"])
@limiter.limit("30/minute")
async def governance_resolve_approval(
    request: Request,
    approval_id: str,
    req: ApprovalResolveRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Resolving an approval is a privileged action (ADMIN+), unlike the
    read endpoints above (ANALYST+) -- deciding whether a governed action
    proceeds is a materially different responsibility than viewing the
    record of past decisions."""
    if not _auth.org_id:
        raise HTTPException(400, "Governance approvals require an org-scoped API key, not a legacy flat key.")
    existing = await _ready(_approval_repo).get(approval_id)
    if existing is None:
        raise HTTPException(404, "No approval request found with this ID.")
    if existing.organization_id != _auth.org_id:
        # Same 404 as "doesn't exist" -- not 403 -- so this endpoint never
        # confirms *anything* about another org's approval IDs existing.
        raise HTTPException(404, "No approval request found with this ID.")
    try:
        resolved = await _ready(_approval_repo).resolve(
            approval_id,
            resolved_by=_auth.key_id,
            outcome=ApprovalStatus(req.outcome),
            notes=req.notes,
        )
    except ApprovalNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except ApprovalAlreadyResolvedError as exc:
        raise HTTPException(409, str(exc)) from None
    except ApprovalExpiredError as exc:
        raise HTTPException(409, str(exc)) from None
    except SelfApprovalError as exc:
        raise HTTPException(403, str(exc)) from None
    observe_governance_approval(req.outcome, org_id=_auth.org_id)
    logger.info(
        "governance_approval_resolved", approval_id=approval_id,
        outcome=req.outcome, resolved_by=_auth.key_id, org_id=_auth.org_id,
    )
    return resolved.to_dict()


@app.post("/api/governance/approvals/{approval_id}/execute", tags=["governance"])
@limiter.limit("30/minute")
async def governance_execute_approval(
    request: Request,
    approval_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """The REQUIRE_APPROVAL -> resume-execution pipeline (v3
    authority-layer work): a human has already resolved this approval
    APPROVED via the resolve endpoint above; this actually runs the
    original action against the exact arguments they reviewed, via the
    same InternalToolExecutor the live governed MCP dispatch path uses.
    ADMIN-role, same as resolve -- executing a previously-gated action
    is at least as privileged as approving it.
    """
    if not _auth.org_id:
        raise HTTPException(400, "Governance approvals require an org-scoped API key, not a legacy flat key.")
    try:
        result = await resume_approval(
            approval_id,
            approval_repo=_ready(_approval_repo),
            evidence_repo=_ready(_evidence_repo),
            org_id=_auth.org_id,
        )
    except ApprovalNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    except ApprovalExpiredError as exc:
        raise HTTPException(409, str(exc)) from None
    except (ApprovalNotApprovedError, ApprovalActionMismatchError) as exc:
        raise HTTPException(409, str(exc)) from None
    except ValueError as exc:
        # build_resume_action()'s "no persisted arguments" case -- a
        # pre-resume-feature approval that was already APPROVED before
        # this endpoint existed.
        raise HTTPException(422, str(exc)) from None
    logger.info(
        "governance_approval_executed", approval_id=approval_id, org_id=_auth.org_id,
    )
    return {"approval_id": approval_id, "result": result}


def _policy_rule_to_dict(rule: PolicyRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "reason_code": rule.reason_code,
        "effect": rule.effect.value,
        "risk_tiers": sorted(t.value for t in rule.risk_tiers) if rule.risk_tiers else None,
        "action_types": sorted(rule.action_types) if rule.action_types else None,
        "targets": sorted(rule.targets) if rule.targets else None,
    }


@app.get("/api/governance/policy", tags=["governance"])
@limiter.limit("30/minute")
async def governance_get_policy(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """The org's persisted policy, in evaluation order (first-match-wins
    — see governance/policy.py). Previously policies only existed as
    in-code objects a call site constructed fresh each time; this is
    what an org actually configured, queryable and editable without a
    deploy."""
    if not _auth.org_id:
        raise HTTPException(400, "Governance policy requires an org-scoped API key, not a legacy flat key.")
    policy = await _ready(_policy_repo).get_policy(_auth.org_id)
    return {"org_id": _auth.org_id, "rules": [_policy_rule_to_dict(r) for r in policy.rules]}


@app.post("/api/governance/policy/rules", tags=["governance"])
@limiter.limit("20/minute")
async def governance_add_policy_rule(
    request: Request,
    req: PolicyRuleCreateRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Adding a policy rule is ADMIN+ (like resolving an approval) — it
    changes what future actions this org's own governance pipeline
    allows, not just a view of past decisions. Appended at the end of
    the evaluation order; use POST /api/governance/policy/reorder to
    change that."""
    if not _auth.org_id:
        raise HTTPException(400, "Governance policy requires an org-scoped API key, not a legacy flat key.")
    try:
        rule = PolicyRule(
            rule_id=req.rule_id,
            reason_code=req.reason_code,
            effect=GovernanceDecision(req.effect),
            risk_tiers=frozenset(RiskTier(t) for t in req.risk_tiers) if req.risk_tiers else None,
            action_types=frozenset(req.action_types) if req.action_types else None,
            targets=frozenset(req.targets) if req.targets else None,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    existing = await _ready(_policy_repo).get_policy(_auth.org_id)
    if any(r.rule_id == rule.rule_id for r in existing.rules):
        raise HTTPException(409, f"Rule {rule.rule_id!r} already exists for this org.")
    await _ready(_policy_repo).add_rule(_auth.org_id, rule)
    logger.info("governance_policy_rule_added", rule_id=rule.rule_id, org_id=_auth.org_id, added_by=_auth.key_id)
    return _policy_rule_to_dict(rule)


@app.delete("/api/governance/policy/rules/{rule_id}", tags=["governance"])
@limiter.limit("20/minute")
async def governance_remove_policy_rule(
    request: Request,
    rule_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, str]:
    if not _auth.org_id:
        raise HTTPException(400, "Governance policy requires an org-scoped API key, not a legacy flat key.")
    try:
        await _ready(_policy_repo).remove_rule(_auth.org_id, rule_id)
    except PolicyRuleNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    logger.info("governance_policy_rule_removed", rule_id=rule_id, org_id=_auth.org_id, removed_by=_auth.key_id)
    return {"status": "removed", "rule_id": rule_id}


@app.post("/api/governance/policy/reorder", tags=["governance"])
@limiter.limit("20/minute")
async def governance_reorder_policy(
    request: Request,
    req: PolicyReorderRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    if not _auth.org_id:
        raise HTTPException(400, "Governance policy requires an org-scoped API key, not a legacy flat key.")
    try:
        await _ready(_policy_repo).reorder(_auth.org_id, req.rule_ids)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from None
    policy = await _ready(_policy_repo).get_policy(_auth.org_id)
    logger.info("governance_policy_reordered", org_id=_auth.org_id, reordered_by=_auth.key_id)
    return {"org_id": _auth.org_id, "rules": [_policy_rule_to_dict(r) for r in policy.rules]}


@app.post("/api/governance/supplychain/scan", tags=["governance"])
@limiter.limit("30/minute")
async def governance_supplychain_scan(
    request: Request,
    req: SupplyChainScanRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """MCP Trust/Supply-Chain Scanner (SPEC.md Section 7, Phase 13) --
    evaluates a caller-supplied MCP server manifest (this endpoint never
    connects to a remote MCP server itself; see supplychain/scanner.py's
    module docstring for why). Not org-scoped: the checks it runs are
    either pure (content/name analysis) or query the public, org-agnostic
    AI Incident Database, so there's no per-org data to isolate here."""
    manifest = McpServerManifest(
        name=req.server_name,
        publisher=req.publisher,
        tools=[McpToolDescriptor(name=t.name, description=t.description) for t in req.tools],
    )
    incident_repo = _public_incident_repo if req.check_known_incidents else None
    report = await _supplychain_scanner.scan(manifest, incident_repo=incident_repo)
    return report.to_dict()


# ── MCP Upstream Gateway ────────────────────────────────────────────────────────
# v3 authority-layer work: an org-scoped registry of approved external MCP
# servers, and a governed proxy call to a specific tool on one of them. See
# governance/upstream.py, governance/upstream_executor.py,
# mcp/upstream_dispatch.py.

@app.post("/api/governance/upstream/servers", tags=["governance"], status_code=201)
@limiter.limit("10/minute")
async def upstream_register_server(
    request: Request,
    req: UpstreamServerRegisterRequest,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    """Registering a server IS the approval step (see
    ReasonCode.UNAPPROVED_MCP_SERVER) -- ADMIN-role, and the URL is
    SSRF-validated (private/loopback/link-local/reserved/multicast/
    unspecified addresses, cloud-metadata endpoint) before anything is
    persisted."""
    if not _auth.org_id:
        raise HTTPException(400, "Upstream servers require an org-scoped API key, not a legacy flat key.")
    try:
        server = await _ready(_upstream_registry).register(
            _auth.org_id, req.name, req.url, added_by=_auth.key_id, auth_token=req.auth_token,
        )
    except UnsafeUpstreamServerURLError as exc:
        raise HTTPException(422, str(exc)) from None
    logger.info("upstream_server_registered", server_id=server.server_id, org_id=_auth.org_id, added_by=_auth.key_id)
    return server.to_dict()


@app.get("/api/governance/upstream/servers", tags=["governance"])
@limiter.limit("30/minute")
async def upstream_list_servers(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    if not _auth.org_id:
        raise HTTPException(400, "Upstream servers require an org-scoped API key, not a legacy flat key.")
    servers = await _ready(_upstream_registry).list_for_org(_auth.org_id)
    return {"servers": [s.to_dict() for s in servers]}


@app.delete("/api/governance/upstream/servers/{server_id}", tags=["governance"])
@limiter.limit("10/minute")
async def upstream_remove_server(
    request: Request,
    server_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, str]:
    if not _auth.org_id:
        raise HTTPException(400, "Upstream servers require an org-scoped API key, not a legacy flat key.")
    try:
        await _ready(_upstream_registry).remove(_auth.org_id, server_id)
    except UpstreamServerNotFoundError as exc:
        raise HTTPException(404, str(exc)) from None
    logger.info("upstream_server_removed", server_id=server_id, org_id=_auth.org_id, removed_by=_auth.key_id)
    return {"status": "removed", "server_id": server_id}


@app.post("/api/governance/upstream/servers/{server_id}/call", tags=["governance"])
@limiter.limit("30/minute")
async def upstream_call_tool(
    request: Request,
    server_id: str,
    req: UpstreamToolCallRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """A governed proxy call to one tool on one registered upstream MCP
    server -- goes through the exact same five-way decision every
    internal tool call goes through (risk classification, authority,
    policy, quarantine, evidence), with the registry membership check
    (registered / same org / enabled) as an additional pre-check. Same
    ANALYST+ tier as internal governed tool calls: real authorization
    happens in the governance pipeline, not the REST role check."""
    if not _auth.org_id:
        raise HTTPException(400, "Upstream calls require an org-scoped API key, not a legacy flat key.")
    executor = UpstreamMCPExecutor(_ready(_upstream_registry))
    try:
        outcome = await apply_upstream_governance(
            server_id, req.tool_name, req.arguments, _auth,
            gateway=_upstream_gateway,
            evidence_repo=_ready(_evidence_repo),
            policy_repo=_ready(_policy_repo),
            approval_repo=_ready(_approval_repo),
            upstream_registry=_ready(_upstream_registry),
            executor=executor,
        )
    except UpstreamServerNotAvailableError as exc:
        raise HTTPException(404, str(exc)) from None
    if not outcome.proceed:
        return outcome.blocked_response or {"error": "governance_blocked"}
    return {"server_id": server_id, "tool_name": req.tool_name, "result": outcome.result}


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
            snapshot["monthly_spend_usd"] = round(await _ready(_cost_repo).total_cost(30), 4)
        if _trust_repo:
            snapshot["models"] = await _ready(_trust_repo).all_models()
        if _org_repo:
            snapshot["org_count"] = len(await _ready(_org_repo).list_orgs())
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
    try:
        validate_webhook_url(req.url)
    except UnsafeWebhookURLError as exc:
        raise HTTPException(400, f"Invalid webhook URL: {exc}") from exc
    config = WebhookConfig(
        url=req.url, events=events,
        org_id=_auth.org_id,
        provider=WebhookProvider(req.provider),
        secret=req.secret, description=req.description,
        max_retries=req.max_retries,
    )
    await _webhook_manager.register_and_persist(config)
    return config.to_dict()


@app.get("/api/webhooks", tags=["webhooks"])
@limiter.limit("60/minute")
async def list_webhooks(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    # Org-specific keys: force scope to their org. Legacy super-admin keys
    # (is_legacy=True, role=OWNER): see everything, same as /api/audit.
    scoped_org_id: str | None
    if _auth.org_id is not None:
        scoped_org_id = _auth.org_id
    elif _auth.is_legacy and _auth.role == Role.OWNER:
        scoped_org_id = None
    else:
        scoped_org_id = _auth.org_id
    return {"webhooks": [c.to_dict() for c in _webhook_manager.list_webhooks(org_id=scoped_org_id)]}


@app.delete("/api/webhooks/{webhook_id}", tags=["webhooks"])
@limiter.limit("30/minute")
async def delete_webhook(
    request: Request,
    webhook_id: str,
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> dict[str, Any]:
    scoped_org_id = _auth.org_id if not (_auth.is_legacy and _auth.role == Role.OWNER) else None
    if not await _webhook_manager.remove_and_persist(webhook_id, org_id=scoped_org_id):
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
    is_super_admin = _auth.is_legacy and _auth.role == Role.OWNER
    if cfg is None or (not is_super_admin and cfg.org_id != _auth.org_id):
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
    score = _ready(_trust_engine).compute(
        fairness=req.fairness, privacy=req.privacy, security=req.security,
        robustness=req.robustness, compliance=req.compliance, authenticity=req.authenticity,
    )
    compliance_report = _ready(_compliance).evaluate(
        fairness_score=req.fairness, privacy_score=req.privacy,
        security_score=req.security, robustness_score=req.robustness,
        compliance_maturity=req.compliance, use_case=req.use_case,
    )
    passport = _ready(_passport_gen).generate(
        model_name=req.model_name, provider=req.provider, trust_score=score,
        compliance_summary={"overall": round(compliance_report.compliance_score * 100, 1)},
    )
    await _ready(_passport_repo).create(passport, org_id=_auth.org_id, source="evaluate")
    drift_alert = None
    if req.record_drift:
        drift_alert = await _ready(_trust_repo).record(req.model_name, req.provider, score, org_id=_auth.org_id)

    observe_trust_score(req.model_name, req.provider, score.overall, org_id=_auth.org_id)
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
        observe_drift_alert(drift_alert.get("severity", "LOW"), org_id=_auth.org_id)
        deliveries = await _webhook_manager.fire(
            WebhookEvent.DRIFT_ALERT,
            {"model": req.model_name, "provider": req.provider,
             "delta": drift_alert.get("delta"), "severity": drift_alert.get("severity"),
             "score": score.overall},
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.DRIFT_ALERT.value, d.success, org_id=_auth.org_id)
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
        "verify_url": f"/api/trust-index/verify/{passport.passport_id}",
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
    history = await _ready(_trust_repo).history(model_name, provider, limit=limit, org_id=_auth.org_id)
    trend = await _ready(_trust_repo).trend(model_name, provider, org_id=_auth.org_id)
    return {"model": model_name, "provider": provider, "history": history, "trend": trend}


@app.get("/api/models", tags=["trust"])
@limiter.limit("120/minute")
async def list_models(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    return {"models": await _ready(_trust_repo).all_models(org_id=_auth.org_id)}


# ── Guardrails ─────────────────────────────────────────────────────────────────

@app.post("/api/scan", tags=["guardrails"])
@limiter.limit("200/minute")
async def scan_text(
    request: Request,
    req: ScanTextRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    result = _ready(_guardrails).scan(req.text)
    blocked = result.is_blocked
    observe_guardrail(blocked, org_id=_auth.org_id)
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
            observe_webhook_delivery(WebhookEvent.GUARDRAIL_TRIGGERED.value, d.success, org_id=_auth.org_id)

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
    result = _ready(_hallucination).analyze(text, candidates=candidates)
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
        org_id=_auth.org_id,
    )
    cost_record = await _ready(_cost_repo).record(usage)
    observe_cost(req.model, req.provider, cost_record.total_cost, req.input_tokens, req.output_tokens, org_id=_auth.org_id)
    record_cost(req.provider, req.model, cost_record.total_cost, req.input_tokens + req.output_tokens)

    await _ws_manager.broadcast({
        "type": "cost_update",
        "data": {"model": req.model, "provider": req.provider,
                 "cost_usd": cost_record.total_cost,
                 "tokens": req.input_tokens + req.output_tokens,
                 "timestamp": datetime.now(UTC).isoformat()},
    })

    budget = await _ready(_cost_repo).check_budget(org_id=_auth.org_id)
    if budget.is_exceeded:
        deliveries = await _webhook_manager.fire(
            WebhookEvent.BUDGET_EXCEEDED,
            {"monthly_limit_usd": budget.monthly_limit_usd,
             "total_spent_usd": budget.total_spent_usd,
             "overage_usd": round(budget.total_spent_usd - budget.monthly_limit_usd, 4)},
        )
        for d in deliveries:
            observe_webhook_delivery(WebhookEvent.BUDGET_EXCEEDED.value, d.success, org_id=_auth.org_id)

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
    oid = _auth.org_id
    return {
        "total_cost_usd": await _ready(_cost_repo).total_cost(days, org_id=oid),
        "total_tokens": await _ready(_cost_repo).total_tokens(days, org_id=oid),
        "model_breakdown": await _ready(_cost_repo).get_model_breakdown(days, org_id=oid),
        "team_breakdown": await _ready(_cost_repo).get_team_breakdown(days, org_id=oid),
        "daily_costs": await _ready(_cost_repo).get_daily_costs(days, org_id=oid),
        "budget_status": (await _ready(_cost_repo).check_budget(org_id=oid)).to_dict(),
        "request_count": await _ready(_cost_repo).request_count(days, org_id=oid),
    }


@app.post("/api/cost/analyze", tags=["cost"])
@limiter.limit("60/minute")
async def analyze_prompt(
    request: Request,
    req: AnalyzePromptRequest,
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    result = _ready(_cost_analyzer).analyze_prompt_efficiency(
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
    decision = _ready(_router).route(req.task_description, req.quality_requirement)
    return decision.to_dict()


@app.get("/api/cost/models", tags=["cost"])
@limiter.limit("60/minute")
async def model_pricing(
    request: Request,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    return {"models": _ready(_router).provider_comparison()}


# ── Drift ──────────────────────────────────────────────────────────────────────

@app.get("/api/drift/{model_name}/{provider}", tags=["drift"])
@limiter.limit("120/minute")
async def get_drift_trend(
    request: Request,
    model_name: str,
    provider: str,
    _auth: OrgContext = Depends(require_role(Role.VIEWER)),
) -> dict[str, Any]:
    trend = await _ready(_trust_repo).trend(model_name, provider)
    history = await _ready(_trust_repo).history(model_name, provider, limit=10)
    return {"trend": trend, "recent_history": history}


# ── API versioning ─────────────────────────────────────────────────────────────

@app.get("/api/version", tags=["ops"])
async def api_version() -> dict[str, Any]:
    """Return full version and stability metadata."""
    return {
        "version": "1.2.0",
        "major": 1,
        "minor": 2,
        "patch": 0,
        "stable": True,
        "api_versions": ["1.0", "1.1"],
        "current_api_prefix": "/api/v1",
        "deprecated_prefixes": [],
        "release_date": "2026-07-12",
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
) -> Response:
    """Handle the OAuth2 callback — exchange code for tokens, then redirect the
    browser to /auth/complete with the access token in a URL fragment (never
    sent to the server, unlike a query param, so it never lands in access
    logs). That page extracts it client-side and finishes the login."""
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

    access_token = tokens.get("access_token") or ""
    fragment = f"token={quote(access_token)}&name={quote(claims.name or claims.email or claims.sub)}"
    return RedirectResponse(url=f"/auth/complete#{fragment}", status_code=302)


@app.post("/api/auth/logout", tags=["auth"])
async def auth_logout(
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Invalidate the current session (client should discard its token)."""
    return {"logged_out": True, "timestamp": datetime.now(UTC).isoformat()}


@app.post("/api/auth/login-key", tags=["auth"])
@limiter.limit("10/minute")
async def login_with_key(request: Request, req: LoginKeyRequest) -> dict[str, Any]:
    """Human-facing login step for the dashboard's /login page.

    Distinct from every other endpoint's Bearer-header auth: this is the
    one interactive login step, so it's where TOTP MFA gets enforced (see
    auth/mfa.py's module docstring for why it can't be enforced on
    ordinary API calls). Flow:
      1. POST {api_key} — if the key's org requires MFA and the key isn't
         enrolled yet, returns 403 telling the caller to enroll first.
         If enrolled, returns {mfa_required: true} without a code.
      2. POST {api_key, mfa_code} — verifies the code (or a backup code)
         and returns {ok: true}. The frontend then treats the api_key
         itself as the session token, same as before this endpoint existed.
    """
    if not settings.auth_enabled:
        return {"ok": True, "mfa_required": False}
    if settings.api_keys and req.api_key in settings.api_keys:
        return {"ok": True, "mfa_required": False}

    try:
        ctx = await _ready(_org_repo).authenticate(req.api_key)
    except SSORequiredError:
        raise HTTPException(
            403, "This organization requires SSO login — use the SSO button instead."
        ) from None
    if ctx is None:
        raise HTTPException(401, "Invalid or revoked API key")

    org = await _ready(_org_repo).get_org(ctx.org_id) if ctx.org_id else None
    if org is not None and org.mfa_required:
        if not ctx.mfa_enrolled:
            raise HTTPException(
                403,
                "This organization requires MFA and this key hasn't enrolled yet. "
                f"An admin must call POST /api/orgs/{org.id}/keys/{ctx.key_id}/mfa/enroll first.",
            )
        if not req.mfa_code:
            return {"ok": False, "mfa_required": True}

        key = await _ready(_org_repo).get_key(ctx.key_id)
        if key is None or not key.mfa_secret:
            raise HTTPException(401, "MFA state is inconsistent for this key — contact an admin")

        if mfa.verify_code(key.mfa_secret, req.mfa_code):
            return {"ok": True, "mfa_required": True}

        remaining = mfa.verify_and_consume_backup_code(
            key.mfa_backup_codes or [], req.mfa_code
        )
        if remaining is not None:
            await _ready(_org_repo).consume_backup_code(ctx.key_id, remaining)
            return {"ok": True, "mfa_required": True, "backup_code_used": True}

        raise HTTPException(401, "Invalid MFA code")

    return {"ok": True, "mfa_required": False}


@app.get("/api/auth/session", tags=["auth"])
async def auth_session(_auth: OrgContext = Depends(get_org_context)) -> dict[str, Any]:
    """Current auth context — used by the Settings page for self-service
    MFA enrollment (needs its own key_id/mfa_enrolled without a separate
    list-keys call, which would require ADMIN and this doesn't)."""
    return {
        "key_id": _auth.key_id,
        "key_name": _auth.key_name,
        "org_id": _auth.org_id,
        "org_name": _auth.org_name,
        "role": _auth.role.value,
        "is_legacy": _auth.is_legacy,
        "mfa_enrolled": _auth.mfa_enrolled,
    }


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
            "email": "annaduraiguruprasath7@gmail.com",
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
            await _ready(_cost_repo).request_count()
    except Exception:
        db_ok = False
    return {
        "platform": "ResponsibleAI Governance Platform",
        "version": "1.2.0",
        "status": "operational" if db_ok else "degraded",
        "uptime_seconds": round(time.monotonic() - _START_TIME, 1),
        "timestamp": datetime.now(UTC).isoformat(),
    }


# ── Audit log ──────────────────────────────────────────────────────────────────

@app.get("/api/audit", tags=["audit"])
@limiter.limit("60/minute")
async def list_audit_entries(
    request: Request,
    org_id: str | None = Query(None, description="Cross-org filter (super-admin only)"),
    endpoint: str | None = Query(None, description="Filter by endpoint path"),
    days: int = Query(30, ge=1, le=365, description="Lookback window in days"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    _auth: OrgContext = Depends(require_role(Role.ANALYST)),
) -> dict[str, Any]:
    """Query the governance audit log. Always scoped to the authenticated org."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    # Org-specific keys: force scope to their org regardless of query param.
    # Legacy super-admin keys (is_legacy=True, role=OWNER): allow cross-org filter.
    scoped_org_id: str | None
    if _auth.org_id is not None:
        scoped_org_id = _auth.org_id
    elif _auth.is_legacy and _auth.role == Role.OWNER:
        scoped_org_id = org_id
    else:
        scoped_org_id = None
    rows = await _ready(_audit_repo).query(org_id=scoped_org_id, endpoint=endpoint, days=days, limit=limit, offset=offset)
    total = await _ready(_audit_repo).count(days=days, org_id=scoped_org_id)
    return {
        "entries": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "days": days,
    }


@app.get("/api/audit/export", tags=["audit"])
@limiter.limit("10/minute")
async def export_audit_log(
    request: Request,
    org_id: str | None = Query(None, description="Cross-org filter (super-admin only)"),
    days: int = Query(30, ge=1, le=365),
    _auth: OrgContext = Depends(require_role(Role.ADMIN)),
) -> Response:
    """Export audit log as CSV. Results scoped to authenticated org."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    scoped_org_id: str | None
    if _auth.org_id is not None:
        scoped_org_id = _auth.org_id
    elif _auth.is_legacy and _auth.role == Role.OWNER:
        scoped_org_id = org_id
    else:
        scoped_org_id = None
    rows = await _ready(_audit_repo).query(org_id=scoped_org_id, days=days, limit=5000)
    import csv as _csv
    import io as _io
    buf = _io.StringIO()
    writer = _csv.writer(buf)
    writer.writerow(["id", "timestamp", "org_id", "key_id", "endpoint", "method",
                     "status_code", "ip_address", "request_id", "duration_ms",
                     "entry_hash", "prev_hash"])
    for r in rows:
        writer.writerow([
            r.get("id", ""), r.get("timestamp", ""), r.get("org_id", ""),
            r.get("key_id", ""), r.get("endpoint", ""), r.get("method", ""),
            r.get("status_code", ""), r.get("ip_address", ""),
            r.get("request_id", ""), r.get("duration_ms", ""),
            r.get("entry_hash", ""), r.get("prev_hash", ""),
        ])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=audit-{days}d.csv"},
    )


@app.get("/api/audit/verify", tags=["audit"])
@limiter.limit("10/minute")
async def verify_audit_chain(
    request: Request,
    days: int = Query(90, ge=1, le=365),
    _auth: OrgContext = Depends(require_role(Role.OWNER)),
) -> dict[str, Any]:
    """Verify audit log tamper-evidence by recomputing the hash chain.

    Restricted to legacy super-admin OWNER — the chain spans all orgs on
    this server, so verifying it inherently reveals cross-org existence.
    """
    if not (_auth.is_legacy and _auth.role == Role.OWNER):
        raise HTTPException(403, "Audit chain verification requires super-admin access")
    return await _ready(_audit_repo).verify_chain(days=days)


@app.get("/api/audit/summary", tags=["audit"])
async def audit_endpoint_summary(
    days: int = Query(7, ge=1, le=90),
    _auth: OrgContext = Depends(get_org_context),
) -> dict[str, Any]:
    """Top endpoints by request count and average latency."""
    if not _audit_repo:
        raise HTTPException(503, "Audit repository not initialised")
    summary = await _ready(_audit_repo).endpoint_summary(days=days)
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
    oid = _auth.org_id
    total_cost = await _ready(_cost_repo).total_cost(days=days, org_id=oid)
    total_tokens = await _ready(_cost_repo).total_tokens(days=days, org_id=oid)
    request_count = await _ready(_cost_repo).request_count(days=days, org_id=oid)
    model_breakdown = await _ready(_cost_repo).get_model_breakdown(days=days, org_id=oid)
    return {
        "period_days": days,
        "total_cost_usd": round(total_cost, 6),
        "total_requests": request_count,
        "total_tokens": total_tokens,
        "cost_by_model": {k: round(v, 6) for k, v in model_breakdown.items()},
        "timestamp": datetime.now(UTC).isoformat(),
    }
