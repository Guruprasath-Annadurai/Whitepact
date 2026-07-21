"""Runtime configuration — every value overridable via env var or .env file."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="RAI_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Database
    db_path: str = Field(
        default_factory=lambda: str(Path.home() / ".responsibleai" / "data.db"),
        description="SQLite database path. Use ':memory:' for stateless/testing.",
    )

    # Authentication
    api_keys: list[str] = Field(
        default=[],
        description="Comma-separated list of valid API keys. Empty = auth disabled (dev only).",
    )
    auth_enabled: bool = Field(
        default=True,
        description="Set to false to disable auth (development only).",
    )

    # Rate limiting
    rate_limit_default: str = Field(
        default="100/minute",
        description="Default rate limit applied to all endpoints.",
    )
    rate_limit_evaluate: str = Field(
        default="30/minute",
        description="Rate limit for the /api/evaluate endpoint.",
    )

    # CORS
    allowed_origins: list[str] = Field(
        default=["http://localhost:8765", "http://127.0.0.1:8765"],
        description="Allowed CORS origins.",
    )
    allow_all_origins: bool = Field(
        default=False,
        description="Set true to allow all origins (dev/demo only).",
    )

    # Governance
    alert_threshold: float = Field(
        default=5.0,
        description="Trust score drop (points) that triggers a DriftAlert.",
        ge=0.1,
        le=50.0,
    )
    monthly_budget_usd: float = Field(
        default=10_000.0,
        description="Monthly AI spending budget for budget enforcement.",
        ge=0.0,
    )

    # Logging
    log_level: str = Field(
        default="INFO",
        description="Logging level: DEBUG, INFO, WARNING, ERROR.",
    )
    log_json: bool = Field(
        default=True,
        description="Emit structured JSON logs (recommended for production).",
    )

    # PostgreSQL (optional — defaults to SQLite via db_path)
    database_url: str | None = Field(
        default=None,
        description=(
            "Full database URL for async engine. "
            "postgresql://user:pass@host/db or leave unset to use SQLite."
        ),
    )

    # Schema migrations
    auto_migrate: bool = Field(
        default=True,
        description=(
            "Run `alembic upgrade head` automatically at startup. "
            "create_all() only creates brand-new tables — it never ALTERs "
            "existing ones, so without this, upgrading an existing self-hosted "
            "install to a version with schema changes leaves old columns "
            "missing and endpoints 500ing at runtime instead of failing at "
            "startup. Disable only if you run migrations explicitly as a "
            "separate deploy step (recommended for multi-replica hosted "
            "deployments, to avoid concurrent migration runs — see "
            "DEPLOY_RUNBOOK.md)."
        ),
    )

    # Redis (optional — falls back to in-memory rate limiting)
    redis_url: str | None = Field(
        default=None,
        description="Redis URL for distributed rate limiting, e.g. redis://localhost:6379/0.",
    )

    # OpenTelemetry (optional)
    otel_endpoint: str | None = Field(
        default=None,
        description="OTLP HTTP endpoint, e.g. http://otel-collector:4318. Unset = disabled.",
    )
    otel_service_name: str = Field(
        default="responsibleai",
        description="Service name reported to the OTLP collector.",
    )
    otel_headers: str = Field(
        default="",
        description="Comma-separated key=value pairs sent as OTLP headers (e.g. Datadog API key).",
    )

    # OIDC / OAuth2 Single Sign-On (optional — leave unset to use API key auth only)
    oidc_issuer: str | None = Field(
        default=None,
        description="OIDC issuer URL, e.g. https://accounts.google.com or https://login.microsoftonline.com/<tenant>.",
    )
    oidc_client_id: str = Field(
        default="",
        description="OAuth2 client ID registered with the OIDC provider.",
    )
    oidc_client_secret: str = Field(
        default="",
        description="OAuth2 client secret (kept server-side only).",
    )
    oidc_redirect_uri: str = Field(
        default="http://localhost:8765/api/auth/callback",
        description="Callback URL registered with the OIDC provider.",
    )
    oidc_scopes: list[str] = Field(
        default=["openid", "email", "profile"],
        description="OAuth2 scopes to request.",
    )
    oidc_jwks_uri: str | None = Field(
        default=None,
        description="JWKS endpoint override. Auto-discovered from oidc_issuer if unset.",
    )
    oidc_skip_verification: bool = Field(
        default=False,
        description="Skip JWT signature verification (test/dev only — never use in production).",
    )

    # Stripe billing (optional — leave unset to disable paid-tier checkout)
    stripe_secret_key: str | None = Field(
        default=None,
        description="Stripe secret key (sk_live_... / sk_test_...). Unset = billing endpoints disabled.",
    )
    stripe_webhook_secret: str | None = Field(
        default=None,
        description="Stripe webhook signing secret (whsec_...) for verifying incoming events.",
    )
    stripe_price_id_pro: str | None = Field(
        default=None,
        description="Stripe Price ID for the PRO plan subscription.",
    )
    stripe_price_id_enterprise: str | None = Field(
        default=None,
        description="Stripe Price ID for the ENTERPRISE plan subscription.",
    )
    billing_success_url: str = Field(
        default="http://localhost:8765/billing/success",
        description="Redirect URL after successful Stripe checkout.",
    )
    billing_cancel_url: str = Field(
        default="http://localhost:8765/billing/cancel",
        description="Redirect URL after cancelled Stripe checkout.",
    )

    # Server
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8765, ge=1, le=65535)
    workers: int = Field(default=1, ge=1, le=32)

    @field_validator("oidc_scopes", mode="before")
    @classmethod
    def _parse_scopes(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return list(v) if v else ["openid", "email", "profile"]

    @field_validator("api_keys", mode="before")
    @classmethod
    def _parse_keys(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [k.strip() for k in v.split(",") if k.strip()]
        return list(v) if v else []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return list(v) if v else []

    @property
    def otel_headers_dict(self) -> dict[str, str]:
        if not self.otel_headers:
            return {}
        result: dict[str, str] = {}
        for pair in self.otel_headers.split(","):
            if "=" in pair:
                k, _, v = pair.strip().partition("=")
                result[k.strip()] = v.strip()
        return result

    @property
    def effective_db_url(self) -> str:
        """Postgres URL if set, else derive SQLite URL from db_path."""
        return self.database_url or self.db_path

    @property
    def db_dir(self) -> Path:
        p = Path(self.db_path)
        if p.name == ":memory:":
            return Path(".")
        return p.parent


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
        _ensure_db_dir(_settings)
    return _settings


def _ensure_db_dir(s: Settings) -> None:
    if s.db_path != ":memory:":
        Path(s.db_path).parent.mkdir(parents=True, exist_ok=True)
