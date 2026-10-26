# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""A newly started test server must not inherit another server's SSE shutdown.

This deliberately reproduces process-global transport state left by an earlier
in-process Uvicorn server. It does not alter authentication or dispatch behavior.
"""

from __future__ import annotations

import pytest
from sse_starlette.sse import AppStatus

from tests import test_mcp_wave1_compatibility as compatibility

governed_app_with_key = compatibility.governed_app_with_key
tcp_mcp = compatibility.tcp_mcp


@pytest.fixture(autouse=True)
def previous_server_was_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(AppStatus, "should_exit", True)


async def test_new_server_completes_invalid_argument_response_after_prior_shutdown(tcp_mcp):
    await compatibility.test_real_tcp_malformed_and_invalid_arguments_never_dispatch(tcp_mcp)


async def test_new_server_preserves_revocation_checks_after_prior_shutdown(tcp_mcp):
    await compatibility.test_real_tcp_revoked_key_cannot_reuse_discovery_session(tcp_mcp)
