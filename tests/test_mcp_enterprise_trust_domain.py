# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2: enterprise MCP trust domain must not allow ungoverned stdio (BLK-P0-02)."""

from __future__ import annotations

import pytest

from responsibleai.mcp.server import _ENTERPRISE_STDIO_REFUSAL, main


def test_enterprise_trust_domain_blocks_stdio_main(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_community_trust_domain_reaches_stdio_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "community")
    seen: list[str] = []

    def _fake_run(coro: object) -> None:
        seen.append("asyncio.run")
        close = getattr(coro, "close", None)
        if callable(close):
            close()

    monkeypatch.setattr("responsibleai.mcp.server.asyncio.run", _fake_run)
    main()
    assert seen == ["asyncio.run"]


def test_enterprise_refusal_message_documents_hosted_path() -> None:
    assert "hosted MCP" in _ENTERPRISE_STDIO_REFUSAL
    assert "mcp_governance_enabled" in _ENTERPRISE_STDIO_REFUSAL
