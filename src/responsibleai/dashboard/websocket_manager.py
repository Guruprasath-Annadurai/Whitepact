"""WebSocket connection manager for live dashboard updates.

Enterprise features:
- Per-API-key channel isolation (tenants only see their own events)
- Heartbeat ping every 30 s to detect stale connections
- Dead-connection cleanup on failed sends
- Connection count metric exposed for Prometheus
- Broadcast to all tenants or a specific tenant
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)

_HEARTBEAT_INTERVAL = 30  # seconds


class ConnectionManager:
    """Manages authenticated WebSocket connections with per-tenant isolation."""

    def __init__(self) -> None:
        # api_key -> list of active sockets
        self._connections: dict[str, list[WebSocket]] = {}
        self._heartbeat_task: asyncio.Task | None = None  # type: ignore[type-arg]

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Start the background heartbeat task. Call once at app startup."""
        if self._heartbeat_task is None or self._heartbeat_task.done():
            self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    def stop(self) -> None:
        if self._heartbeat_task and not self._heartbeat_task.done():
            self._heartbeat_task.cancel()

    # ── Connection management ─────────────────────────────────────────────────

    async def connect(self, websocket: WebSocket, api_key: str) -> None:
        await websocket.accept()
        self._connections.setdefault(api_key, []).append(websocket)
        logger.info(
            "ws_connected",
            extra={"api_key_prefix": api_key[:8] + "...", "total": self.connection_count},
        )

    def disconnect(self, websocket: WebSocket, api_key: str) -> None:
        bucket = self._connections.get(api_key, [])
        if websocket in bucket:
            bucket.remove(websocket)
        if not bucket:
            self._connections.pop(api_key, None)
        logger.info(
            "ws_disconnected",
            extra={"api_key_prefix": api_key[:8] + "...", "total": self.connection_count},
        )

    # ── Broadcast ─────────────────────────────────────────────────────────────

    async def broadcast(
        self,
        message: dict[str, Any],
        api_key: str | None = None,
    ) -> int:
        """Send *message* to all sockets for *api_key*, or everyone if None.

        Returns the number of sockets reached.
        """
        sockets: list[WebSocket] = []
        if api_key:
            sockets = list(self._connections.get(api_key, []))
        else:
            for bucket in self._connections.values():
                sockets.extend(bucket)

        dead: list[tuple[str, WebSocket]] = []
        sent = 0
        for ws in sockets:
            try:
                await ws.send_json(message)
                sent += 1
            except Exception:
                key = self._find_key(ws)
                if key:
                    dead.append((key, ws))

        for key, ws in dead:
            self.disconnect(ws, key)

        return sent

    # ── Stats ─────────────────────────────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        return sum(len(v) for v in self._connections.values())

    @property
    def tenant_count(self) -> int:
        return len(self._connections)

    # ── Internals ─────────────────────────────────────────────────────────────

    def _find_key(self, ws: WebSocket) -> str | None:
        for key, bucket in self._connections.items():
            if ws in bucket:
                return key
        return None

    async def _heartbeat_loop(self) -> None:
        while True:
            await asyncio.sleep(_HEARTBEAT_INTERVAL)
            await self.broadcast({"type": "ping", "connections": self.connection_count})
