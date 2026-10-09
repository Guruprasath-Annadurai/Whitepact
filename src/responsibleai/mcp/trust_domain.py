# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""MCP trust domain guards — Community stdio vs Enterprise governed hosted."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, TextIO

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings

_logger = logging.getLogger("responsibleai.mcp.trust_domain")

ENTERPRISE_STDIO_REFUSAL = (
    "Enterprise MCP trust domain forbids ungoverned stdio execution. "
    "Set WHITEPACT_MCP_TRUST_DOMAIN=community only for documented local "
    "self-hosted use, or run governed hosted MCP (mcp_governance_enabled=true) "
    "with tenant-scoped credentials."
)

PRODUCTION_COMMUNITY_DOWNGRADE_REFUSAL = (
    "Production deployments require WHITEPACT_MCP_TRUST_DOMAIN=enterprise. "
    "Community stdio cannot be enabled in production."
)

# Printed to stderr before the stdio protocol starts. Stdout is the MCP
# stream and must stay untouched. The wording is a boundary, not a claim
# that this process enforces authority.
COMMUNITY_STDIO_BOUNDARY = (
    "WHITEPACT STDIO: UNGOVERNED LOCAL MODE\n"
    "This process is not hosted governed MCP. It does not enforce tenant "
    "authority, memory-scope delegation, or execution authorization.\n"
    "Do not treat it as protected execution. Enterprise deployments must set "
    "WHITEPACT_MCP_TRUST_DOMAIN=enterprise and use hosted MCP.\n"
)


def write_community_stdio_boundary(stream: TextIO | None = None) -> None:
    """Tell a local operator this process is outside the governed product."""
    target = sys.stderr if stream is None else stream
    target.write(COMMUNITY_STDIO_BOUNDARY)
    target.flush()


def mcp_trust_domain_allows_stdio(settings: Settings) -> bool:
    return settings.mcp_trust_domain == "community"


def assert_production_mcp_trust_domain(settings: Settings) -> None:
    """Fail closed when production would run with community MCP trust domain."""
    from responsibleai.dashboard.config import is_production_environment

    production = is_production_environment(settings.environment) or bool(
        getattr(settings, "is_production", False)
    )
    if production and settings.mcp_trust_domain != "enterprise":
        raise ValueError(PRODUCTION_COMMUNITY_DOWNGRADE_REFUSAL)


def refuse_ungoverned_stdio_exit() -> None:
    """Terminate the process if enterprise trust domain blocks stdio MCP."""
    from responsibleai.dashboard.config import get_settings

    if not mcp_trust_domain_allows_stdio(get_settings()):
        _logger.error(ENTERPRISE_STDIO_REFUSAL)
        raise SystemExit(2)


def refuse_ungoverned_stdio_exit_if_needed(settings: Settings) -> None:
    if not mcp_trust_domain_allows_stdio(settings):
        _logger.error(ENTERPRISE_STDIO_REFUSAL)
        raise SystemExit(2)


def entrypoint_main_stdio() -> None:
    """Single stdio CLI entry used by console scripts and ``python -m``."""
    refuse_ungoverned_stdio_exit()
    from responsibleai.mcp.server import _run_stdio_main_body

    _run_stdio_main_body()
