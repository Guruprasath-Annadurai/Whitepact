# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact product CLI — governance diagnostics and platform utilities.

The ``whitepact`` console script must not alias ``biasbuster.cli:main``.
Bias probes remain under ``biasbuster`` / ``whitepact bias`` for compatibility.

Sovereign and dashboard-backed commands are registered lazily so a default
``pip install rai-governance-platform`` can run ``whitepact --help``, ``info``,
and ``--version`` without optional database stack dependencies.
"""

from __future__ import annotations

import click

from responsibleai import __version__

_OPTIONAL_SOVEREIGN_HINT = (
    "This command requires optional dashboard dependencies. "
    "Install with: pip install 'rai-governance-platform[dashboard]'"
)

# Top-level commands registered by sovereign/cli + cli_aliases (+ sovereign group).
# Listed for --help without importing the sovereign stack.
_DEFERRED_SOVEREIGN_COMMANDS: frozenset[str] = frozenset(
    {
        "authority",
        "capsule",
        "ci",
        "connect",
        "context",
        "doctor",
        "explain",
        "gauntlet",
        "init",
        "policy",
        "prove",
        "replay",
        "sandbox",
        "shadow",
        "simulate",
        "sovereign",
        "trace",
        "xray",
    }
)

_sovereign_attached = False
_sovereign_unavailable = False
_bias_attached = False


def _optional_deps_stub(name: str) -> click.Command:
    """Click command that explains missing optional dependencies."""

    @click.command(
        name=name,
        context_settings={
            "ignore_unknown_options": True,
            "allow_extra_args": True,
            "help_option_names": ["-h", "--help"],
        },
        short_help="Requires [dashboard] optional dependencies",
    )
    @click.pass_context
    def _cmd(ctx: click.Context, *_args: object, **_kwargs: object) -> None:
        if ctx.resilient_parsing:
            return
        raise click.ClickException(_OPTIONAL_SOVEREIGN_HINT)

    return _cmd


def _attach_sovereign(main: click.Group) -> None:
    global _sovereign_attached, _sovereign_unavailable
    if _sovereign_attached or _sovereign_unavailable:
        return
    try:
        from responsibleai.sovereign.cli import register_top_level, sovereign
        from responsibleai.sovereign.cli_aliases import register_top_level_aliases

        main.add_command(sovereign)
        register_top_level(main)
        register_top_level_aliases(main)
        _sovereign_attached = True
    except (ModuleNotFoundError, ImportError):
        _sovereign_unavailable = True


def _attach_bias(main: click.Group) -> None:
    global _bias_attached
    if _bias_attached:
        return
    from biasbuster.cli import main as _biasbuster_cli

    main.add_command(_biasbuster_cli, name="bias")
    _bias_attached = True


class WhitePactCLI(click.Group):
    """Root CLI group with lazy sovereign/dashboard command registration."""

    def list_commands(self, ctx: click.Context) -> list[str]:
        names = {"info", "bias", *_DEFERRED_SOVEREIGN_COMMANDS}
        return sorted(names)

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        if cmd_name == "info":
            return super().get_command(ctx, cmd_name)
        # Help generation resolves every listed subcommand; do not import sovereign stack.
        if ctx.resilient_parsing:
            if cmd_name == "bias" or cmd_name in _DEFERRED_SOVEREIGN_COMMANDS:
                return click.Command(name=cmd_name)
            return None
        if cmd_name == "bias":
            _attach_bias(self)
            return super().get_command(ctx, cmd_name)
        if cmd_name in _DEFERRED_SOVEREIGN_COMMANDS:
            _attach_sovereign(self)
            if _sovereign_unavailable:
                return _optional_deps_stub(cmd_name)
            return super().get_command(ctx, cmd_name)
        return None


@click.group(cls=WhitePactCLI)
@click.version_option(version=__version__, prog_name="whitepact")
def main() -> None:
    """WhitePact — AI governance platform CLI.

    Diagnostics, sovereign read/simulate tooling, and local developer utilities.
    MCP servers: use ``whitepact-mcp`` or ``whitepact-mcp-http``.
    Bias probes: ``biasbuster run`` or ``whitepact bias run``.
    """


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
