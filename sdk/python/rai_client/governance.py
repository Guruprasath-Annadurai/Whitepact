"""WhitePact runtime governance helpers for the HTTP API (SDK P1-03).

Enforcement boundary, stated plainly:

* ``call_tool`` asks the **server** to run a tool. The decision, the single-use grant, the isolated
  execution and the evidence all happen on the server, so a tool that runs through this call cannot
  skip them. A ``governance_denied`` or ``governance_approval_required`` outcome means the tool did
  **not** run.
* This client cannot stop code that never calls it. An agent that reaches a downstream system by
  another route (its own HTTP client, a direct database connection) is outside WhitePact's
  authority, and no result here says otherwise.
* Reading ``denied`` or ``requires_approval`` is a convenience for the caller. Honouring it is the
  caller's responsibility; nothing in this process enforces it.

See ``ENFORCEMENT_BOUNDARY.md`` and ``docs/launch/ENFORCEMENT_PATH_MATRIX.md``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from .transport import validate_base_url, validate_timeout


def _resource_id(value: str) -> str:
    """Bind an opaque identifier to one route segment; never normalize it."""
    if (
        not isinstance(value, str)
        or not value
        or value in (".", "..")
        or any(
            c.isspace()
            or ord(c) < 32
            or 127 <= ord(c) <= 159
            or 0xD800 <= ord(c) <= 0xDFFF
            or c in "/\\?#%"
            for c in value
        )
    ):
        raise ValueError("Invalid resource identifier")
    return quote(value, safe="")


class GovernanceRequestError(RuntimeError):
    """The server did not return a governance answer (non-2xx, or a body that is not a JSON object).

    This is deliberately an exception and not an outcome: a 401, 403, 429 or 5xx carries no ``denied``
    or ``requires_approval`` flag, so a caller testing only those flags would read it as "not blocked".
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"governance request failed [{status_code}]: {detail}")
        self.status_code = status_code
        self.detail = detail


@dataclass(frozen=True)
class GovernanceToolOutcome:
    """Parsed result of a governed tool call.

    ``completed`` requires a result envelope with no contradictory or uncertainty marker. The absence of
    ``denied`` or ``requires_approval`` is NOT permission; check ``completed``.
    """

    raw: dict[str, Any]

    @property
    def completed(self) -> bool:
        return self._completed(0)

    def _completed(self, depth: int) -> bool:
        if depth >= 128:
            return False
        if not isinstance(self.raw, dict) or "result" not in self.raw or "error" in self.raw:
            return False
        for field in (
            "reconciliation_required",
            "denied",
            "requires_approval",
            "quarantined",
            "failed",
            "pending",
            "is_error",
            "isError",
        ):
            if field in self.raw and self.raw[field] is not False:
                return False
        for field in ("status", "outcome_status"):
            if field in self.raw:
                value = self.raw[field]
                if field == "outcome_status" and value is None:
                    continue  # Canonical legacy response has no durable outcome status.
                if value != "SUCCEEDED":
                    return False
        if "decision" in self.raw and self.raw["decision"] not in ("ALLOW", "ALLOW_WITH_REDACTION"):
            return False
        result = self.raw["result"]
        if isinstance(result, dict):
            if "error" in result or any(
                field in result and result[field] is not False for field in ("is_error", "isError")
            ):
                return False
            if any(
                field in result
                for field in (
                    "result",
                    "status",
                    "outcome_status",
                    "decision",
                    "reconciliation_required",
                    "denied",
                    "requires_approval",
                    "quarantined",
                    "failed",
                    "pending",
                )
            ):
                return GovernanceToolOutcome(result)._completed(depth + 1)
        return True

    @property
    def requires_approval(self) -> bool:
        return (
            self.raw.get("error") == "governance_approval_required"
            or self.raw.get("decision") == "REQUIRE_APPROVAL"
        )

    @property
    def approval_id(self) -> str | None:
        return self.raw.get("approval_id")

    @property
    def denied(self) -> bool:
        return self.raw.get("error") == "governance_denied" or self.raw.get("decision") in (
            "DENY",
            "DENIED",
        )

    @property
    def quarantined(self) -> bool:
        return (
            self.raw.get("error") == "governance_quarantined"
            or self.raw.get("decision") == "QUARANTINE"
        )

    @property
    def reconciliation_required(self) -> bool:
        return self._reconciliation_required(0)

    def _reconciliation_required(self, depth: int) -> bool:
        if depth >= 128:
            return True  # Malformed/deep response cannot establish a certain outcome.
        return (
            self.raw.get("status") == "UNKNOWN"
            or self.raw.get("outcome_status") == "UNKNOWN"
            or self.raw.get("error") == "governance_unknown_outcome"
            or self.raw.get("reconciliation_required") is True
            or (
                isinstance(self.raw.get("result"), dict)
                and GovernanceToolOutcome(self.raw["result"])._reconciliation_required(depth + 1)
            )
        )


class GovernanceRuntimeClient:
    """Bearer-authenticated governance runtime surface (approvals, tools, evidence)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8765",
        timeout: float = 30.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        validate_base_url(base_url, api_key)
        validate_timeout(timeout)
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout
        self._transport = transport  # tests only; production uses the default transport

    @asynccontextmanager
    async def _client(self) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            try:
                yield client
            except httpx.RequestError as exc:
                # Preserve HTTPX timeout/transport classification, not credential-bearing
                # request metadata or an unsafe provider exception chain. Never retry here.
                message = str(exc).replace(self._key, "[REDACTED]") if self._key else str(exc)
                # asynccontextmanager is entered while the original exception is active;
                # replacing it would retain that original in __context__. Scrub the
                # HTTPX error in place instead, retaining its exact subclass.
                exc.args = (message,)
                exc._request = None
                exc.__context__ = None
                exc.__cause__ = None
                raise exc from None

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base}/api/{path.lstrip('/')}"

    def _parse_response(self, resp: httpx.Response) -> dict[str, Any]:
        if not resp.is_success:
            detail = resp.text.replace(self._key, "[REDACTED]") if self._key else resp.text
            raise GovernanceRequestError(resp.status_code, detail[:200])
        try:
            body = resp.json()
        except ValueError:
            raise GovernanceRequestError(resp.status_code, "response is not JSON") from None
        if not isinstance(body, dict):
            raise GovernanceRequestError(resp.status_code, "response is not a JSON object")
        return body

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        *,
        purpose: str = "sdk-governance",
    ) -> GovernanceToolOutcome:
        async with self._client() as client:
            resp = await client.post(
                self._url("v1/governance/tools/call"),
                headers=self._headers(),
                json={"name": name, "arguments": arguments or {}, "purpose": purpose},
            )
        return GovernanceToolOutcome(raw=self._parse_response(resp))

    async def revoke_delegation(self, identity_id: str, *, reason: str) -> dict[str, Any]:
        identity_id = _resource_id(identity_id)
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/delegations/{identity_id}/revoke"),
                headers=self._headers(),
                json={"reason": reason},
            )
            return self._parse_response(resp)

    async def get_policy(self) -> dict[str, Any]:
        """Read server-configured tenant policy; availability is not execution authority."""
        async with self._client() as client:
            resp = await client.get(self._url("governance/policy"), headers=self._headers())
            return self._parse_response(resp)

    async def list_approvals(self, status: str | None = None) -> dict[str, Any]:
        params = {"status": status} if status else None
        async with self._client() as client:
            resp = await client.get(
                self._url("governance/approvals"),
                headers=self._headers(),
                params=params,
            )
            return self._parse_response(resp)

    async def resolve_approval(
        self,
        approval_id: str,
        outcome: str,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        approval_id = _resource_id(approval_id)
        body: dict[str, Any] = {"outcome": outcome}
        if notes is not None:
            body["notes"] = notes
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/resolve"),
                headers=self._headers(),
                json=body,
            )
            return self._parse_response(resp)

    async def execute_approval(self, approval_id: str) -> dict[str, Any]:
        approval_id = _resource_id(approval_id)
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/execute"),
                headers=self._headers(),
                json={},
            )
            return self._parse_response(resp)

    async def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        """Legacy detail route; current backend lacks this endpoint. Use get_attestation."""
        evidence_id = _resource_id(evidence_id)
        async with self._client() as client:
            resp = await client.get(
                self._url(f"governance/evidence/{evidence_id}"),
                headers=self._headers(),
            )
            return self._parse_response(resp)

    async def list_evidence(self, *, limit: int = 50) -> dict[str, Any]:
        """Return the backend's bounded listing, not a complete-history claim."""
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
            raise ValueError("Evidence limit must be an integer from 1 to 200")
        async with self._client() as client:
            resp = await client.get(
                self._url("governance/evidence"), headers=self._headers(), params={"limit": limit}
            )
            return self._parse_response(resp)

    async def get_attestation(self, evidence_id: str) -> dict[str, Any]:
        """Read the server's evidence/outcome attestation; this is not a signature proof."""
        evidence_id = _resource_id(evidence_id)
        async with self._client() as client:
            resp = await client.get(
                self._url(f"governance/evidence/{evidence_id}/attestation"),
                headers=self._headers(),
            )
            return self._parse_response(resp)
