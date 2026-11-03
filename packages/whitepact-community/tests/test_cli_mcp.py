"""CLI and MCP functional tests."""

from __future__ import annotations

import json

from click.testing import CliRunner

from whitepact_community.cli import main
from whitepact_community.mcp_server import dispatch_tool, handle_jsonrpc, list_tool_names


def test_cli_help_and_version() -> None:
    runner = CliRunner()
    help_result = runner.invoke(main, ["--help"])
    assert help_result.exit_code == 0
    assert "WhitePact Community Core" in help_result.output
    version_result = runner.invoke(main, ["version", "--json"])
    assert version_result.exit_code == 0
    payload = json.loads(version_result.output)
    assert payload["edition"] == "community"
    assert payload["version"]


def test_cli_evaluate_allow_and_deny() -> None:
    runner = CliRunner()
    allow = runner.invoke(
        main,
        [
            "evaluate",
            "--action-type",
            "local_echo",
            "--target",
            "local_echo",
            "--grant",
            "local_echo",
            "--json",
        ],
    )
    assert allow.exit_code == 0
    assert json.loads(allow.output)["decision"] == "ALLOW"

    deny = runner.invoke(
        main,
        [
            "evaluate",
            "--action-type",
            "tenant_admin",
            "--target",
            "tenant_admin",
            "--grant",
            "local_echo",
            "--json",
        ],
    )
    assert deny.exit_code == 3
    assert json.loads(deny.output)["decision"] == "DENY"


def test_cli_run_local_and_deny_demo() -> None:
    runner = CliRunner()
    ok = runner.invoke(main, ["run-local", "--text", "community"])
    assert ok.exit_code == 0
    assert json.loads(ok.output)["echo"] == "community"
    denied = runner.invoke(main, ["deny-demo"])
    assert denied.exit_code == 3


def test_cli_mcp_diagnose() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["mcp", "diagnose"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["requires_saas_account"] is False
    assert payload["tool_count"] >= 3


def test_cli_enterprise_exit_code() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["enterprise", "billing_checkout"])
    assert result.exit_code == 4


def test_cli_malformed_arg() -> None:
    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "evaluate",
            "--action-type",
            "local_echo",
            "--target",
            "local_echo",
            "--arg",
            "not-a-pair",
            "--json",
        ],
    )
    assert result.exit_code == 2


def test_mcp_initialize_and_tools_list() -> None:
    init = handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {},
        }
    )
    assert init is not None
    assert init["result"]["serverInfo"]["name"] == "whitepact-community"
    tools = handle_jsonrpc({"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert tools is not None
    names = {t["name"] for t in tools["result"]["tools"]}
    assert names == set(list_tool_names())


def test_mcp_authorized_and_unauthorized_tool_calls() -> None:
    allowed = handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "wpc_local_echo",
                "arguments": {"text": "ok", "grants": ["local_echo"]},
            },
        }
    )
    assert allowed is not None
    assert allowed["result"]["isError"] is False

    denied = dispatch_tool(
        "wpc_policy_evaluate",
        {
            "action_type": "tenant_admin",
            "target": "tenant_admin",
            "grants": ["local_echo"],
        },
    )
    assert denied["ok"] is False
    assert denied["decision"]["decision"] == "DENY"


def test_mcp_invalid_tool_input() -> None:
    result = handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "wpc_local_echo", "arguments": {}},
        }
    )
    assert result is not None
    assert result["result"]["isError"] is True


def test_mcp_unknown_enterprise_tool_rejected() -> None:
    result = handle_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {"name": "billing_checkout", "arguments": {}},
        }
    )
    assert result is not None
    assert result["result"]["isError"] is True
    body = json.loads(result["result"]["content"][0]["text"])
    assert body["error"] == "CommunityCapabilityUnavailable"
