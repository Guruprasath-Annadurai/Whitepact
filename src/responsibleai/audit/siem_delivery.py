# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Best-effort SIEM HTTP delivery with retries and idempotent correlation keys (P1-06)."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class SiemDeliveryResult:
    delivered: bool
    attempts: int
    status_code: int | None
    error: str | None
    duplicate_skipped: bool = False


class SiemEventForwarder:
    """Forward NDJSON audit/SIEM payloads to an enterprise HTTP collector."""

    def __init__(self, *, max_retries: int = 3, retry_delays: tuple[float, ...] = (0.0, 0.25, 1.0)) -> None:
        self._max_retries = max(1, max_retries)
        self._retry_delays = retry_delays
        self._delivered_hashes: set[str] = set()

    def _idempotency_key(self, body: str) -> str:
        return hashlib.sha256(body.encode("utf-8")).hexdigest()

    async def forward_ndjson(
        self,
        url: str,
        body: str,
        *,
        bearer_token: str | None = None,
        hmac_secret: str | None = None,
        skip_duplicates: bool = True,
    ) -> SiemDeliveryResult:
        if not url.strip():
            return SiemDeliveryResult(False, 0, None, "destination URL is required")
        key = self._idempotency_key(body)
        if skip_duplicates and key in self._delivered_hashes:
            return SiemDeliveryResult(True, 0, None, None, duplicate_skipped=True)

        headers: dict[str, str] = {
            "Content-Type": "application/x-ndjson",
            "X-WhitePact-Idempotency-Key": key,
        }
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        if hmac_secret:
            sig = hmac.new(hmac_secret.encode(), body.encode("utf-8"), hashlib.sha256).hexdigest()
            headers["X-WhitePact-Signature-256"] = f"sha256={sig}"

        last_status: int | None = None
        last_error: str | None = None
        attempts = 0
        delays = list(self._retry_delays)[: self._max_retries]
        while len(delays) < self._max_retries:
            delays.append(delays[-1] if delays else 1.0)

        for attempt, delay in enumerate(delays):
            if delay:
                await asyncio.sleep(delay)
            attempts = attempt + 1
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, content=body.encode("utf-8"), headers=headers)
                last_status = resp.status_code
                if resp.is_success:
                    self._delivered_hashes.add(key)
                    return SiemDeliveryResult(True, attempts, last_status, None)
                last_error = f"HTTP {resp.status_code}"
            except httpx.HTTPError as exc:
                last_error = str(exc)

        return SiemDeliveryResult(False, attempts, last_status, last_error)
