# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Helm values contract for Launch Cell B deployment profiles."""

from __future__ import annotations

from typing import Any

_PROFILES = frozenset({"development", "staging", "production"})


def _cfg(values: dict[str, Any]) -> dict[str, Any]:
    raw = values.get("config")
    return raw if isinstance(raw, dict) else {}


def _replica_floor(values: dict[str, Any]) -> int:
    autoscaling = values.get("autoscaling")
    if isinstance(autoscaling, dict) and autoscaling.get("enabled"):
        try:
            return max(int(autoscaling.get("minReplicas", 1)), 1)
        except (TypeError, ValueError):
            return 1
    try:
        return max(int(values.get("replicaCount", 1)), 1)
    except (TypeError, ValueError):
        return 1


def _has_database_url(values: dict[str, Any]) -> bool:
    cfg = _cfg(values)
    if str(cfg.get("databaseUrl") or "").strip():
        return True
    ext = values.get("externalSecrets")
    if isinstance(ext, dict):
        db = ext.get("databaseUrl")
        if isinstance(db, dict) and str(db.get("name") or "").strip():
            return True
    return False


def collect_helm_profile_errors(values: dict[str, Any]) -> list[str]:
    """Return machine-readable Helm values errors for the deployment profile."""
    profile = str(values.get("deploymentProfile") or "").strip().lower()
    if not profile:
        return ["helm_deployment_profile_missing"]
    if profile not in _PROFILES:
        return [f"helm_deployment_profile_invalid:{profile}"]

    errors: list[str] = []
    cfg = _cfg(values)
    replicas = _replica_floor(values)

    if profile == "production":
        if not cfg.get("authEnabled", True):
            errors.append("helm_production_auth_disabled_forbidden")
        if cfg.get("allowAllOrigins"):
            errors.append("helm_production_allow_all_origins_forbidden")
        if cfg.get("mcpHttpAllowUnauthenticatedDemo"):
            errors.append("helm_production_mcp_unauthenticated_demo_forbidden")
        if cfg.get("oidcSkipVerification"):
            errors.append("helm_production_oidc_skip_verification_forbidden")
        if cfg.get("vcSkipVerification"):
            errors.append("helm_production_vc_skip_verification_forbidden")
        if str(cfg.get("apiKeys") or "").strip():
            errors.append("helm_production_static_api_keys_forbidden")
        if not _has_database_url(values):
            errors.append("helm_production_database_url_required")
        persistence = values.get("persistence")
        persistence_enabled = isinstance(persistence, dict) and bool(persistence.get("enabled"))
        if persistence_enabled and _has_database_url(values):
            errors.append("helm_production_sqlite_persistence_with_postgres_forbidden")
        if replicas > 1 and not str(cfg.get("redisUrl") or "").strip():
            errors.append("helm_production_redis_required_for_multi_replica")
        if replicas > 1 and cfg.get("autoMigrate"):
            errors.append("helm_production_auto_migrate_forbidden_multi_replica")
        migration = values.get("migration")
        migration_enabled = (
            True
            if migration is None
            else bool(migration.get("enabled", True))
            if isinstance(migration, dict)
            else True
        )
        if not migration_enabled:
            errors.append("helm_production_migration_job_required")
        env_name = str(cfg.get("environment") or "").strip().lower()
        if env_name not in {"production", "prod"}:
            errors.append("helm_production_environment_must_be_production")
        oidc = values.get("oidc")
        if isinstance(oidc, dict) and oidc.get("enabled"):
            if (
                not str(oidc.get("issuer") or "").strip()
                or not str(oidc.get("clientId") or "").strip()
            ):
                errors.append("helm_production_oidc_enabled_but_incomplete")
            if not str(oidc.get("existingSecret") or "").strip():
                errors.append("helm_production_oidc_client_secret_secret_ref_required")

    if profile in {"staging", "production"}:
        if str(cfg.get("logJson", "true")).lower() not in {"1", "true", "yes"}:
            errors.append("helm_staging_production_log_json_required")

    sec = values.get("securityContext")
    if isinstance(sec, dict):
        if sec.get("readOnlyRootFilesystem") is not True:
            errors.append("helm_security_context_read_only_root_filesystem_required")
        if sec.get("runAsNonRoot") is not True:
            errors.append("helm_security_context_run_as_non_root_required")
        if sec.get("allowPrivilegeEscalation") is not False:
            errors.append("helm_security_context_no_privilege_escalation_required")

    return errors
