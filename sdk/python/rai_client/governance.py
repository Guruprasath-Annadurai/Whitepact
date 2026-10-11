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

from dataclasses import dataclass
from typing import Any

import httpx

from .transport import validate_base_url


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
        if "decision" in self.raw and self.raw["decision"] != "ALLOW":
            return False
        result = self.raw["result"]
        return not (
            isinstance(result, dict)
            and any(result.get(field) for field in ("error", "is_error", "isError"))
        )

    @property
    def requires_approval(self) -> bool:
        return self.raw.get("error") == "governance_approval_required"

    @property
    def approval_id(self) -> str | None:
        return self.raw.get("approval_id")

    @property
    def denied(self) -> bool:
        return self.raw.get("error") == "governance_denied"

    @property
    def reconciliation_required(self) -> bool:
        return (
            self.raw.get("status") == "UNKNOWN"
            or self.raw.get("outcome_status") == "UNKNOWN"
            or self.raw.get("error") == "governance_unknown_outcome"
            or self.raw.get("reconciliation_required") is True
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
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout
        self._transport = transport  # tests only; production uses the default transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self._timeout, transport=self._transport)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _url(self, path: str) -> str:
        return f"{self._base}/api/{path.lstrip('/')}"

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
        if not resp.is_success:
            detail = resp.text.replace(self._key, "[REDACTED]") if self._key else resp.text
            raise GovernanceRequestError(resp.status_code, detail[:200])
        try:
            body = resp.json()
        except ValueError as exc:
            raise GovernanceRequestError(resp.status_code, "response is not JSON") from exc
        if not isinstance(body, dict):
            raise GovernanceRequestError(resp.status_code, "response is not a JSON object")
        return GovernanceToolOutcome(raw=body)

    async def revoke_delegation(self, identity_id: str, *, reason: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/delegations/{identity_id}/revoke"),
                headers=self._headers(),
                json={"reason": reason},
            )
            resp.raise_for_status()
            return resp.json()

    async def list_approvals(self, status: str | None = None) -> dict[str, Any]:
        params = {"status": status} if status else None
        async with self._client() as client:
            resp = await client.get(
                self._url("governance/approvals"),
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            return resp.json()

    async def resolve_approval(
        self,
        approval_id: str,
        outcome: str,
        *,
        notes: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"outcome": outcome}
        if notes is not None:
            body["notes"] = notes
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/resolve"),
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def execute_approval(self, approval_id: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/execute"),
                headers=self._headers(),
                json={},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        async with self._client() as client:
            resp = await client.get(
                self._url(f"governance/evidence/{evidence_id}"),
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
