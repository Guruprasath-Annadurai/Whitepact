# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Vendor-neutral production operations types for Launch Cell B.

These types document the corporate operating model. They do not grant authority
or bypass governance. Formula enforcement remains a separate runtime concern.
"""

from __future__ import annotations

from enum import StrEnum


class DeploymentEnvironment(StrEnum):
    LOCAL = "local"
    TEST = "test"
    CI = "ci"
    STAGING = "staging"
    PRODUCTION = "production"
    DISASTER_RECOVERY = "disaster_recovery"


class SubsystemClassification(StrEnum):
    REAL_AND_TESTED = "REAL_AND_TESTED"
    REAL_BUT_PARTIAL = "REAL_BUT_PARTIAL"
    DEV_ONLY = "DEV_ONLY"
    DOCUMENTATION_ONLY = "DOCUMENTATION_ONLY"
    MISSING = "MISSING"
    UNVERIFIED = "UNVERIFIED"


class HealthProbeKind(StrEnum):
    LIVENESS = "liveness"
    READINESS = "readiness"
    STARTUP = "startup"
    DEEP_DIAGNOSTICS = "deep_diagnostics"


class FormulaRolloutMode(StrEnum):
    """Infrastructure support for future Ω∞ enforcement stages (Gate 8+)."""

    OFF = "OFF"
    SHADOW = "SHADOW"
    ADVISORY = "ADVISORY"
    RESTRICTED_ENFORCEMENT = "RESTRICTED_ENFORCEMENT"
    FULL_ENFORCEMENT = "FULL_ENFORCEMENT"


# Canonical structured log fields (see docs/operations/OBSERVABILITY_STANDARD.md).
STRUCTURED_LOG_CORE_FIELDS: tuple[str, ...] = (
    "timestamp",
    "level",
    "service",
    "environment",
    "version",
    "commit_sha",
    "request_id",
    "correlation_id",
    "tenant_id",
    "principal_id",
    "action_category",
    "decision_category",
    "latency_ms",
    "error_code",
)

# Environment variables that must never be enabled in production (fail-closed checks
# live in dashboard.config.Settings validators and MCP hosted_production_preflight).
PRODUCTION_FORBIDDEN_FLAGS: frozenset[str] = frozenset(
    {
        "WHITEPACT_AUTH_ENABLED=false",
        "RAI_AUTH_ENABLED=false",
        "WHITEPACT_ALLOW_ALL_ORIGINS=true",
        "RAI_ALLOW_ALL_ORIGINS=true",
        "WHITEPACT_OIDC_SKIP_VERIFY=true",
        "RAI_OIDC_SKIP_VERIFY=true",
        "WHITEPACT_VC_SKIP_VERIFY=true",
        "RAI_VC_SKIP_VERIFY=true",
    }
)
