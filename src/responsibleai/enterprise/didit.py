# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Didit V3 session API and full-payload webhook authentication.

No application UUID is sent to create-session. It is required locally to
authenticate destination/application scope in signed callbacks. No Simple
signature, redirect, or browser callback can authorize an identity.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
from urllib.parse import urlparse

import httpx

from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.environment import is_production


def deny(code="DIDIT_PROOF_INVALID", message="Didit verification proof is invalid."):
    return EnterpriseError(code, message, 403)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _normalize(value):
    if isinstance(value, dict):
        return {k: _normalize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize(v) for v in value]
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON")
        return int(value) if value.is_integer() else value
    return value


def canonical(value):
    return json.dumps(
        _normalize(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


class DiditProvider:
    def __init__(
        self, *, api_key, webhook_secret, workflow_id, application_id, environment, transport=None
    ):
        if environment not in {"sandbox", "live"} or not all(
            (api_key, webhook_secret, workflow_id, application_id)
        ):
            raise deny("PROVIDER_NOT_ENROLLED", "Didit enrollment is incomplete.")
        if is_production() and environment == "sandbox":
            raise deny("PROVIDER_NOT_ENROLLED", "Sandbox identity cannot qualify production.")
        self.environment = environment
        self.name = "didit-sandbox" if environment == "sandbox" else "didit"
        self.workflow_id = workflow_id
        self.application_id = application_id
        self._api_key = api_key
        self._secret = webhook_secret.encode()
        self._transport = transport

    @classmethod
    def from_env(cls):
        return cls(
            api_key=os.environ.get("WHITEPACT_DIDIT_API_KEY", ""),
            webhook_secret=os.environ.get("WHITEPACT_DIDIT_WEBHOOK_SECRET", ""),
            workflow_id=os.environ.get("WHITEPACT_DIDIT_WORKFLOW_ID", ""),
            application_id=os.environ.get("WHITEPACT_DIDIT_APPLICATION_ID", ""),
            environment=os.environ.get("WHITEPACT_DIDIT_ENVIRONMENT", ""),
        )

    def _request(self, method, path, body=None):
        try:
            with httpx.Client(
                transport=self._transport, timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                response = client.request(
                    method,
                    "https://verification.didit.me/v3/" + path,
                    headers={"x-api-key": self._api_key},
                    json=body,
                )
                response.raise_for_status()
                if len(response.content) > 2_000_000:
                    raise ValueError("oversized response")
                data = json.loads(response.content, object_pairs_hook=_pairs)
                if not isinstance(data, dict):
                    raise ValueError("invalid response")
                return data
        except (httpx.HTTPError, ValueError, UnicodeError):
            raise EnterpriseError(
                "DIDIT_UNAVAILABLE",
                "Didit service is unavailable; reconcile the original request.",
                503,
            ) from None

    def start_session(self, *, subject_id, return_url):
        # A callback is navigation only; omit it rather than trust a client URL.
        result = self._request(
            "POST", "session/", {"workflow_id": self.workflow_id, "vendor_data": subject_id}
        )
        session = result.get("session_id")
        url = result.get("url")
        try:
            parsed = urlparse(url) if isinstance(url, str) else None
            port = parsed.port if parsed else None
        except ValueError:
            raise deny() from None
        if (
            not isinstance(session, str)
            or not session
            or len(session) > 64
            or not parsed
            or parsed.scheme != "https"
            or parsed.hostname != "verify.didit.me"
            or parsed.username
            or parsed.password
            or port not in (None, 443)
        ):
            raise deny()
        if (
            result.get("vendor_data", subject_id) != subject_id
            or result.get("workflow_id", self.workflow_id) != self.workflow_id
        ):
            raise deny()
        return {
            "provider": self.name,
            "session_id": session,
            "subject_id": subject_id,
            "hosted_url": url,
        }

    def retrieve_decision(self, session_id):
        # Never permit a supplied session ID to redirect the secret-bearing API call.
        import uuid

        try:
            uuid.UUID(session_id)
        except (ValueError, TypeError, AttributeError):
            raise deny() from None
        return self._request("GET", f"session/{session_id}/decision/")

    def verify_webhook(self, *, payload, signature, timestamp, test_delivery=False):
        try:
            if len(payload) > 2_000_000:
                raise ValueError("oversized payload")
            data = json.loads(payload, object_pairs_hook=_pairs)
            if not isinstance(data, dict):
                raise ValueError("invalid payload")
            stamp = int(timestamp)
            if (
                not str(timestamp).isdigit()
                or type(data.get("timestamp")) is not int
                or data["timestamp"] != stamp
                or abs(time.time() - stamp) > 300
            ):
                raise ValueError("stale timestamp")
            expected = hmac.new(self._secret, canonical(data), hashlib.sha256).hexdigest()
            if (
                not isinstance(signature, str)
                or len(signature) != 64
                or not hmac.compare_digest(signature, expected)
            ):
                raise ValueError("bad signature")
            if (
                data.get("application_id") != self.application_id
                or data.get("environment") != self.environment
            ):
                raise ValueError("wrong destination scope")
            if data.get("webhook_type") not in {"status.updated", "data.updated"}:
                raise ValueError("unsupported event")
            import uuid

            uuid.UUID(data.get("event_id", ""))
            if not test_delivery and data.get("workflow_id") != self.workflow_id:
                raise ValueError("wrong workflow")
            if type(data.get("created_at")) is not int or data["created_at"] > stamp + 300:
                raise ValueError("invalid event time")
            return data
        except (ValueError, TypeError, AttributeError, UnicodeError, OverflowError) as exc:
            raise deny() from exc

    def validate_decision(self, decision, event):
        if any(
            decision.get(k) != event.get(k)
            for k in ("session_id", "workflow_id", "vendor_data", "status")
        ):
            raise deny()
        if (
            decision.get("environment", self.environment) != self.environment
            or decision.get("application_id", self.application_id) != self.application_id
        ):
            raise deny()
        if event["status"] == "Approved":
            # A workflow label or manual final approval alone is not proof of
            # the required documentary, liveness and ownership checks.
            for name in ("id_verifications", "liveness_checks", "face_matches"):
                checks = decision.get(name)
                if (
                    not isinstance(checks, list)
                    or not checks
                    or any(not isinstance(c, dict) or c.get("status") != "Approved" for c in checks)
                ):
                    raise deny(
                        "ASSURANCE_NOT_APPROVED", "Required Didit proofing checks have not passed."
                    )
        return decision
