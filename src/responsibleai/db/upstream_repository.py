"""Async repository for the MCP Upstream Gateway's registry
(``upstream_mcp_servers``) -- org-scoped CRUD over approved external
MCP servers. See ``governance/upstream.py`` for the SSRF validation this
repository enforces at registration time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, upstream_mcp_servers
from responsibleai.governance.upstream import UpstreamServer, validate_upstream_server_url


def _now() -> str:
    return datetime.now(UTC).isoformat()


class UpstreamServerNotFoundError(Exception):
    def __init__(self, server_id: str) -> None:
        self.server_id = server_id
        super().__init__(f"Upstream MCP server {server_id!r} not found.")


def _row_to_server(row: Any) -> UpstreamServer:
    return UpstreamServer(
        server_id=row.id,
        org_id=row.org_id,
        name=row.name,
        url=row.url,
        enabled=bool(row.enabled),
        added_by=row.added_by,
        created_at=datetime.fromisoformat(row.created_at),
        auth_token=getattr(row, "auth_token", None),
    )


class UpstreamServerRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def register(
        self,
        org_id: str,
        name: str,
        url: str,
        *,
        added_by: str | None = None,
        auth_token: str | None = None,
    ) -> UpstreamServer:
        """Raises ``UnsafeUpstreamServerURLError`` (from
        ``validate_upstream_server_url``) before ever writing a row --
        registration is the one point an org actually chooses to trust
        a URL, so it's the one point that must refuse an unsafe one
        outright rather than merely warning."""
        validate_upstream_server_url(url)
        server = UpstreamServer(
            server_id=str(uuid.uuid4()),
            org_id=org_id,
            name=name,
            url=url,
            added_by=added_by,
            auth_token=auth_token,
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(upstream_mcp_servers).values(
                    id=server.server_id,
                    org_id=server.org_id,
                    name=server.name,
                    url=server.url,
                    enabled=1,
                    auth_token=server.auth_token,
                    added_by=server.added_by,
                    created_at=server.created_at.isoformat(),
                )
            )
        return server

    async def get(self, server_id: str) -> UpstreamServer | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(upstream_mcp_servers).where(upstream_mcp_servers.c.id == server_id)
                )
            ).fetchone()
        return _row_to_server(row) if row else None

    async def list_for_org(self, org_id: str) -> list[UpstreamServer]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(upstream_mcp_servers)
                    .where(upstream_mcp_servers.c.org_id == org_id)
                    .order_by(upstream_mcp_servers.c.created_at.asc())
                )
            ).fetchall()
        return [_row_to_server(r) for r in rows]

    async def remove(self, org_id: str, server_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(upstream_mcp_servers)
                .where(upstream_mcp_servers.c.org_id == org_id)
                .where(upstream_mcp_servers.c.id == server_id)
            )
        if result.rowcount == 0:
            raise UpstreamServerNotFoundError(server_id)

    async def set_enabled(self, org_id: str, server_id: str, enabled: bool) -> UpstreamServer:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(upstream_mcp_servers)
                .where(upstream_mcp_servers.c.org_id == org_id)
                .where(upstream_mcp_servers.c.id == server_id)
                .values(enabled=1 if enabled else 0)
            )
        if result.rowcount == 0:
            raise UpstreamServerNotFoundError(server_id)
        server = await self.get(server_id)
        assert server is not None  # just updated it, in the same org
        return server
