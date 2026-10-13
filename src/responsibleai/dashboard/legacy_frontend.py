# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Retire the legacy ResponsibleAI HTML shell (BLK-P0-06).

The modern WhitePact React SPA is the only supported enterprise workspace UI.
Legacy pages used ``localStorage['rai_api_key']`` via ``static/js/app.js`` and
must not remain reachable as an alternate governance surface when unified SaaS
mode is enforced.

Retired shell HTML/JS/CSS live under ``legacy_templates/`` (not mounted at
``/static``). Unified/enterprise mode serves only an explicit static allowlist.
"""

from __future__ import annotations

import os
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings

_PACKAGE_DIR = Path(__file__).resolve().parent
LEGACY_TEMPLATES_ROOT = _PACKAGE_DIR / "legacy_templates"
LEGACY_GOVERNANCE_SHELL_DIR = LEGACY_TEMPLATES_ROOT / "governance_shell"

# Former on-disk subdir name — must never be servable under /static (BLK-P0-06-BYPASS-02).
RETIRED_LEGACY_STATIC_NAMESPACE_SEGMENTS: frozenset[str] = frozenset({"_retired_legacy_governance"})

# HTTP routes that served the legacy ResponsibleAI governance shell (app.js).
LEGACY_GOVERNANCE_PAGE_PATHS: frozenset[str] = frozenset(
    {
        "/auth/complete",
        "/evaluate",
        "/guardrails",
        "/hallucination",
        "/cost",
        "/router",
        "/trust-scores",
        "/eval",
        "/redteam",
        "/audit",
        "/incidents",
        "/webhooks-manage",
        "/organizations",
        "/billing",
        "/settings",
    }
)

# Static assets that only exist to power the legacy shell (community mode disk layout).
_LEGACY_HTML_FILENAMES: frozenset[str] = frozenset(
    {
        "index.html",
        "auth_complete.html",
        "evaluate.html",
        "guardrails.html",
        "hallucination.html",
        "cost.html",
        "router.html",
        "trust_scores.html",
        "eval.html",
        "redteam.html",
        "audit.html",
        "incidents.html",
        "webhooks_manage.html",
        "organizations.html",
        "billing.html",
        "settings.html",
        "login.html",
        "signup.html",
    }
)

LEGACY_SHELL_STATIC_REL_PATHS: frozenset[str] = frozenset(
    {name for name in _LEGACY_HTML_FILENAMES} | {"js/app.js", "js/i18n.js", "css/app.css"}
)

LEGACY_GOVERNANCE_STATIC_PATHS: frozenset[str] = frozenset(
    {f"/static/{name}" for name in _LEGACY_HTML_FILENAMES}
    | {"/static/js/app.js", "/static/js/i18n.js", "/static/css/app.css"}
)

# Canonical inventory for regression tests (relative to /static/ URL paths).
RETIRED_LEGACY_STATIC_INVENTORY: frozenset[str] = frozenset(LEGACY_GOVERNANCE_STATIC_PATHS)

# Public marketing / incident surfaces that remain under /static in unified mode.
UNIFIED_SAAS_STATIC_ALLOW_REL_PATHS: frozenset[str] = frozenset(
    {
        "assess.html",
        "leaderboard.html",
        "registry.html",
        "trust.html",
        "verify.html",
        "status.html",
        "incident_db.html",
        "incident_db_detail.html",
        "incident_db_report.html",
        "locales/en.json",
        "locales/es.json",
    }
)

UNIFIED_SAAS_STATIC_ALLOW_PREFIXES: tuple[str, ...] = ("whitepact/",)


def unified_saas_legacy_retirement_enforced(settings: Settings) -> bool:
    """True when legacy HTML governance surfaces must not be served."""
    flag = os.environ.get("WHITEPACT_UNIFIED_SAAS", "").strip().lower()
    if flag in {"1", "true", "yes", "on"}:
        return True
    if settings.is_production:
        return True
    if getattr(settings, "mcp_trust_domain", "community") == "enterprise":
        return True
    return False


def canonicalize_http_path(path: str, *, decode: bool = True) -> str:
    """Normalize URL path segments (slashes, dot segments) without filesystem access."""
    raw = path if path.startswith("/") else f"/{path}"
    if decode:
        try:
            raw = unquote(raw)
        except Exception:
            pass
    parts: list[str] = []
    for segment in raw.split("/"):
        if segment in ("", "."):
            continue
        if segment == "..":
            if parts:
                parts.pop()
            continue
        parts.append(segment)
    return "/" + "/".join(parts) if parts else "/"


def _static_relative_path(canonical_path: str) -> str | None:
    if not canonical_path.startswith("/static/"):
        if canonical_path == "/static":
            return ""
        return None
    rel = canonical_path.removeprefix("/static/").lstrip("/")
    return rel


def is_retired_legacy_static_namespace(relpath: str) -> bool:
    """True when URL maps to a blocked retired namespace under /static."""
    canonical = canonicalize_http_path(f"/static/{relpath}")
    rel = _static_relative_path(canonical)
    if rel is None:
        return False
    parts = PurePosixPath(rel).parts
    if not parts:
        return False
    return parts[0] in RETIRED_LEGACY_STATIC_NAMESPACE_SEGMENTS


def is_retired_legacy_static_relpath(relpath: str) -> bool:
    """True if a static mount relative path resolves to a retired legacy asset."""
    if is_retired_legacy_static_namespace(relpath):
        return True
    canonical = canonicalize_http_path(f"/static/{relpath}")
    rel = _static_relative_path(canonical)
    if rel is None:
        return False
    normalized = str(PurePosixPath(rel))
    return normalized in LEGACY_SHELL_STATIC_REL_PATHS


def is_allowed_unified_saas_static_relpath(relpath: str) -> bool:
    """Allowlist for production/unified static serving (BLK-P0-06-BYPASS-02)."""
    normalized = str(PurePosixPath(relpath))
    if not normalized:
        return False
    if any(normalized.startswith(prefix) for prefix in UNIFIED_SAAS_STATIC_ALLOW_PREFIXES):
        return True
    return normalized in UNIFIED_SAAS_STATIC_ALLOW_REL_PATHS


def is_retired_legacy_governance_path(path: str) -> bool:
    canonical = canonicalize_http_path(path)
    if (
        canonical.rstrip("/") in LEGACY_GOVERNANCE_PAGE_PATHS
        or canonical in LEGACY_GOVERNANCE_PAGE_PATHS
    ):
        return True
    if canonical in LEGACY_GOVERNANCE_STATIC_PATHS:
        return True
    rel = _static_relative_path(canonical)
    if rel is not None and is_retired_legacy_static_relpath(rel):
        return True
    return False


def legacy_shell_disk_path(relpath: str) -> Path | None:
    """Map community-mode /static relative paths to on-disk legacy template files."""
    normalized = str(PurePosixPath(relpath))
    if normalized in _LEGACY_HTML_FILENAMES:
        return LEGACY_GOVERNANCE_SHELL_DIR / normalized
    if normalized == "js/app.js":
        return LEGACY_TEMPLATES_ROOT / "assets" / "js" / "app.js"
    if normalized == "js/i18n.js":
        return LEGACY_TEMPLATES_ROOT / "assets" / "js" / "i18n.js"
    if normalized == "css/app.css":
        return LEGACY_TEMPLATES_ROOT / "assets" / "css" / "app.css"
    return None


def legacy_governance_retired_response() -> HTMLResponse:
    return HTMLResponse(
        status_code=404,
        content=(
            "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
            "<title>WhitePact workspace</title></head><body>"
            "<h1>This legacy ResponsibleAI dashboard page is retired</h1>"
            "<p>Use the WhitePact workspace at <a href='/dashboard'>/dashboard</a> "
            "with your verified session. Static API keys in the browser are not supported.</p>"
            "</body></html>"
        ),
        headers={"X-WhitePact-Legacy-Frontend": "retired"},
    )


class UnifiedSaaSLegacyRetirementMiddleware(BaseHTTPMiddleware):
    """Block legacy governance HTML before StaticFiles serves shell assets."""

    async def dispatch(self, request: Request, call_next) -> Response:
        from responsibleai.dashboard.config import get_settings

        settings = get_settings()
        if not unified_saas_legacy_retirement_enforced(settings):
            return await call_next(request)
        path = request.url.path
        if is_retired_legacy_governance_path(path):
            return legacy_governance_retired_response()
        return await call_next(request)


class UnifiedSaasStaticFiles(StaticFiles):
    """StaticFiles with unified allowlist and no retired legacy under /static."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        from responsibleai.dashboard.config import get_settings

        settings = get_settings()
        if unified_saas_legacy_retirement_enforced(settings):
            if is_retired_legacy_static_relpath(path):
                return legacy_governance_retired_response()
            if not is_allowed_unified_saas_static_relpath(path):
                return legacy_governance_retired_response()
        return await super().get_response(path, scope)

    def lookup_path(self, path: str):  # type: ignore[override]
        from responsibleai.dashboard.config import get_settings

        settings = get_settings()
        if unified_saas_legacy_retirement_enforced(settings):
            if is_retired_legacy_static_relpath(path):
                return "", None
            if not is_allowed_unified_saas_static_relpath(path):
                return "", None
        full_path, stat_result = super().lookup_path(path)
        if stat_result is not None:
            return full_path, stat_result
        if not unified_saas_legacy_retirement_enforced(settings):
            disk = legacy_shell_disk_path(path)
            if disk is not None and disk.is_file():
                return str(disk), os.stat(disk)
        return "", None
