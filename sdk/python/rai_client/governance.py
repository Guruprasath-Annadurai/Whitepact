"""WhitePact runtime governance helpers for the HTTP API (SDK P1-03)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class GovernanceToolOutcome:
    """Parsed result of a governed tool call."""

    raw: dict[str, Any]

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
            self.raw.get("status") == "UNKNOWN" or self.raw.get("reconciliation_required") is True
        )


class GovernanceRuntimeClient:
    """Bearer-authenticated governance runtime surface (approvals, tools, evidence)."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "http://localhost:8765",
        timeout: float = 30.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._key = api_key
        self._timeout = timeout

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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url("v1/governance/tools/call"),
                headers=self._headers(),
                json={"name": name, "arguments": arguments or {}, "purpose": purpose},
            )
            return GovernanceToolOutcome(raw=resp.json())

    async def revoke_delegation(self, identity_id: str, *, reason: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url(f"governance/delegations/{identity_id}/revoke"),
                headers=self._headers(),
                json={"reason": reason},
            )
            resp.raise_for_status()
            return resp.json()

    async def list_approvals(self, status: str | None = None) -> dict[str, Any]:
        params = {"status": status} if status else None
        async with httpx.AsyncClient(timeout=self._timeout) as client:
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
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/resolve"),
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            return resp.json()

    async def execute_approval(self, approval_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                self._url(f"governance/approvals/{approval_id}/execute"),
                headers=self._headers(),
                json={},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_evidence(self, evidence_id: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(
                self._url(f"governance/evidence/{evidence_id}"),
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()
