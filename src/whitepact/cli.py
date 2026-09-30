# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact product CLI — governance diagnostics and platform utilities.

The ``whitepact`` console script must not alias ``biasbuster.cli:main``.
Bias probes remain under ``biasbuster`` / ``whitepact bias`` for compatibility.
"""

from __future__ import annotations

import click

from responsibleai import __version__


@click.group()
@click.version_option(version=__version__, prog_name="whitepact")
def main() -> None:
    """WhitePact — AI governance platform CLI.

    Diagnostics, sovereign read/simulate tooling, and local developer utilities.
    MCP servers: use ``whitepact-mcp`` or ``whitepact-mcp-http``.
    Bias probes: ``biasbuster run`` or ``whitepact bias run``.
    """


from responsibleai.sovereign.cli import register_top_level, sovereign  # noqa: E402
from responsibleai.sovereign.cli_aliases import register_top_level_aliases  # noqa: E402

main.add_command(sovereign)
register_top_level(main)
register_top_level_aliases(main)


from biasbuster.cli import main as _biasbuster_cli  # noqa: E402

main.add_command(_biasbuster_cli, name="bias")


@main.command("info")
def info_cmd() -> None:
    """Show product identity and distribution metadata."""
    click.echo("product: WhitePact")
    click.echo(f"version: {__version__}")
    click.echo("pypi_distribution: rai-governance-platform")
    click.echo("import: responsibleai (canonical), whitepact (alias)")
    click.echo("cli: whitepact (this), biasbuster (bias probes only)")
    click.echo("mcp: whitepact-mcp, whitepact-mcp-http")


if __name__ == "__main__":
    main()
