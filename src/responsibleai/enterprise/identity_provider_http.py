# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Provider-independent HTTP callback adapter.

This adapter can open a verification session at an enrolled provider and
validate an HMAC callback. It does not select, purchase, or simulate a
commercial identity vendor, and it is not a compatibility claim for any
vendor's published API or signing scheme. Missing enrollment fails closed.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import urllib.error
import urllib.request
from datetime import UTC, datetime
from typing import Any

from responsibleai.enterprise.errors import (
    PROVIDER_NOT_ENROLLED,
    PROVIDER_SIGNATURE_INVALID,
    forbidden,
)
from responsibleai.environment import is_production


class _RedirectRejectedError(Exception):
    pass


class _RejectRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise _RedirectRejectedError(str(newurl))


def _timeout_from_env() -> float:
    raw = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_TIMEOUT_SECONDS", "10")
    try:
        value = float(raw)
    except ValueError:
        return 10
    return min(30.0, max(1.0, value))


class HttpCallbackIdentityProvider:
    """Call an enrolled provider's session API. Never marks a subject verified."""

    def __init__(
        self,
        *,
        name: str,
        base_url: str,
        api_token: str,
        webhook_secret: str,
        allow_insecure: bool = False,
        timeout_seconds: float = 10,
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._secret = webhook_secret.encode("utf-8")
        self._allow_insecure = allow_insecure
        self._timeout = timeout_seconds

    @classmethod
    def from_env(cls) -> HttpCallbackIdentityProvider:
        name = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_NAME", "").strip()
        base_url = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_BASE_URL", "").strip()
        token = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_API_TOKEN", "").strip()
        secret = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_WEBHOOK_SECRET", "").strip()
        allow_insecure = os.environ.get("WHITEPACT_IDENTITY_PROVIDER_ALLOW_INSECURE") == "1"
        if not name or not base_url or not token or not secret:
            raise forbidden(
                PROVIDER_NOT_ENROLLED,
                "Identity provider enrollment is incomplete.",
            )
        if name == "hmac-reference":
            raise forbidden(
                PROVIDER_NOT_ENROLLED,
                "The reference adapter is not an enrolled identity provider.",
            )
        if is_production() and allow_insecure:
            raise forbidden(
                PROVIDER_NOT_ENROLLED,
                "Insecure provider transport is not allowed in production.",
            )
        if base_url.startswith("http://") and not allow_insecure:
            raise forbidden(
                PROVIDER_NOT_ENROLLED,
                "Identity provider URL must use HTTPS.",
            )
        if not (base_url.startswith("https://") or base_url.startswith("http://")):
            raise forbidden(PROVIDER_NOT_ENROLLED, "Identity provider URL is invalid.")
        return cls(
            name=name,
            base_url=base_url,
            api_token=token,
            webhook_secret=secret,
            allow_insecure=allow_insecure,
            timeout_seconds=_timeout_from_env(),
        )

    def start_session(self, *, subject_id: str, return_url: str | None) -> dict[str, str]:
        body = json.dumps({"subject_id": subject_id, "return_url": return_url or ""}).encode(
            "utf-8"
        )
        request = urllib.request.Request(
            self._base_url + "/sessions",
            data=body,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        opener = urllib.request.build_opener(_RejectRedirects())
        try:
            with opener.open(request, timeout=self._timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except _RedirectRejectedError as exc:
            raise forbidden(
                PROVIDER_NOT_ENROLLED, "Identity provider session request was redirected."
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise forbidden(
                PROVIDER_NOT_ENROLLED, "Identity provider session request failed."
            ) from exc
        if not isinstance(payload, dict):
            raise forbidden(PROVIDER_NOT_ENROLLED, "Identity provider session response is invalid.")
        session_id = str(payload.get("session_id") or "")
        hosted_url = str(payload.get("hosted_url") or "")
        if not session_id or not hosted_url:
            raise forbidden(
                PROVIDER_NOT_ENROLLED, "Identity provider did not return a hosted session."
            )
        if hosted_url.startswith("http://") and not self._allow_insecure:
            raise forbidden(PROVIDER_NOT_ENROLLED, "Identity provider hosted URL must use HTTPS.")
        return {
            "provider": self.name,
            "session_id": session_id,
            "subject_id": subject_id,
            "hosted_url": hosted_url,
        }

    def verify_webhook(self, *, payload: bytes, signature: str, timestamp: str) -> dict[str, Any]:
        expected = hmac.new(self._secret, payload + timestamp.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature or ""):
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider webhook signature is invalid.")
        try:
            ts = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError as exc:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider timestamp is invalid.") from exc
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        if abs((datetime.now(UTC) - ts.astimezone(UTC)).total_seconds()) > 300:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider webhook timestamp is stale.")
        body = json.loads(payload.decode("utf-8"))
        if not isinstance(body, dict) or "event_id" not in body:
            raise forbidden(PROVIDER_SIGNATURE_INVALID, "Provider event is malformed.")
        return body
