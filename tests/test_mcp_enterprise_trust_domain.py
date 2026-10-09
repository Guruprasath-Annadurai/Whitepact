# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2: enterprise MCP trust domain must not allow ungoverned stdio (BLK-P0-02)."""

from __future__ import annotations

import pytest

from responsibleai.mcp.server import main
from responsibleai.mcp.trust_domain import ENTERPRISE_STDIO_REFUSAL


def test_enterprise_trust_domain_blocks_stdio_main(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
    with pytest.raises(SystemExit) as exc:
        main()
    assert exc.value.code == 2


def test_community_trust_domain_reaches_stdio_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.dashboard.config import get_settings

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "community")
    seen: list[str] = []
    monkeypatch.setattr(
        "responsibleai.mcp.server._run_stdio_main_body",
        lambda: seen.append("body"),
    )
    main()
    assert seen == ["body"]


def test_enterprise_refusal_message_documents_hosted_path() -> None:
    assert "hosted MCP" in ENTERPRISE_STDIO_REFUSAL
    assert "mcp_governance_enabled" in ENTERPRISE_STDIO_REFUSAL


def test_community_stdio_announces_ungoverned_boundary_on_stderr(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from responsibleai.mcp import server as mcp_server
    from responsibleai.mcp.trust_domain import COMMUNITY_STDIO_BOUNDARY

    def _close(coro: object) -> None:
        close = getattr(coro, "close", None)
        if close is not None:
            close()

    monkeypatch.setattr(mcp_server.asyncio, "run", _close)
    mcp_server._run_stdio_main_body()
    captured = capsys.readouterr()
    assert COMMUNITY_STDIO_BOUNDARY in captured.err
    assert "UNGOVERNED LOCAL MODE" in captured.err
    assert "not hosted governed MCP" in captured.err
    assert "protected execution" in captured.err
    assert COMMUNITY_STDIO_BOUNDARY not in captured.out


def test_enterprise_stdio_exits_before_the_community_banner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from responsibleai.dashboard.config import get_settings
    from responsibleai.mcp.trust_domain import COMMUNITY_STDIO_BOUNDARY

    monkeypatch.setattr(get_settings(), "mcp_trust_domain", "enterprise")
    with pytest.raises(SystemExit):
        main()
    captured = capsys.readouterr()
    assert COMMUNITY_STDIO_BOUNDARY not in captured.err
    assert COMMUNITY_STDIO_BOUNDARY not in captured.out
