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
from typing import TYPE_CHECKING

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, Response

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

LEGACY_GOVERNANCE_STATIC_PATHS: frozenset[str] = frozenset(
    {f"/static/{name}" for name in _LEGACY_HTML_FILENAMES}
    | {"/static/js/app.js", "/static/css/app.css"}
)


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


def is_retired_legacy_governance_path(path: str) -> bool:
    normalized = path.rstrip("/") or "/"
    if normalized in LEGACY_GOVERNANCE_PAGE_PATHS:
        return True
    return path in LEGACY_GOVERNANCE_STATIC_PATHS


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
