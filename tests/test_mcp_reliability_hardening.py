# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and regression tests for MCP reliability hardening (Pass 4.4).

Verifies:
1. ADK toolset endpoint configuration (no dashboard endpoint).
2. DatabaseEngine schema separation in production (no metadata.create_all on auto_create_tables=False).
3. Dual-budget sliding-window auth failure rate limiting (credential fingerprint isolation).
4. Decoupled liveness (/health) and readiness (/ready) HTTP probe endpoints.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure worktree's src directory takes precedence over any installed package
src_dir = str(Path(__file__).resolve().parents[1] / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

import pytest  # noqa: E402 — sys.path must be patched before package import
from starlette.testclient import TestClient  # noqa: E402

from responsibleai.mcp.server import (  # noqa: E402
    _AuthFailureLimiter,
    _build_http_app,
)


# ---------------------------------------------------------------------------
# 1. ADK toolset endpoint test
# ---------------------------------------------------------------------------
def test_adk_toolset_endpoint_not_pointing_to_dashboard() -> None:
    adk_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "responsibleai"
        / "integrations"
        / "adk_toolset.py"
    )
    content = adk_path.read_text(encoding="utf-8")
    assert "https://responsibleai-dashboard.onrender.com/mcp" not in content
    assert "https://whitepact-mcp-http.onrender.com/mcp" in content


# ---------------------------------------------------------------------------
# 2. DatabaseEngine production schema separation
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_database_engine_init_auto_create_tables_false() -> None:
    from responsibleai.db.engine import DatabaseEngine

    mock_conn = AsyncMock()
    mock_engine = MagicMock()
    mock_engine.begin.return_value.__aenter__.return_value = mock_conn

    db = DatabaseEngine(mock_engine)

    with patch("responsibleai.db.engine.metadata.create_all") as mock_create_all:
        await db.init(auto_create_tables=False)
        mock_create_all.assert_not_called()
        assert mock_conn.execute.called


# ---------------------------------------------------------------------------
# 3. Dual-budget sliding-window auth failure limiter
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_dual_budget_limiter_credential_isolation() -> None:
    """An attacker probing with one invalid credential must not block another
    credential or client on the same peer IP."""
    limiter = _AuthFailureLimiter(max_failures=3, window_seconds=60.0, peer_max_failures=10)

    peer_ip = "198.51.100.24"
    bad_cred_1 = "cred:aaaa1111"
    bad_cred_2 = "cred:bbbb2222"

    # Record 3 failures on bad_cred_1
    for _ in range(3):
        await limiter.record_failure(bad_cred_1, peer_key=peer_ip)

    # bad_cred_1 is blocked
    assert await limiter.is_blocked(bad_cred_1, peer_key=peer_ip) is True

    # bad_cred_2 on the same peer IP is NOT blocked (under peer aggregate limit of 10)
    assert await limiter.is_blocked(bad_cred_2, peer_key=peer_ip) is False

    # Anonymous client on the same peer IP is NOT blocked
    assert await limiter.is_blocked(f"anon:{peer_ip}", peer_key=peer_ip) is False


@pytest.mark.asyncio
async def test_dual_budget_limiter_peer_aggregate_ceiling() -> None:
    """If an attacker cycles 10 distinct credentials on the same IP, the peer
    aggregate ceiling kicks in to prevent brute-force cycling."""
    limiter = _AuthFailureLimiter(max_failures=3, window_seconds=60.0, peer_max_failures=5)

    peer_ip = "198.51.100.99"

    # Record 1 failure each across 5 different credentials
    for i in range(5):
        cred = f"cred:token_{i}"
        await limiter.record_failure(cred, peer_key=peer_ip)

    # Any new credential on that peer IP is blocked by peer aggregate ceiling
    new_cred = "cred:fresh_attempt"
    assert await limiter.is_blocked(new_cred, peer_key=peer_ip) is True


# ---------------------------------------------------------------------------
# 4. Decoupled Liveness (/health) vs Readiness (/ready)
# ---------------------------------------------------------------------------
def test_health_liveness_probe_returns_ok() -> None:
    app = _build_http_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "transports" in data


def test_readiness_probe_returns_200_when_db_healthy() -> None:
    from responsibleai.db.engine import DatabaseEngine

    with patch.object(DatabaseEngine, "ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = True
        app = _build_http_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/ready")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "ready"
            assert data["database"] == "connected"
            assert mock_ping.called


def test_readiness_probe_returns_503_when_db_unhealthy() -> None:
    from responsibleai.db.engine import DatabaseEngine

    with patch.object(DatabaseEngine, "ping", new_callable=AsyncMock) as mock_ping:
        mock_ping.return_value = False
        app = _build_http_app()
        with TestClient(app, raise_server_exceptions=False) as client:
            resp = client.get("/ready")
            assert resp.status_code == 503
            data = resp.json()
            assert data["status"] == "unavailable"
            assert data["database"] == "disconnected"
            assert mock_ping.called
