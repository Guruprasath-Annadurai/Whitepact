"""Community MCP stdio server — local tools only, no SaaS account required."""

from __future__ import annotations

import json
import logging
import sys
from typing import Any

from whitepact_community.errors import (
    CommunityCapabilityUnavailable,
    GovernanceDenied,
    WhitePactCommunityError,
    error_payload,
)
from whitepact_community.models import ActionRequest, AuthorityGrant, IdentityContext
from whitepact_community.sdk import GovernanceClient
from whitepact_community.version import API_COMPATIBILITY, __version__

logger = logging.getLogger("whitepact_community.mcp")

# Community-supported tools. Enterprise surfaces are absent, not faked.
COMMUNITY_TOOLS: dict[str, dict[str, Any]] = {
    "wpc_health": {
        "description": "Local Community Core health check (no SaaS account required).",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    "wpc_policy_evaluate": {
        "description": "Evaluate a local governance policy decision.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string"},
                "target": {"type": "string"},
                "arguments": {"type": "object"},
                "grants": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Explicitly granted action types (deny-by-default).",
                },
            },
            "required": ["action_type", "target"],
            "additionalProperties": False,
        },
    },
    "wpc_local_echo": {
        "description": "Authorized local echo operation under governance.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "grants": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    "wpc_governed_local_action": {
        "description": "Execute one bounded local governed action.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "payload": {"type": "object"},
                "grants": {"type": "array", "items": {"type": "string"}},
            },
            "additionalProperties": False,
        },
    },
}


def list_tool_names() -> list[str]:
    return sorted(COMMUNITY_TOOLS)


def _validate_tool_input(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    if name not in COMMUNITY_TOOLS:
        raise CommunityCapabilityUnavailable(
            name,
            "Unknown or enterprise-only tool; not provided by Community Core.",
        )
    schema = COMMUNITY_TOOLS[name]["inputSchema"]
    required = schema.get("required", [])
    for key in required:
        if key not in arguments:
            raise WhitePactCommunityError(f"INVALID_TOOL_INPUT: missing required field {key!r}")
    if schema.get("additionalProperties") is False:
        allowed = set(schema.get("properties", {}))
        extra = set(arguments) - allowed
        if extra:
            raise WhitePactCommunityError(
                f"INVALID_TOOL_INPUT: unexpected fields {sorted(extra)}"
            )
    for key, value in arguments.items():
        expected = schema.get("properties", {}).get(key, {}).get("type")
        if expected == "string" and not isinstance(value, str):
            raise WhitePactCommunityError(
                f"INVALID_TOOL_INPUT: field {key!r} must be string"
            )
        if expected == "object" and value is not None and not isinstance(value, dict):
            raise WhitePactCommunityError(
                f"INVALID_TOOL_INPUT: field {key!r} must be object"
            )
        if expected == "array" and not isinstance(value, list):
            raise WhitePactCommunityError(
                f"INVALID_TOOL_INPUT: field {key!r} must be array"
            )
    return arguments


def _grants(raw: Any, client: GovernanceClient) -> frozenset[str]:
    if raw is None:
        return frozenset(client.config.default_grants)
    if not isinstance(raw, list) or not all(isinstance(x, str) for x in raw):
        raise WhitePactCommunityError("INVALID_TOOL_INPUT: grants must be an array of strings")
    return frozenset(raw)


def dispatch_tool(name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    args = _validate_tool_input(name, dict(arguments or {}))
    client = GovernanceClient.local()

    if name == "wpc_health":
        action = ActionRequest(action_type="local_health", target="local_health")
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=_grants(None, client),
            organization_id=client.config.org_id,
        )
        return client.execute_local(action, authority)

    if name == "wpc_policy_evaluate":
        grants = _grants(args.get("grants"), client)
        action = ActionRequest(
            action_type=args["action_type"],
            target=args["target"],
            arguments=dict(args.get("arguments") or {}),
            identity=IdentityContext(identity_id="mcp-client", org_id=client.config.org_id),
        )
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=grants,
            organization_id=client.config.org_id,
        )
        decision = client.evaluate(action, authority)
        payload = {"ok": True, "decision": decision.to_dict()}
        if not decision.allowed:
            payload["ok"] = False
        return payload

    if name == "wpc_local_echo":
        grants = _grants(args.get("grants"), client)
        action = ActionRequest(
            action_type="local_echo",
            target="local_echo",
            arguments={"text": args["text"]},
        )
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=grants,
            organization_id=client.config.org_id,
        )
        return client.execute_local(action, authority)

    if name == "wpc_governed_local_action":
        grants = _grants(args.get("grants"), client)
        action = ActionRequest(
            action_type="governed_local_action",
            target="governed_local_action",
            arguments=dict(args.get("payload") or {}),
        )
        authority = AuthorityGrant(
            delegated_by="local-operator",
            granted_action_types=grants,
            organization_id=client.config.org_id,
        )
        return client.execute_local(action, authority)

    raise CommunityCapabilityUnavailable(name)


def _jsonrpc_result(req_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _jsonrpc_error(req_id: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def handle_jsonrpc(message: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one MCP-shaped JSON-RPC request (initialize / tools/list / tools/call)."""
    req_id = message.get("id")
    method = message.get("method")
    params = message.get("params") or {}

    if method == "initialize":
        return _jsonrpc_result(
            req_id,
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "whitepact-community",
                    "version": __version__,
                    "apiCompatibility": API_COMPATIBILITY,
                },
            },
        )

    if method == "notifications/initialized":
        return None

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": meta["description"],
                "inputSchema": meta["inputSchema"],
            }
            for name, meta in sorted(COMMUNITY_TOOLS.items())
        ]
        return _jsonrpc_result(req_id, {"tools": tools})

    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        try:
            if not isinstance(name, str):
                raise WhitePactCommunityError("INVALID_TOOL_INPUT: tool name required")
            result = dispatch_tool(name, arguments if isinstance(arguments, dict) else {})
            is_error = bool(result.get("ok") is False)
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(result, sort_keys=True)}],
                    "isError": is_error,
                },
            )
        except GovernanceDenied as exc:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(error_payload(exc))}],
                    "isError": True,
                },
            )
        except CommunityCapabilityUnavailable as exc:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(error_payload(exc))}],
                    "isError": True,
                },
            )
        except WhitePactCommunityError as exc:
            return _jsonrpc_result(
                req_id,
                {
                    "content": [{"type": "text", "text": json.dumps(error_payload(exc))}],
                    "isError": True,
                },
            )

    if method == "ping":
        return _jsonrpc_result(req_id, {})

    return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")


def run_stdio() -> int:
    """Real MCP stdio loop: read newline-delimited JSON-RPC from stdin."""
    logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            sys.stdout.write(
                json.dumps(_jsonrpc_error(None, -32700, "Parse error")) + "\n"
            )
            sys.stdout.flush()
            continue
        response = handle_jsonrpc(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()
    return 0


def main() -> None:
    raise SystemExit(run_stdio())


if __name__ == "__main__":
    main()
