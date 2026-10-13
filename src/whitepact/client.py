# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""External WhitePact developer client.

Calls the hosted governance HTTP API. Tool execution happens only inside
the server's governed path (``POST /api/v1/governance/tools/call`` and the
approval resume route). This client does not accept an execution grant
and does not run tools locally.

Tenant identity is whatever the authenticated server returns. A caller
supplied organization id is checked against that value and never sent as
authority.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import httpx

_API_PREFIX = "/api/v1"
_SAFE_RETRY_STATUSES = frozenset({429, 502, 503})
_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_CLIENT_PROTOCOL_MAJOR = 1


class WhitePactError(Exception):
    """Base error. ``str(self)`` is safe to show; it does not include secrets."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WhitePactConnectionError(WhitePactError):
    """TCP connection failed. DNS failures use :class:`WhitePactDNSError`."""


class WhitePactDNSError(WhitePactConnectionError):
    """Hostname could not be resolved."""


class WhitePactTimeoutError(WhitePactError):
    """The call exceeded the configured finite timeout and was not retried if unsafe."""


class WhitePactAuthError(WhitePactError):
    """HTTP 401. The credential was missing, rejected, or not sent."""


class WhitePactForbiddenError(WhitePactError):
    """HTTP 403."""


class WhitePactNotFoundError(WhitePactError):
    """HTTP 404. Treated as absence; not proof about another tenant."""


class WhitePactConflictError(WhitePactError):
    """HTTP 409."""


class WhitePactValidationError(WhitePactError):
    """HTTP 422."""


class WhitePactRateLimitError(WhitePactError):
    """HTTP 429."""


class WhitePactServerError(WhitePactError):
    """HTTP 500/502/503 or another 5xx."""


class WhitePactMalformedResponseError(WhitePactError):
    """The server returned a body that is not JSON."""


class WhitePactSchemaError(WhitePactError):
    """JSON parsed, but it does not match the endpoint contract."""


class WhitePactProtocolError(WhitePactError):
    """Server API version is missing or outside the v1 protocol this client speaks."""


class WhitePactTenantError(WhitePactError):
    """Caller organization id disagrees with the authenticated server tenant."""


@dataclass(frozen=True)
class ServerAuthority:
    """Tenant taken from the server, not from the caller."""

    organization_id: str
    api_version: str
    protocol_min_version: str


@dataclass(frozen=True)
class ProtectResult:
    """Outcome of a governed protect call.

    ``executed`` is true only when the server already ran the tool inside
    its execution-grant boundary. The client did not run it.
    """

    decision: str
    executed: bool
    tool: str
    approval_id: str | None
    action_id: str | None
    outcome_status: str | None
    result: dict[str, Any] | None
    raw: dict[str, Any]


def _parse_version(value: str) -> tuple[int, int, int]:
    parts = value.strip().split(".")
    numbers: list[int] = []
    for part in parts[:3]:
        token = part.split("-", 1)[0]
        if not token.isdigit():
            raise ValueError(value)
        numbers.append(int(token))
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2]


def _is_dns_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    return (
        "name or service not known" in text
        or "nodename nor servname" in text
        or "getaddrinfo" in text
        or "temporary failure in name resolution" in text
    )


class WhitePactClient:
    """Synchronous client for the hosted WhitePact governance API.

    Async wrappers are intentionally absent: the repository's external
    developer journey is a script/CLI style client. Unsafe mutations are
    never retried.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_backoff: float = 0.2,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not isinstance(base_url, str) or not base_url.strip():
            raise ValueError("base_url is required.")
        parsed = urlsplit(base_url.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("base_url must be an http or https URL with a host.")
        if parsed.username or parsed.password:
            raise ValueError("base_url must not embed credentials.")
        if not isinstance(api_key, str) or not api_key.strip():
            raise WhitePactAuthError(
                "Authentication is required. Pass api_key. "
                "WhitePact does not read a token from the connect context file."
            )
        if (
            not isinstance(timeout, (int, float))
            or not math.isfinite(float(timeout))
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive finite number of seconds.")
        if max_retries < 0:
            raise ValueError("max_retries must be >= 0.")
        self.base_url = base_url.strip().rstrip("/")
        self.timeout = float(timeout)
        self.max_retries = max_retries
        self.retry_backoff = retry_backoff
        self._api_key = api_key.strip()
        self.server_organization_id: str | None = None
        self.api_version: str | None = None
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            transport=transport,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Accept": "application/json",
            },
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> WhitePactClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _redact(self, text: str) -> str:
        redacted = text.replace(self._api_key, "[redacted]")
        parsed = urlsplit(self.base_url)
        if parsed.password:
            redacted = redacted.replace(parsed.password, "[redacted]")
        return redacted

    def _check_protocol(self, response: httpx.Response) -> None:
        version = response.headers.get("X-API-Version")
        minimum = response.headers.get("X-API-Min-Version")
        if not version or not minimum:
            raise WhitePactProtocolError(
                "Server omitted X-API-Version or X-API-Min-Version. "
                "This client only speaks the WhitePact v1 HTTP protocol."
            )
        try:
            parsed_version = _parse_version(version)
            parsed_min = _parse_version(minimum)
        except ValueError:
            raise WhitePactProtocolError(
                "Server API version headers are not numeric. Refusing to continue."
            ) from None
        if parsed_version[0] != _CLIENT_PROTOCOL_MAJOR or parsed_min[0] > _CLIENT_PROTOCOL_MAJOR:
            raise WhitePactProtocolError(
                f"Server protocol {version} (minimum {minimum}) is not supported. "
                "This client speaks API v1 only."
            )
        self.api_version = version

    def _error_message(self, response: httpx.Response) -> str:
        try:
            body = response.json()
        except ValueError:
            body = None
        detail = ""
        if isinstance(body, dict):
            raw = body.get("message") or body.get("detail") or body.get("error")
            if isinstance(raw, str):
                detail = raw
            elif isinstance(raw, list):
                detail = "validation failed"
        text = detail or f"HTTP {response.status_code}"
        return self._redact(text)[:300]

    def _raise_for_status(self, response: httpx.Response) -> None:
        code = response.status_code
        if code < 400:
            return
        message = self._error_message(response)
        if code == 401:
            raise WhitePactAuthError(
                "Authentication failed (HTTP 401). Check the API key. The key is not included here.",
                status_code=401,
            )
        if code == 403:
            raise WhitePactForbiddenError(f"Forbidden (HTTP 403). {message}", status_code=403)
        if code == 404:
            raise WhitePactNotFoundError(f"Not found (HTTP 404). {message}", status_code=404)
        if code == 409:
            raise WhitePactConflictError(f"Conflict (HTTP 409). {message}", status_code=409)
        if code == 422:
            raise WhitePactValidationError(
                f"Invalid request (HTTP 422). {message}", status_code=422
            )
        if code == 429:
            raise WhitePactRateLimitError(
                "Rate limited (HTTP 429). Wait before retrying. Unsafe calls are not retried.",
                status_code=429,
            )
        if code >= 500:
            raise WhitePactServerError(
                f"Server error (HTTP {code}). If this was a mutation, it was not retried.",
                status_code=code,
            )
        raise WhitePactError(f"HTTP {code}. {message}", status_code=code)

    def _read_json(self, response: httpx.Response) -> Any:
        if not response.content:
            raise WhitePactMalformedResponseError("Server returned an empty body.")
        try:
            return response.json()
        except ValueError as exc:
            raise WhitePactMalformedResponseError(
                "Server returned malformed JSON. The body was not parsed."
            ) from exc

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> Any:
        unsafe = method.upper() in _UNSAFE_METHODS
        attempts = 1 if unsafe else self.max_retries + 1
        last_error: WhitePactError | None = None
        for attempt in range(attempts):
            try:
                response = self._client.request(method, path, json=json_body, params=params)
            except httpx.TimeoutException as exc:
                message = "Timed out contacting WhitePact."
                if unsafe:
                    message += " The mutation was not retried; it may have reached the server."
                    raise WhitePactTimeoutError(message) from exc
                last_error = WhitePactTimeoutError(message)
            except httpx.ConnectError as exc:
                if _is_dns_error(exc):
                    err: WhitePactError = WhitePactDNSError(
                        "DNS lookup failed for the WhitePact host."
                    )
                else:
                    err = WhitePactConnectionError("Could not connect to the WhitePact host.")
                if unsafe:
                    raise err from exc
                last_error = err
            except httpx.HTTPError as exc:
                err = WhitePactConnectionError("Network error contacting WhitePact.")
                if unsafe:
                    raise err from exc
                last_error = err
            else:
                try:
                    self._check_protocol(response)
                    self._raise_for_status(response)
                except (WhitePactRateLimitError, WhitePactServerError) as exc:
                    retryable = (not unsafe) and exc.status_code in _SAFE_RETRY_STATUSES
                    if not retryable or attempt + 1 >= attempts:
                        raise
                    last_error = exc
                except WhitePactError:
                    raise
                else:
                    return self._read_json(response)
            if attempt + 1 < attempts:
                delay = self.retry_backoff * (2**attempt)
                if delay > 0:
                    time.sleep(delay)
        if last_error is None:
            raise WhitePactConnectionError("WhitePact request failed without a response.")
        raise last_error

    def _assert_tenant(self, expected_organization_id: str | None) -> None:
        if expected_organization_id is None:
            return
        if not self.server_organization_id:
            raise WhitePactTenantError(
                "Authenticate before passing an organization id. "
                "The server tenant is authoritative."
            )
        if expected_organization_id != self.server_organization_id:
            raise WhitePactTenantError(
                "Caller organization id does not match the authenticated server tenant. "
                "The client will not send it."
            )

    def authenticate(self) -> ServerAuthority:
        """Read server-authoritative tenant from ``GET /api/v1/governance/policy``."""
        body = self._request("GET", f"{_API_PREFIX}/governance/policy")
        if (
            not isinstance(body, dict)
            or not isinstance(body.get("org_id"), str)
            or not body["org_id"]
        ):
            raise WhitePactSchemaError("Policy response is missing the server organization id.")
        if not isinstance(body.get("rules"), list):
            raise WhitePactSchemaError("Policy response is missing the rules list.")
        self.server_organization_id = body["org_id"]
        if not self.api_version:
            raise WhitePactProtocolError("Authenticated response did not carry an API version.")
        minimum = "1.0.0"
        return ServerAuthority(
            organization_id=body["org_id"],
            api_version=self.api_version,
            protocol_min_version=minimum,
        )

    def _ensure_authority(self, expected_organization_id: str | None) -> None:
        if self.server_organization_id is None:
            self.authenticate()
        self._assert_tenant(expected_organization_id)

    def protect(
        self,
        tool: str,
        arguments: dict[str, Any] | None = None,
        *,
        purpose: str,
        expected_organization_id: str | None = None,
    ) -> ProtectResult:
        """Evaluate and, only if the server authorizes, execute inside WhitePact.

        There is no local execute method and no grant parameter. ALLOW means
        the hosted runtime already consumed its own execution authorization.
        """
        if not tool or not purpose:
            raise WhitePactValidationError("tool and purpose are required.")
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "POST",
            f"{_API_PREFIX}/governance/tools/call",
            json_body={"name": tool, "arguments": dict(arguments or {}), "purpose": purpose},
        )
        if not isinstance(body, dict):
            raise WhitePactSchemaError("Governed tool response was not an object.")
        return _protect_result(tool, body)

    def resolve_approval(
        self,
        approval_id: str,
        outcome: str,
        *,
        notes: str | None = None,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        if outcome not in {"APPROVED", "DENIED"}:
            raise WhitePactValidationError("outcome must be APPROVED or DENIED.")
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "POST",
            f"{_API_PREFIX}/governance/approvals/{approval_id}/resolve",
            json_body={"outcome": outcome, "notes": notes},
        )
        if not isinstance(body, dict) or "approval_id" not in body and "status" not in body:
            raise WhitePactSchemaError("Approval resolve response is missing status.")
        return body

    def execute_approval(
        self,
        approval_id: str,
        *,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        """Resume an already-approved action through the server. Not a local exec."""
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "POST",
            f"{_API_PREFIX}/governance/approvals/{approval_id}/execute",
        )
        if not isinstance(body, dict) or body.get("approval_id") != approval_id:
            raise WhitePactSchemaError("Approval execute response did not echo the approval id.")
        if "result" not in body:
            raise WhitePactSchemaError("Approval execute response is missing result.")
        return body

    def list_evidence(
        self,
        *,
        limit: int = 50,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "GET",
            f"{_API_PREFIX}/governance/evidence",
            params={"limit": limit},
        )
        if not isinstance(body, dict) or not isinstance(body.get("evidence"), list):
            raise WhitePactSchemaError("Evidence list response is missing the evidence array.")
        return body

    def get_attestation(
        self,
        evidence_id: str,
        *,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "GET",
            f"{_API_PREFIX}/governance/evidence/{evidence_id}/attestation",
        )
        if not isinstance(body, dict):
            raise WhitePactSchemaError("Attestation response was not an object.")
        for key in ("evidence_id", "decision", "organization_id"):
            if key not in body:
                raise WhitePactSchemaError(f"Attestation response is missing {key}.")
        if body.get("organization_id") != self.server_organization_id:
            raise WhitePactTenantError(
                "Attestation tenant does not match the authenticated server tenant."
            )
        return body

    def inspect_execution_grant(
        self,
        evidence_id: str,
        *,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        """Read a grant reference from stored evidence. Does not execute it."""
        attestation = self.get_attestation(
            evidence_id, expected_organization_id=expected_organization_id
        )
        listing = self.list_evidence(limit=200, expected_organization_id=expected_organization_id)
        match = next(
            (
                row
                for row in listing["evidence"]
                if isinstance(row, dict) and row.get("evidence_id") == evidence_id
            ),
            None,
        )
        if not isinstance(match, dict):
            raise WhitePactNotFoundError(
                "Evidence attestation exists but the record was not in the tenant evidence list."
            )
        if match.get("organization_id") != self.server_organization_id:
            raise WhitePactTenantError("Evidence tenant does not match the authenticated server.")
        grant = match.get("execution_authorization_id")
        return {
            "evidence_id": evidence_id,
            "organization_id": self.server_organization_id,
            "decision": match.get("decision") or attestation.get("decision"),
            "execution_authorization_id": grant if isinstance(grant, str) and grant else None,
            "grant_present": isinstance(grant, str) and bool(grant),
            "executed_by_client": False,
        }

    def query_audit(
        self,
        *,
        days: int = 7,
        limit: int = 50,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        """Query the audit log. The caller organization id is not sent."""
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "GET",
            f"{_API_PREFIX}/audit-log",
            params={"days": days, "limit": limit},
        )
        if not isinstance(body, dict) or not isinstance(body.get("entries"), list):
            raise WhitePactSchemaError("Audit response is missing entries.")
        if "total" not in body:
            raise WhitePactSchemaError("Audit response is missing total.")
        return body

    def revoke_delegation(
        self,
        identity_id: str,
        *,
        reason: str,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        if not reason:
            raise WhitePactValidationError("A revocation reason is required.")
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "POST",
            f"{_API_PREFIX}/governance/delegations/{identity_id}/revoke",
            json_body={"reason": reason},
        )
        if not isinstance(body, dict) or not isinstance(body.get("revoked_delegation_ids"), list):
            raise WhitePactSchemaError("Revoke response is missing revoked_delegation_ids.")
        return body

    def revoke_passport(
        self,
        passport_id: str,
        *,
        reason: str | None = None,
        expected_organization_id: str | None = None,
    ) -> dict[str, Any]:
        self._ensure_authority(expected_organization_id)
        body = self._request(
            "POST",
            f"{_API_PREFIX}/governance/authority-passports/{passport_id}/revoke",
            json_body={"reason": reason},
        )
        if not isinstance(body, dict):
            raise WhitePactSchemaError("Passport revoke response was not an object.")
        return body


def _protect_result(tool: str, body: dict[str, Any]) -> ProtectResult:
    error = body.get("error")
    if error:
        decision = {
            "governance_denied": "DENY",
            "governance_approval_required": "REQUIRE_APPROVAL",
            "governance_quarantined": "QUARANTINE",
            "governance_unknown_outcome": "UNKNOWN",
            "organization_not_governable": "DENY",
            "governance_authority_unavailable": "DENY",
            "governance_evidence_unavailable": "DENY",
            "governance_blocked": "DENY",
        }.get(str(error), "DENY")
        approval = body.get("approval_id")
        action = body.get("action_id")
        return ProtectResult(
            decision=decision,
            executed=False,
            tool=tool,
            approval_id=approval if isinstance(approval, str) else None,
            action_id=action if isinstance(action, str) else None,
            outcome_status=None,
            result=None,
            raw=body,
        )
    if "result" not in body or "tool" not in body:
        raise WhitePactSchemaError(
            "Governed tool response is neither a decision error nor a server execution result."
        )
    result = body.get("result")
    outcome = body.get("outcome_status")
    return ProtectResult(
        decision="ALLOW",
        executed=True,
        tool=str(body.get("tool") or tool),
        approval_id=None,
        action_id=None,
        outcome_status=outcome if isinstance(outcome, str) else None,
        result=result if isinstance(result, dict) else {"value": result},
        raw=body,
    )
