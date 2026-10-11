#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Conformance checks for a LIVE WhitePact hosted MCP endpoint, as an assistant's connector would see it.

This is preparation for real ChatGPT / Claude / Grok compatibility tests, not a substitute for them: it proves the
endpoint meets the published requirements those clients document (401 challenge, protected-resource metadata,
authorization-server metadata, PKCE S256, tool listing and annotations, a read-only authority call). It never
registers clients, never starts an OAuth flow, never calls a state-changing tool, and never prints the token.

    WHITEPACT_COMPAT_TOKEN=<reviewer token> python scripts/live_mcp_compat_check.py \\
        --base-url https://mcp-staging.example.com --resource https://mcp-staging.example.com/mcp

Exit status: 0 only if every check that ran passed AND none were skipped for a required reason; a skipped check is
reported as SKIP and is never counted as a pass.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

READ_ONLY_TOOLS = (
    "whitepact_policy_status",
    "whitepact_list_pending_approvals",
    "whitepact_verify_evidence",
)
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@dataclass
class Check:
    name: str
    status: str  # PASS | FAIL | SKIP
    detail: str = ""


def _rpc(method: str, params: dict[str, Any] | None = None, ident: int = 1) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": ident, "method": method, "params": params or {}}


def _body(response: Any) -> dict[str, Any]:
    text = response.text
    if response.headers.get("content-type", "").startswith("text/event-stream"):
        for line in text.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        return {}
    return response.json()


async def run_checks(
    client: Any, *, resource: str, token: str | None, oauth_expected: bool = True
) -> list[Check]:
    out: list[Check] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        out.append(Check(name, "PASS" if ok else "FAIL", detail))

    def skip(name: str, why: str) -> None:
        out.append(Check(name, "SKIP", why))

    path = (
        "/" + resource.split("://", 1)[-1].split("/", 1)[-1] if resource.count("/") > 2 else "/mcp"
    )

    health = await client.get("/health")
    record("health endpoint answers 200", health.status_code == 200, f"status {health.status_code}")
    ready = await client.get("/ready")
    record(
        "readiness reports a connected database",
        ready.status_code == 200,
        f"status {ready.status_code}",
    )

    unauth = await client.post(path, json=_rpc("tools/list"), headers=MCP_HEADERS)
    challenge = unauth.headers.get("www-authenticate", "")
    record(
        "unauthenticated request gets 401 (Claude ignores a challenge on 200)",
        unauth.status_code == 401,
        f"status {unauth.status_code}",
    )
    record("401 carries resource_metadata", "resource_metadata=" in challenge, challenge[:120])

    prm = await client.get("/.well-known/oauth-protected-resource")
    if prm.status_code == 200:
        meta = prm.json()
        record(
            "protected-resource `resource` equals the connector URL exactly",
            meta.get("resource") == resource,
            f"{meta.get('resource')!r} vs {resource!r}",
        )
        servers = meta.get("authorization_servers") or []
        record(
            "first authorization server is https",
            bool(servers) and str(servers[0]).startswith("https://"),
            str(servers[:1]),
        )
        issuer = str(servers[0]).rstrip("/") if servers else ""
        # Only the endpoint's own origin is fetched; a foreign issuer is checked separately by hand.
        same_origin = issuer.startswith(str(client.base_url).rstrip("/"))
        asm = (
            await client.get(issuer + "/.well-known/oauth-authorization-server")
            if same_origin
            else None
        )
        if asm is not None and asm.status_code == 200:
            a = asm.json()
            record(
                "PKCE S256 advertised", "S256" in (a.get("code_challenge_methods_supported") or [])
            )
            record(
                "issuer matches the protected resource's authorization server",
                a.get("issuer", "").rstrip("/") == issuer,
            )
            record("registration endpoint present (DCR)", bool(a.get("registration_endpoint")))
            record(
                "public-client token auth supported",
                "none" in (a.get("token_endpoint_auth_methods_supported") or []),
            )
            record(
                "every endpoint is https and under the issuer origin",
                all(
                    str(a.get(k, "")).startswith(issuer)
                    for k in ("authorization_endpoint", "token_endpoint", "registration_endpoint")
                ),
            )
        elif asm is None:
            skip(
                "authorization-server metadata",
                f"issuer {issuer!r} is on another origin; check it separately",
            )
        else:
            record("authorization-server metadata reachable", False, f"status {asm.status_code}")
    elif oauth_expected:
        record("protected-resource metadata is served", False, f"status {prm.status_code}")
    else:
        skip("OAuth discovery", "endpoint is not configured for OAuth (static keys only)")

    if not token:
        for name in (
            "initialize + tools/list with credentials",
            "tool annotations are present and truthful",
            "authority tools are read-only",
            "a read-only authority tool call works",
        ):
            skip(name, "no credential supplied (set WHITEPACT_COMPAT_TOKEN)")
        return out

    auth = {**MCP_HEADERS, "Authorization": f"Bearer {token}"}
    init = await client.post(
        path,
        json=_rpc(
            "initialize",
            {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "whitepact-compat-check", "version": "1"},
            },
        ),
        headers=auth,
    )
    record(
        "initialize succeeds with the credential",
        init.status_code == 200 and "result" in _body(init),
        f"status {init.status_code}",
    )
    listing = await client.post(path, json=_rpc("tools/list", ident=2), headers=auth)
    tools = (_body(listing).get("result") or {}).get("tools") or []
    record(
        "tools/list returns tools",
        listing.status_code == 200 and bool(tools),
        f"{len(tools)} tools",
    )
    names = [t["name"] for t in tools]
    record(
        "tool names unique and <= 64 chars",
        len(names) == len(set(names)) and all(len(n) <= 64 for n in names),
    )
    missing = [
        t["name"]
        for t in tools
        if not (t.get("annotations") or {}).keys() >= {"readOnlyHint", "destructiveHint"}
    ]
    record(
        "every tool declares readOnlyHint and destructiveHint", not missing, ", ".join(missing[:5])
    )
    authority = [
        t
        for t in tools
        if t["name"].startswith("whitepact_")
        and t["name"] in READ_ONLY_TOOLS + ("whitepact_simulate_policy",)
    ]
    if authority:
        bad = [
            t["name"]
            for t in authority
            if not (t.get("annotations") or {}).get("readOnlyHint")
            or (t.get("annotations") or {}).get("destructiveHint")
        ]
        record(
            "authority tools are annotated read-only and non-destructive", not bad, ", ".join(bad)
        )
        call = await client.post(
            path,
            json=_rpc("tools/call", {"name": "whitepact_policy_status", "arguments": {}}, ident=3),
            headers=auth,
        )
        result = _body(call).get("result") or {}
        structured = result.get("structuredContent") or {}
        ok = call.status_code == 200 and not result.get("isError") and "rule_count" in structured
        record(
            "whitepact_policy_status returns a tenant summary (read-only)",
            ok,
            structured.get("error", "") if isinstance(structured, dict) else "",
        )
    else:
        skip("authority tools", "not advertised for this credential/environment")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--base-url", required=True)
    parser.add_argument(
        "--resource", required=True, help="the exact MCP URL a user enters in the assistant"
    )
    parser.add_argument(
        "--no-oauth", action="store_true", help="the endpoint uses static keys only"
    )
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)
    import httpx

    if (
        not args.base_url.startswith("https://")
        and "localhost" not in args.base_url
        and "127.0.0.1" not in args.base_url
    ):
        print("refusing a non-https remote endpoint", file=sys.stderr)
        return 2
    token = os.environ.get("WHITEPACT_COMPAT_TOKEN") or None

    async def _go() -> list[Check]:
        async with httpx.AsyncClient(
            base_url=args.base_url, timeout=args.timeout, follow_redirects=False
        ) as client:
            return await run_checks(
                client, resource=args.resource, token=token, oauth_expected=not args.no_oauth
            )

    checks = asyncio.run(_go())
    for check in checks:
        print(
            f"{check.status:5} {check.name}"
            + (f"  [{check.detail}]" if check.detail and check.status != "PASS" else "")
        )
    failed = [c for c in checks if c.status == "FAIL"]
    skipped = [c for c in checks if c.status == "SKIP"]
    print(
        f"\n{len(checks) - len(failed) - len(skipped)} passed, {len(failed)} failed, {len(skipped)} skipped (a skip is not a pass)"
    )
    return 1 if failed or skipped else 0


if __name__ == "__main__":
    raise SystemExit(main())
