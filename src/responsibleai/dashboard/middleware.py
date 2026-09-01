"""FastAPI middleware: request ID, logging, security headers, auth."""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from responsibleai.dashboard.logging_config import get_logger, set_request_id

logger = get_logger("middleware")

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


# Enterprise Readiness Phase 18/19 (public-API fuzz/abuse audit): no
# request-body-size cap existed anywhere in this app -- confirmed by
# grep, not assumed. A reverse proxy in front of a real deployment
# (DEPLOYMENT.md's nginx config) may already enforce one, but this
# app had no defense-in-depth of its own, meaning a self-hosted
# deployment run without such a proxy (or any deployment, before the
# proxy's own limit is reached) had no bound on how much of an
# oversized request body Starlette would buffer into memory before a
# Pydantic model's own field-level max_length ever got a chance to run.
# 10 MB comfortably covers every real request shape this API accepts
# (the largest, `governance/approve` arguments payloads and consent
# `scope_description`/`purpose` fields, are bounded by Pydantic's own
# `max_length` at a few KB each) with generous headroom.
MAX_REQUEST_BODY_BYTES = 10 * 1024 * 1024


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Rejects a request whose declared `Content-Length` exceeds
    `MAX_REQUEST_BODY_BYTES` with 413, before any route handler or
    Pydantic validation runs.

    Scoped limitation, stated honestly: this checks the `Content-Length`
    header, which covers every normal JSON-body request this API's own
    clients send. It does NOT defend against a chunked-transfer-encoded
    request that omits `Content-Length` and streams an unbounded body —
    closing that fully would mean wrapping the ASGI `receive` channel to
    count bytes as they arrive, a larger change than this pass makes.
    Real-world deployments still have their reverse proxy's own limit as
    a second layer; this middleware is the application-level
    defense-in-depth `DEPENDENCY_RISK_REGISTER.md`'s "no dedicated
    request-size fuzz coverage" gap named as missing, not the only
    layer this system now relies on.
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
