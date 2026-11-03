"""Community CLI — help, version, policy evaluation, MCP diagnose, local tests."""

from __future__ import annotations

import json
import sys
from typing import Any

import click

from whitepact_community.errors import (
    CommunityCapabilityUnavailable,
    ConfigurationError,
    GovernanceDenied,
    WhitePactCommunityError,
    error_payload,
)
from whitepact_community.models import ActionRequest, AuthorityGrant, IdentityContext
from whitepact_community.sdk import GovernanceClient
from whitepact_community.version import API_COMPATIBILITY, __version__


def _emit(data: Any, *, as_json: bool) -> None:
    if as_json:
        click.echo(json.dumps(data, indent=2, sort_keys=True, default=str))
    else:
        if isinstance(data, dict):
            for key, value in data.items():
                click.echo(f"{key}: {value}")
        else:
            click.echo(str(data))


def _client(config: str | None) -> GovernanceClient:
    return GovernanceClient.local(config)


@click.group()
@click.version_option(__version__, prog_name="whitepact-community")
def main() -> None:
    """WhitePact Community Core CLI (local governance only)."""


@main.command("version")
@click.option("--json", "as_json", is_flag=True)
def version_cmd(as_json: bool) -> None:
    """Print package version and API compatibility boundary."""
    _emit(
        {
            "name": "whitepact-community",
            "version": __version__,
            "api_compatibility": API_COMPATIBILITY,
            "edition": "community",
        },
        as_json=as_json,
    )


@main.command("evaluate")
@click.option("--config", "config_path", type=click.Path(exists=False), default=None)
@click.option("--action-type", required=True)
@click.option("--target", required=True)
@click.option("--grant", multiple=True, help="Granted action type (repeatable).")
@click.option("--arg", "args", multiple=True, help="key=value argument")
@click.option("--identity", default="local-operator")
@click.option("--json", "as_json", is_flag=True)
def evaluate_cmd(
    config_path: str | None,
    action_type: str,
    target: str,
    grant: tuple[str, ...],
    args: tuple[str, ...],
    identity: str,
    as_json: bool,
) -> None:
    """Evaluate a policy decision without executing the action."""
    try:
        client = _client(config_path)
        arguments: dict[str, Any] = {}
        for item in args:
            if "=" not in item:
                raise ConfigurationError(f"Invalid --arg {item!r}; expected key=value")
            key, value = item.split("=", 1)
            arguments[key] = value
        grants = frozenset(grant) if grant else frozenset(client.config.default_grants)
        action = ActionRequest(
            action_type=action_type,
            target=target,
            arguments=arguments,
            identity=IdentityContext(identity_id=identity, org_id=client.config.org_id),
        )
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=grants,
            organization_id=client.config.org_id,
        )
        result = client.evaluate(action, authority)
        payload = result.to_dict()
        _emit(payload, as_json=as_json or True)
        if not result.allowed:
            raise SystemExit(GovernanceDenied.exit_code)
    except WhitePactCommunityError as exc:
        _emit(error_payload(exc), as_json=True)
        raise SystemExit(exc.exit_code) from exc


@main.command("run-local")
@click.option("--config", "config_path", type=click.Path(exists=False), default=None)
@click.option("--action-type", default="local_echo")
@click.option("--text", default="hello-community")
@click.option("--grant", multiple=True)
@click.option("--json", "as_json", is_flag=True, default=True)
def run_local_cmd(
    config_path: str | None,
    action_type: str,
    text: str,
    grant: tuple[str, ...],
    as_json: bool,
) -> None:
    """Execute one bounded local governed operation."""
    try:
        client = _client(config_path)
        grants = frozenset(grant) if grant else frozenset(client.config.default_grants)
        action = ActionRequest(
            action_type=action_type,
            target=action_type,
            arguments={"text": text},
            identity=IdentityContext(identity_id="local-operator", org_id=client.config.org_id),
        )
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=grants,
            organization_id=client.config.org_id,
        )
        result = client.execute_local(action, authority)
        _emit(result, as_json=as_json)
    except GovernanceDenied as exc:
        _emit(error_payload(exc), as_json=True)
        raise SystemExit(exc.exit_code) from exc
    except WhitePactCommunityError as exc:
        _emit(error_payload(exc), as_json=True)
        raise SystemExit(exc.exit_code) from exc


@main.command("deny-demo")
@click.option("--json", "as_json", is_flag=True, default=True)
def deny_demo_cmd(as_json: bool) -> None:
    """Demonstrate unauthorized action refusal (exit code 3)."""
    client = GovernanceClient.local()
    action = ActionRequest(action_type="tenant_admin", target="tenant_admin")
    authority = AuthorityGrant(
        delegated_by="local-operator",
        granted_action_types=frozenset({"local_echo"}),
        organization_id="local",
    )
    result = client.evaluate(action, authority)
    _emit(result.to_dict(), as_json=as_json)
    if not result.allowed:
        raise SystemExit(GovernanceDenied.exit_code)
    raise SystemExit(1)


@main.group("mcp")
def mcp_group() -> None:
    """MCP diagnostics and startup helpers."""


@mcp_group.command("diagnose")
@click.option("--json", "as_json", is_flag=True, default=True)
def mcp_diagnose(as_json: bool) -> None:
    """Report MCP entrypoint readiness without requiring a SaaS account."""
    try:
        from whitepact_community import mcp_server

        tools = mcp_server.list_tool_names()
        _emit(
            {
                "ok": True,
                "entrypoint": "whitepact-community-mcp",
                "transport": "stdio",
                "tool_count": len(tools),
                "tools": tools,
                "requires_saas_account": False,
                "version": __version__,
            },
            as_json=as_json,
        )
    except Exception as exc:  # noqa: BLE001 — diagnose must surface import errors
        _emit({"ok": False, "error": type(exc).__name__, "message": str(exc)}, as_json=True)
        raise SystemExit(1) from exc


@mcp_group.command("start")
def mcp_start() -> None:
    """Start the Community MCP stdio server (blocks on stdin/stdout)."""
    from whitepact_community.mcp_server import main as mcp_main

    mcp_main()


@main.command("enterprise")
@click.argument("capability")
def enterprise_cmd(capability: str) -> None:
    """Explicitly reject an enterprise-only capability request."""
    try:
        GovernanceClient.local().enterprise_capability(capability)
    except CommunityCapabilityUnavailable as exc:
        _emit(error_payload(exc), as_json=True)
        raise SystemExit(exc.exit_code) from exc


if __name__ == "__main__":
    main(prog_name="whitepact-community")
