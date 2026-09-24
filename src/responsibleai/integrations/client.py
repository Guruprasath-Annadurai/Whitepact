# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Framework-agnostic HTTP client for the public Trust Index check
endpoint (`GET /api/trust-index/check`) — the one primitive every
agent-framework integration in this package is built on.

No LangChain/LangGraph/ADK import anywhere in this module. Those
frameworks import `TrustClient`, not the reverse.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

DEFAULT_BASE_URL = "https://responsibleai-dashboard.onrender.com"
DEFAULT_TIMEOUT_SECONDS = 5.0
BASE_URL_ENV_VAR = "RAI_TRUST_API_BASE"
WHITEPACT_TRUST_API_BASE_ENV = "WHITEPACT_TRUST_API_BASE"
WHITEPACT_TRUST_FAILURE_MODE_ENV = "WHITEPACT_TRUST_FAILURE_MODE"
RAI_TRUST_FAILURE_MODE_ENV = "RAI_TRUST_FAILURE_MODE"
# Continuous MCP Trust (v3 authority-layer work): a governed call with a
# provider/model pair does a live Trust Index lookup, but every one of
# those was a real network round-trip in the hot dispatch path -- this
# is the default cache window `TrustClient` serves a fresh-enough result
# from without re-fetching. Not "check once, trust forever": a call
# older than this window forces a live re-fetch attempt before it's
# used, and a fetch that fails is served with `stale=True` rather than
# silently treated as equally fresh (see gateway.py's `_trust_reason()`).
DEFAULT_CACHE_TTL_MINUTES = 10.0


@dataclass(frozen=True)
class TrustCheckResult:
    """The result of checking a model/tool against the public Trust Index."""

    model: str
    provider: str
    known: bool
    trust_score: dict[str, Any] | None
    certified: bool
    has_reported_incidents: bool
    passport_id: str | None = None
    verify_url: str | None = None
    recent_incidents: list[dict[str, Any]] | None = None
    error: str | None = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # True only when a live re-fetch was attempted and failed, and this
    # cached (already-past-TTL) result was served as the fallback --
    # never true for a result that's simply within its cache window.
    # Distinct from `error`: `error` means no real data was ever
    # obtained at all; `stale` means real data exists but couldn't be
    # freshly reverified just now.
    stale: bool = False

    @property
    def overall_score(self) -> float | None:
        return self.trust_score.get("overall") if self.trust_score else None

    def is_stale(self, ttl_minutes: float) -> bool:
        return datetime.now(UTC) - self.checked_at > timedelta(minutes=ttl_minutes)

    def trust_status(self, *, min_score: float = 0.0) -> str:
        """Explicit trust disposition for authorization and MCP responses.

        TRUSTED — known model with score meeting ``min_score``.
        UNTRUSTED — known model below threshold.
        UNKNOWN — provider outage, stale/unverifiable data, or unknown model.
        """
        if self.error is not None and not self.stale:
            return "UNKNOWN"
        if self.stale:
            return "UNKNOWN"
        if not self.known:
            return "UNKNOWN"
        score = self.overall_score if self.overall_score is not None else 0.0
        return "TRUSTED" if score >= min_score else "UNTRUSTED"

    def passes(self, *, min_score: float = 0.0, require_known: bool = False) -> bool:
        """Whether this result satisfies a trust threshold for admission.

        Defaults to fail-closed: UNKNOWN (including provider errors and
        unknown models) never passes. Set ``WHITEPACT_TRUST_FAILURE_MODE=advisory``
        only for non-authorizing advisory surfaces that must not block on
        outages while still reporting ``trust_status=UNKNOWN``.
        """
        status = self.trust_status(min_score=min_score)
        if status == "TRUSTED":
            return True
        if status == "UNTRUSTED":
            return False
        if require_known:
            return False
        mode = (
            (
                os.environ.get(WHITEPACT_TRUST_FAILURE_MODE_ENV)
                or os.environ.get(RAI_TRUST_FAILURE_MODE_ENV)
                or "closed"
            )
            .strip()
            .lower()
        )
        if mode == "advisory":
            # Advisory-only: still not treated as TRUSTED; callers must not
            # equate this with authorization to execute.
            return False
        return False


def _resolve_base_url(base_url: str | None) -> str:
    resolved = (
        base_url
        or os.environ.get(WHITEPACT_TRUST_API_BASE_ENV)
        or os.environ.get(BASE_URL_ENV_VAR)
        or DEFAULT_BASE_URL
    )
    return resolved.rstrip("/")


def _result_from_response(model: str, provider: str, data: dict[str, Any]) -> TrustCheckResult:
    return TrustCheckResult(
        model=data.get("model", model),
        provider=data.get("provider", provider),
        known=bool(data.get("known", False)),
        trust_score=data.get("trust_score"),
        certified=bool(data.get("certified", False)),
        has_reported_incidents=bool(data.get("has_reported_incidents", False)),
        passport_id=data.get("passport_id"),
        verify_url=data.get("verify_url"),
        recent_incidents=data.get("recent_incidents"),
    )


def _result_from_error(model: str, provider: str, exc: Exception) -> TrustCheckResult:
    return TrustCheckResult(
        model=model,
        provider=provider,
        known=False,
        trust_score=None,
        certified=False,
        has_reported_incidents=False,
        error=str(exc),
    )


class TrustClient:
    """Thin client over `GET /api/trust-index/check`.

    Both sync (`check`) and async (`check_async`) entry points are
    provided since LangChain/LangGraph agents run in either mode and the
    integration modules shouldn't each reimplement the HTTP call.

    **Continuous MCP Trust (v3 authority-layer work)**: pass
    `cache_ttl_minutes > 0` to cache results per `(model, provider)` --
    a call within the window is served from cache with no network
    round-trip; a call past the window always attempts a live re-fetch
    first. Default is `0` (caching off, always fetch live) -- the
    pre-existing behavior for every caller that constructs
    `TrustClient()` without opting in (LangChain/LangGraph/ADK
    integrations, `rai_check_trust`); only `mcp/server.py`'s governed
    dispatch path opts in, since that's the hot path making a live
    HTTP call on every governed tool call with a provider/model pair.
    """

    def __init__(
        self,
        base_url: str | None = None,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        cache_ttl_minutes: float = 0.0,
    ) -> None:
        self.base_url = _resolve_base_url(base_url)
        self.timeout = timeout
        self.cache_ttl_minutes = cache_ttl_minutes
        self._cache: dict[tuple[str, str], TrustCheckResult] = {}

    def _cached(self, model: str, provider: str) -> TrustCheckResult | None:
        if self.cache_ttl_minutes <= 0:
            return None
        cached = self._cache.get((model, provider))
        if cached is not None and not cached.is_stale(self.cache_ttl_minutes):
            return cached
        return None

    def _store(self, model: str, provider: str, result: TrustCheckResult) -> None:
        if self.cache_ttl_minutes > 0:
            self._cache[(model, provider)] = result

    def _stale_fallback(self, model: str, provider: str) -> TrustCheckResult | None:
        """The prior cached entry, marked `stale=True` -- served only
        when a live re-fetch was just attempted and failed. Returns
        `None` if nothing was ever cached for this pair at all, in
        which case the caller falls back to `_result_from_error()`
        instead (no real data to fall back to)."""
        cached = self._cache.get((model, provider))
        return replace(cached, stale=True) if cached is not None else None

    def check(self, model: str, provider: str) -> TrustCheckResult:
        cached = self._cached(model, provider)
        if cached is not None:
            return cached
        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.get(
                    f"{self.base_url}/api/trust-index/check",
                    params={"model": model, "provider": provider},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            stale = self._stale_fallback(model, provider)
            return stale if stale is not None else _result_from_error(model, provider, exc)
        result = _result_from_response(model, provider, data)
        self._store(model, provider, result)
        return result

    async def check_async(self, model: str, provider: str) -> TrustCheckResult:
        cached = self._cached(model, provider)
        if cached is not None:
            return cached
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(
                    f"{self.base_url}/api/trust-index/check",
                    params={"model": model, "provider": provider},
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPError as exc:
            stale = self._stale_fallback(model, provider)
            return stale if stale is not None else _result_from_error(model, provider, exc)
        result = _result_from_response(model, provider, data)
        self._store(model, provider, result)
        return result
