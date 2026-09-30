# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2: enterprise MCP trust domain must not allow ungoverned stdio (BLK-P0-02)."""

from __future__ import annotations

import pytest

from responsibleai.mcp.server import main
from responsibleai.mcp.trust_domain import ENTERPRISE_STDIO_REFUSAL, entrypoint_main_stdio


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
