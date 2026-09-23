# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""FastAPI middleware: request ID, logging, security headers, auth."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from responsibleai.dashboard.logging_config import get_logger, set_request_id

logger = get_logger("middleware")


class AuthFailureLimiter:
    """IP-keyed limiter on failed Bearer-auth attempts.

    Dashboard slowapi buckets by presented Bearer token when one is present, so
    credential guessing with distinct tokens never accumulates. This limiter is
    IP-keyed and independent of the token tried.

    Production attaches DurableIdentityRateLimiter (identity_rate_counters).
    That is the same atomic PostgreSQL counter used by Layer 2 identity
    security; it is not a second authority. Process-local memory is only a
    non-production fallback when no durable backend is attached.

    Generic slowapi per-route ceilings remain convenience DoS padding and are
    not the failed-auth security control.
    """

    def __init__(self, max_failures: int, window_seconds: float) -> None:
        self._max_failures = max_failures
        self._window_seconds = window_seconds
        self._failures: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()
        self._durable: Any = None
        self._require_durable = False

    def attach_durable(self, limiter: Any, *, require_durable: bool) -> None:
        self._durable = limiter
        self._require_durable = require_durable

    def detach_durable(self) -> None:
        self._durable = None
        self._require_durable = False

    def _protection_unavailable(self) -> HTTPException:
        return HTTPException(
            status_code=503,
            detail="Abuse protection is unavailable. Try again later.",
        )

    def _prune(self, key: str, now: float) -> list[float]:
        attempts = [t for t in self._failures.get(key, []) if now - t < self._window_seconds]
        self._failures[key] = attempts
        return attempts

    def _durable_key(self, key: str) -> str:
        return f"rest-auth-fail:{key}"

    async def is_blocked(self, key: str) -> bool:
        if self._durable is not None:
            from responsibleai.enterprise.errors import EnterpriseError

            try:
                count = await self._durable.current_count(
                    self._durable_key(key), window_seconds=self._window_seconds
                )
            except EnterpriseError as exc:
                if exc.code == "IDENTITY_PROTECTION_UNAVAILABLE":
                    raise self._protection_unavailable() from exc
                raise
            return count >= self._max_failures
        if self._require_durable:
            raise self._protection_unavailable()
        async with self._lock:
            now = asyncio.get_running_loop().time()
            return len(self._prune(key, now)) >= self._max_failures

    async def record_failure(self, key: str) -> None:
        if self._durable is not None:
            from responsibleai.enterprise.errors import EnterpriseError

            try:
                await self._durable.check(
                    self._durable_key(key),
                    limit=self._max_failures,
                    window_seconds=self._window_seconds,
                )
            except EnterpriseError as exc:
                if exc.code == "RATE_LIMITED":
                    return
                if exc.code == "IDENTITY_PROTECTION_UNAVAILABLE":
                    raise self._protection_unavailable() from exc
                raise
            return
        if self._require_durable:
            raise self._protection_unavailable()
        async with self._lock:
            now = asyncio.get_running_loop().time()
            self._prune(key, now).append(now)


# The dashboard's static pages (static/index.html etc.) load Tailwind and
# Chart.js from CDN and use inline <style>/<script> blocks plus onclick=
# attribute handlers rather than a build step — so script-src/style-src
# need 'unsafe-inline' until that markup is refactored to addEventListener
# with nonces. Documented here rather than silently narrowed later: this
# CSP still meaningfully restricts framing, object/embed, and outbound
# connections even with that relaxation.
_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)

# The compiled WhitePact customer application has no inline JavaScript or
# styles and loads no CDN resources.  Give it a substantially tighter policy
# than the legacy operator pages, which still require the compatibility policy
# above until their inline handlers are removed.
_WHITEPACT_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)

_WHITEPACT_PAGE_PATHS = {
    "/",
    "/signup",
    "/login",
    "/verify-email",
    "/forgot-password",
    "/reset-password",
    "/onboarding",
    "/accept-invitation",
    "/dashboard",
    "/about",
    "/contact",
    "/docs",
    "/privacy",
    "/terms",
    "/trust",
    "/billing/success",
    "/billing/cancelled",
}


def _is_whitepact_spa_path(path: str) -> bool:
    return (
        path in _WHITEPACT_PAGE_PATHS
        or path.startswith("/dashboard/")
        or path.startswith("/static/whitepact/")
    )


# Safe to set at the application layer even though TLS termination is the
# deployer's job (DEPLOYMENT.md's nginx config): browsers ignore
# Strict-Transport-Security on plain-HTTP responses per spec, so this is a
# no-op when accessed directly over HTTP and a real defense-in-depth layer
# once a proxy terminates TLS in front of it.
_SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Cache-Control": "no-store",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
    "Content-Security-Policy": _CONTENT_SECURITY_POLICY,
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
}


MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests by Content-Length before handlers run.

    Chunked bodies without Content-Length are out of this defense-in-depth
    check; reverse proxies remain a second layer.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                length = int(content_length)
            except ValueError:
                length = None
            if length is not None and length > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(
                    status_code=413,
                    content={
                        "error": "payload_too_large",
                        "message": (
                            f"Request body exceeds the {MAX_REQUEST_BODY_BYTES} byte limit."
                        ),
                    },
                )
        return await call_next(request)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a short UUID to every request and echo it in the response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        rid = str(uuid.uuid4())[:8]
        set_request_id(rid)
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Inject security-hardening response headers on every response."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        for header, value in _SECURITY_HEADERS.items():
            response.headers[header] = value
        if _is_whitepact_spa_path(request.url.path):
            response.headers["Content-Security-Policy"] = _WHITEPACT_CONTENT_SECURITY_POLICY
        if request.url.path.startswith("/static/whitepact/assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        elif request.url.path in {"/robots.txt", "/sitemap.xml"}:
            response.headers["Cache-Control"] = "public, max-age=3600"
        return response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with method, path, status, and duration."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        rid = getattr(request.state, "request_id", "?")
        logger.info(
            "request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration_ms=duration_ms,
            request_id=rid,
            client=request.client.host if request.client else "unknown",
        )
        response.headers["X-Response-Time-Ms"] = str(duration_ms)
        return response


def build_api_key_dependency(api_keys: list[str], enabled: bool):
    """Return a FastAPI dependency that enforces API key auth."""

    async def _check_key(request: Request) -> None:
        if not enabled or not api_keys:
            return
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail="Missing or malformed Authorization header. Use: Bearer <api-key>",
                headers={"WWW-Authenticate": "Bearer"},
            )
        key = auth[len("Bearer ") :]
        if key not in api_keys:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key.",
                headers={"WWW-Authenticate": "Bearer"},
            )

    return _check_key


async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    logger.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc=str(exc),
        path=request.url.path,
        request_id=rid,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred.",
            "request_id": rid,
        },
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    rid = getattr(request.state, "request_id", "?")
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = {
            **exc.detail,
            "status_code": exc.status_code,
            "request_id": rid,
        }
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "status_code": exc.status_code,
            "request_id": rid,
        },
        headers=getattr(exc, "headers", None),
    )


class RestoreReadinessMiddleware(BaseHTTPMiddleware):
    """Enforce restore readiness admission gate on all incoming HTTP traffic.

    Consequential HTTP mutations and operations are blocked (503 Service Unavailable)
    whenever the system is in RESTORE_PENDING, RECONCILING, or FAILED state.
    Only health check probes and narrow operator recovery endpoints remain admitted.
    """

    ALLOWED_RECOVERY_PATHS = {
        "/health",
        "/healthz",
        "/readyz",
        "/livez",
        "/api/health",
        "/api/restore/status",
        "/api/v1/restore/status",
        "/api/restore/reconcile",
        "/api/v1/restore/reconcile",
        "/robots.txt",
        "/sitemap.xml",
    }

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        from responsibleai.data_governance.backup_defense import (
            RestoreReadinessState,
            get_restore_readiness_gate,
        )

        gate = get_restore_readiness_gate()
        current_state = gate.state
        if current_state != RestoreReadinessState.READY:
            path = request.url.path
            if path not in self.ALLOWED_RECOVERY_PATHS:
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": "restore_quarantine",
                        "message": (
                            f"Operational traffic blocked: system is in {current_state.value} "
                            "state pending restore reconciliation."
                        ),
                        "status": current_state.value,
                    },
                    headers={"Retry-After": "10"},
                )

        return await call_next(request)
