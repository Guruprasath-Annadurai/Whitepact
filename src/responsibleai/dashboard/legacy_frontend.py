# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Retire the legacy ResponsibleAI HTML shell (BLK-P0-06).

The modern WhitePact React SPA is the only supported enterprise workspace UI.
Legacy pages used ``localStorage['rai_api_key']`` via ``static/js/app.js`` and
must not remain reachable as an alternate governance surface when unified SaaS
mode is enforced.
"""

from __future__ import annotations

import os
from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import unquote

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response
from starlette.staticfiles import StaticFiles

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings

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

# On-disk directory for retired shell HTML (not under the public static mount root).
LEGACY_GOVERNANCE_STATIC_SUBDIR = "_retired_legacy_governance"

# Static assets that only exist to power the legacy shell.
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

# Canonical inventory for regression tests (relative to /static/).
RETIRED_LEGACY_STATIC_INVENTORY: frozenset[str] = frozenset(LEGACY_GOVERNANCE_STATIC_PATHS)


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
    """Normalize URL path segments (slashes, dot segments) without filesystem access.

    Repeated slashes collapse; ``.`` is ignored; ``..`` pops one segment but cannot
    escape above the root (``/``). Percent-encoded segments are decoded once when
    ``decode`` is True (Starlette usually provides a decoded ``request.url.path``;
    callers may pass raw paths for tests).
    """
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
    """Return path under ``/static/`` if ``canonical_path`` is a static URL."""
    if not canonical_path.startswith("/static/"):
        if canonical_path == "/static":
            return ""
        return None
    rel = canonical_path.removeprefix("/static/").lstrip("/")
    return rel


def is_retired_legacy_static_relpath(relpath: str) -> bool:
    """True if a static mount relative path resolves to a retired legacy asset."""
    canonical = canonicalize_http_path(f"/static/{relpath}")
    rel = _static_relative_path(canonical)
    if rel is None:
        return False
    normalized = str(PurePosixPath(rel))
    return normalized in LEGACY_SHELL_STATIC_REL_PATHS


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
    """StaticFiles that cannot serve retired legacy shell assets in unified mode."""

    def __init__(self, *args, legacy_html_dir: str | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._legacy_html_dir = legacy_html_dir

    def lookup_path(self, path: str):  # type: ignore[override]
        from responsibleai.dashboard.config import get_settings

        settings = get_settings()
        if unified_saas_legacy_retirement_enforced(settings):
            if is_retired_legacy_static_relpath(path):
                return "", None
        full_path, stat_result = super().lookup_path(path)
        if stat_result is not None:
            return full_path, stat_result
        if (
            self._legacy_html_dir
            and not unified_saas_legacy_retirement_enforced(settings)
            and str(PurePosixPath(path)) in LEGACY_SHELL_STATIC_REL_PATHS
        ):
            import os

            joined = os.path.join(self._legacy_html_dir, path)
            try:
                return joined, os.stat(joined)
            except OSError:
                pass
        return "", None

    async def get_response(self, path: str, scope):  # type: ignore[override]
        from responsibleai.dashboard.config import get_settings

        settings = get_settings()
        if unified_saas_legacy_retirement_enforced(settings):
            if is_retired_legacy_static_relpath(path):
                return legacy_governance_retired_response()
        return await super().get_response(path, scope)
