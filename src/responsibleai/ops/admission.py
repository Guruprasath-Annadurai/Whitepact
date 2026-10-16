# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Per-process admission control: fail fast under overload instead of queueing without bound.

Measured behaviour without it (docs/launch/HTTP_AUTHORIZATION_BENCHMARK.md): at 1,000 concurrent clients 56-77 %
of connections failed and the survivors waited 11-28 s. Waiting that long is worse than refusing: a caller
cannot tell a slow answer from a lost one, and retries pile onto an already saturated worker. This ASGI
middleware caps in-flight HTTP requests per process; the excess get an immediate ``503`` with ``Retry-After``
and no work is started for them.

What it is: a *protective* bound on one process, not a capacity guarantee and not a fairness mechanism (it
does not distinguish tenants). What it is not: a replacement for plan rate limits, which meter per organization.
Liveness/readiness paths are never shed, and long-lived streaming connections are exempt so a handful of SSE
clients cannot exhaust the slots.
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

ASGIApp = Callable[
    [dict[str, Any], Callable[[], Awaitable[Any]], Callable[[Any], Awaitable[None]]],
    Awaitable[None],
]

DEFAULT_EXEMPT_PATHS = frozenset({"/health", "/ready", "/healthz", "/readyz", "/sse"})

_BODY = json.dumps(
    {
        "error": "overloaded",
        "message": "The server is at its concurrency limit. Retry after the indicated delay.",
    }
).encode()


class AdmissionControlMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        max_inflight: int,
        retry_after_seconds: int = 1,
        exempt_paths: Iterable[str] = DEFAULT_EXEMPT_PATHS,
    ) -> None:
        if max_inflight < 0:
            raise ValueError("max_inflight must be >= 0 (0 disables admission control)")
        self.app = app
        self.max_inflight = max_inflight
        self.retry_after = str(max(1, retry_after_seconds))
        self.exempt = frozenset(exempt_paths)
        self.inflight = 0
        self.shed_total = 0

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http" or self.max_inflight == 0 or scope.get("path") in self.exempt:
            await self.app(scope, receive, send)
            return
        # Single event loop, no await between the check and the increment: this is race-free.
        if self.inflight >= self.max_inflight:
            self.shed_total += 1
            await send(
                {
                    "type": "http.response.start",
                    "status": 503,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", self.retry_after.encode()),
                        (b"content-length", str(len(_BODY)).encode()),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": _BODY})
            return
        self.inflight += 1
        try:
            await self.app(scope, receive, send)
        finally:
            self.inflight -= 1
