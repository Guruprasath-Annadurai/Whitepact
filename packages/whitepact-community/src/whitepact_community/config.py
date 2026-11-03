"""Safe local configuration loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

from whitepact_community.errors import ConfigurationError

# Keys that must never appear in community config files.
_FORBIDDEN_KEYS = frozenset(
    {
        "stripe_secret_key",
        "stripe_webhook_secret",
        "aws_secret_access_key",
        "github_token",
        "didit_webhook_secret",
        "sovereign_root_key",
        "production_database_url",
        "saas_admin_token",
    }
)


class CommunityConfig(BaseModel):
    """Local-only configuration. No hosted SaaS account required."""

    org_id: str = "local"
    evidence_path: str | None = None
    default_grants: list[str] = Field(default_factory=lambda: ["local_echo", "local_health", "policy_evaluate", "governed_local_action"])
    quarantine_threshold: int = 3
    authorization_ttl_seconds: int = 30
    log_level: str = "WARNING"

    @field_validator("log_level")
    @classmethod
    def _valid_log_level(cls, value: str) -> str:
        allowed = {"DEBUG", "INFO", "WARNING", "ERROR"}
        upper = value.upper()
        if upper not in allowed:
            raise ValueError(f"log_level must be one of {sorted(allowed)}")
        return upper

    @field_validator("quarantine_threshold")
    @classmethod
    def _positive_threshold(cls, value: int) -> int:
        if value < 1:
            raise ValueError("quarantine_threshold must be >= 1")
        return value


def _reject_forbidden(raw: dict[str, Any]) -> None:
    lowered = {str(k).lower() for k in raw}
    hit = lowered & {k.lower() for k in _FORBIDDEN_KEYS}
    if hit:
        raise ConfigurationError(
            f"Configuration contains forbidden production/secret keys: {sorted(hit)}"
        )


def load_config(path: str | Path | None = None) -> CommunityConfig:
    if path is None:
        return CommunityConfig()
    config_path = Path(path)
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"Malformed configuration JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("Configuration root must be a JSON object")
    _reject_forbidden(raw)
    try:
        return CommunityConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc
