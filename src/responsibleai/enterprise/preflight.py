# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed production preflight for enterprise identity and legacy keys.

Production never boots with static RAI_API_KEYS or a known identity-webhook secret.
"""

from __future__ import annotations

import logging
import os
import warnings
from typing import Any

from responsibleai.dashboard.config import is_production_environment

logger = logging.getLogger(__name__)

DEV_IDENTITY_WEBHOOK_SECRET = "dev-identity-webhook-secret"
KNOWN_WEAK_WEBHOOK_SECRETS = frozenset(
    {
        DEV_IDENTITY_WEBHOOK_SECRET,
        "changeme",
        "secret",
        "password",
        "test",
        "sample",
        "identity-webhook-secret",
        "whitepact",
        "webhook-secret",
    }
)
MIN_PRODUCTION_WEBHOOK_SECRET_LENGTH = 32


class HostedEnterpriseSecurityError(RuntimeError):
    """Raised when production would boot with an unsafe identity configuration."""


def _configured_api_keys(settings: Any) -> list[str]:
    keys = list(getattr(settings, "api_keys", None) or [])
    raw = os.environ.get("RAI_API_KEYS") or os.environ.get("WHITEPACT_API_KEYS") or ""
    extra = [item.strip() for item in raw.split(",") if item.strip()]
    seen: set[str] = set()
    out: list[str] = []
    for item in [*keys, *extra]:
        if item and item not in seen:
            seen.add(item)
            out.append(item)
    return out


def resolve_identity_webhook_secret(
    *,
    environment: str,
    configured: str | None,
) -> str:
    """Return the HMAC webhook secret or fail closed in production."""
    production = is_production_environment(environment)
    value = (configured or "").strip()
    if production:
        if not value:
            raise HostedEnterpriseSecurityError(
                "Production requires WHITEPACT_IDENTITY_WEBHOOK_SECRET to be "
                "explicitly configured. Refusing to start with a missing or empty secret."
            )
        if value.lower() in {item.lower() for item in KNOWN_WEAK_WEBHOOK_SECRETS}:
            raise HostedEnterpriseSecurityError(
                "Production identity webhook secret matches a known development "
                "or sample value. Refusing to start."
            )
        if len(value) < MIN_PRODUCTION_WEBHOOK_SECRET_LENGTH:
            raise HostedEnterpriseSecurityError(
                "Production identity webhook secret is trivially weak. "
                f"Require at least {MIN_PRODUCTION_WEBHOOK_SECRET_LENGTH} characters of entropy."
            )
        return value
    return value or DEV_IDENTITY_WEBHOOK_SECRET


def identity_webhook_secret_from_env(*, environment: str | None = None) -> str:
    env = environment or os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENV") or os.environ.get(
        "ENVIRONMENT", "development"
    )
    configured = os.environ.get("WHITEPACT_IDENTITY_WEBHOOK_SECRET") or os.environ.get(
        "RAI_IDENTITY_WEBHOOK_SECRET"
    )
    return resolve_identity_webhook_secret(environment=env, configured=configured)


def assert_legacy_api_keys_boot_safe(settings: Any) -> None:
    """Production + RAI_API_KEYS must fail startup. Non-prod emits a deprecation warning."""
    keys = _configured_api_keys(settings)
    environment = str(getattr(settings, "environment", "development") or "development")
    if not keys:
        return
    if is_production_environment(environment) or bool(getattr(settings, "is_production", False)):
        raise HostedEnterpriseSecurityError(
            "Production hosted authentication forbids static RAI_API_KEYS / "
            "WHITEPACT_API_KEYS. Remove the variable and issue org-scoped credentials "
            "through verified-principal enterprise IAM. Refusing to start."
        )
    warnings.warn(
        "RAI_API_KEYS is deprecated. Legacy static keys are restricted to a "
        "non-production compatibility scope: they are never OWNER, never "
        "cross-tenant, and cannot issue enterprise credentials or reach Phase 7A. "
        "Migrate to verified-principal API keys (wp_test_/wp_staging_/wp_live_).",
        DeprecationWarning,
        stacklevel=2,
    )
    logger.warning(
        "legacy_rai_api_keys_configured env=%s key_count=%s",
        environment,
        len(keys),
    )


def assert_identity_webhook_boot_safe(settings: Any) -> None:
    environment = str(getattr(settings, "environment", "development") or "development")
    configured = os.environ.get("WHITEPACT_IDENTITY_WEBHOOK_SECRET") or os.environ.get(
        "RAI_IDENTITY_WEBHOOK_SECRET"
    )
    resolve_identity_webhook_secret(environment=environment, configured=configured)


def assert_hosted_enterprise_boot_safe(settings: Any) -> None:
    assert_legacy_api_keys_boot_safe(settings)
    assert_identity_webhook_boot_safe(settings)
    from responsibleai.enterprise.security.preflight import assert_layer2_provider_boot_safe

    assert_layer2_provider_boot_safe(settings)
