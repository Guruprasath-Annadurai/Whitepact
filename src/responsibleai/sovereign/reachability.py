# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unauthenticated reachability probe for ``whitepact connect`` and ``doctor``.

The probe never sends credentials and never stores them. A response only
distinguishes a verified health check from a saved-but-unverified context.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

_METADATA_HOSTS = frozenset(
    {
        "169.254.169.254",
        "metadata.google.internal",
        "metadata.google.internal.",
    }
)


@dataclass(frozen=True)
class ProbeResult:
    ok: bool
    kind: str
    message: str
    status_code: int | None = None

    def as_check(self) -> dict[str, str]:
        return {
            "name": "reachability",
            "result": "PASS" if self.ok else "FAIL",
            "detail": self.message,
            "kind": self.kind,
        }


def validate_developer_base_url(url: str) -> str:
    """Accept an http(s) developer URL. Reject embedded secrets and metadata hosts."""
    raw = url.strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must be http or https and include a host.")
    if parsed.username or parsed.password:
        raise ValueError(
            "URL must not embed credentials. WhitePact does not store tokens in the context file."
        )
    host = parsed.hostname.lower()
    if host in _METADATA_HOSTS:
        raise ValueError("Refusing to probe a cloud metadata address.")
    return raw.rstrip("/")


def _kind_for_status(status_code: int) -> ProbeResult:
    if status_code == 200:
        return ProbeResult(
            ok=True,
            kind="ok",
            status_code=200,
            message="VERIFIED CONNECTION — /api/health returned HTTP 200. This is not authorization.",
        )
    if status_code == 401:
        message = (
            "HTTP 401 from /api/health. The process answered, but this URL is not a verified "
            "WhitePact health check. Context can be saved unverified. No credential was sent."
        )
        kind = "http_401"
    elif status_code == 403:
        message = (
            "HTTP 403 from /api/health. The endpoint refused the check. "
            "Confirm the base URL. No credential was sent."
        )
        kind = "http_403"
    elif status_code == 404:
        message = (
            "HTTP 404 from /api/health. Confirm --url is the WhitePact server origin, "
            "not a path underneath it."
        )
        kind = "http_404"
    elif status_code == 429:
        message = (
            "HTTP 429 from /api/health. The endpoint rate-limited the check. "
            "Wait before retrying. The probe does not keep calling."
        )
        kind = "http_429"
    elif status_code >= 500:
        message = (
            f"HTTP {status_code} from /api/health. The server is up but not healthy. "
            "Retry later. The probe was not repeated."
        )
        kind = "http_5xx"
    else:
        message = (
            f"HTTP {status_code} from /api/health is not a verified WhitePact health response."
        )
        kind = "http_other"
    return ProbeResult(ok=False, kind=kind, status_code=status_code, message=message)


def probe_base_url(
    base_url: str,
    *,
    timeout: float = 5.0,
    transport: httpx.BaseTransport | None = None,
) -> ProbeResult:
    """GET ``{base}/api/health`` once, without an Authorization header."""
    try:
        url = validate_developer_base_url(base_url)
    except ValueError as exc:
        return ProbeResult(ok=False, kind="invalid", message=str(exc))
    target = f"{url}/api/health"
    host = urlsplit(url).hostname or url
    try:
        with httpx.Client(timeout=timeout, follow_redirects=False, transport=transport) as client:
            response = client.get(target)
    except httpx.TimeoutException:
        return ProbeResult(
            ok=False,
            kind="timeout",
            message=f"Timed out after {timeout:g}s contacting {host}. Check that the server is running.",
        )
    except httpx.ConnectError as exc:
        text = str(exc).lower()
        if "name or service not known" in text or "nodename" in text or "getaddrinfo" in text:
            return ProbeResult(
                ok=False,
                kind="dns",
                message=f"DNS lookup failed for {host}. Check the hostname.",
            )
        return ProbeResult(
            ok=False,
            kind="network",
            message=f"Could not connect to {host}. Check the URL and that the server is running.",
        )
    except httpx.HTTPError:
        return ProbeResult(
            ok=False,
            kind="network",
            message=f"Network error contacting {host}. No credential was sent.",
        )
    return _kind_for_status(response.status_code)
