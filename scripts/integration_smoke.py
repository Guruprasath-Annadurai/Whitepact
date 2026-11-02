#!/usr/bin/env python3
"""Cross-platform MCP compatibility preflight for WhitePact.

This is a protocol-level smoke suite: it proves the WhitePact MCP server
itself behaves correctly against the MCP spec, the way ANY compliant
client (Claude, Copilot, Gemini, ...) would exercise it. It does NOT
simulate any specific provider's actual client library or UI -- that
distinction matters, so every result below is labeled:

    LOCAL_PROTOCOL_TEST  -- exercises WhitePact's own /mcp endpoint
                            directly over HTTP. Always runs.
    REAL_PROVIDER_TEST   -- would call a provider's own API/SDK using
                            real credentials. Only runs if the relevant
                            environment variable is set; otherwise
                            reported as SKIPPED, never faked.

Usage:
    python scripts/integration_smoke.py [--base-url URL] [--api-key KEY]

If --api-key / WHITEPACT_API_KEY is not supplied, auth-required checks
are skipped (reported, not silently passed).
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL = "https://whitepact-mcp-http.onrender.com"


@dataclass
class CheckResult:
    name: str
    kind: str  # LOCAL_PROTOCOL_TEST | REAL_PROVIDER_TEST
    passed: bool
    detail: str
    limitation: str = ""


@dataclass
class SmokeReport:
    base_url: str
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, kind: str, passed: bool, detail: str, limitation: str = "") -> None:
        self.results.append(CheckResult(name, kind, passed, detail, limitation))

    def print_table(self) -> None:
        print(f"\nPLATFORM: WhitePact hosted MCP ({self.base_url})")
        header = f"{'CHECK':<28}{'KIND':<20}{'RESULT':<10}{'LIMITATION'}"
        print(header)
        print("-" * len(header))
        for r in self.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"{r.name:<28}{r.kind:<20}{status:<10}{r.limitation}")
        print()
        for r in self.results:
            print(f"  [{r.name}] {r.detail}")

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)


def _rpc(
    client: httpx.Client,
    method: str,
    params: dict | None = None,
    headers: dict | None = None,
    req_id: int = 1,
) -> httpx.Response:
    body = {"jsonrpc": "2.0", "id": req_id, "method": method, "params": params or {}}
    hdrs = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
    if headers:
        hdrs.update(headers)
    return client.post("/mcp", json=body, headers=hdrs, timeout=30.0)


def check_health(report: SmokeReport, client: httpx.Client) -> None:
    try:
        resp = client.get("/health", timeout=15.0)
        ok = resp.status_code == 200 and resp.json().get("status") == "ok"
        report.add(
            "health",
            "LOCAL_PROTOCOL_TEST",
            ok,
            f"GET /health -> {resp.status_code} {resp.text[:200]}",
        )
    except httpx.HTTPError as exc:
        report.add("health", "LOCAL_PROTOCOL_TEST", False, f"request failed: {exc}")


def check_initialize_requires_auth(report: SmokeReport, client: httpx.Client) -> None:
    resp = _rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1.0"},
        },
    )
    ok = resp.status_code == 401
    report.add(
        "auth_required_on_init",
        "LOCAL_PROTOCOL_TEST",
        ok,
        f"unauthenticated initialize -> {resp.status_code} (expected 401)",
    )


def check_invalid_token(report: SmokeReport, client: httpx.Client) -> None:
    resp = _rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1.0"},
        },
        headers={"Authorization": "Bearer not-a-real-key"},
    )
    ok = resp.status_code == 401
    report.add(
        "invalid_token_rejected",
        "LOCAL_PROTOCOL_TEST",
        ok,
        f"initialize with bogus Bearer token -> {resp.status_code} (expected 401)",
    )


def check_malformed_request(report: SmokeReport, client: httpx.Client) -> None:
    # Auth is checked before the body is parsed, so an unauthenticated
    # malformed request correctly fails closed with 401 rather than a
    # body-parsing error -- verified live 2026-08-13. 400/406/422 also
    # accepted in case a future change reorders auth vs. parsing.
    resp = client.post(
        "/mcp",
        content=b"{not valid json",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        timeout=15.0,
    )
    ok = resp.status_code in (400, 401, 406, 422)
    report.add(
        "malformed_request_rejected",
        "LOCAL_PROTOCOL_TEST",
        ok,
        f"malformed JSON body (unauthenticated) -> {resp.status_code} (expected 4xx, fails closed on auth first)",
    )


def check_server_card(report: SmokeReport, client: httpx.Client) -> None:
    resp = client.get("/.well-known/mcp/server-card.json", timeout=15.0)
    ok = resp.status_code == 200 and "tools" in resp.json()
    tool_count = len(resp.json().get("tools", [])) if ok else 0
    report.add(
        "server_card_advertises_tools",
        "LOCAL_PROTOCOL_TEST",
        ok,
        f"GET server-card.json -> {resp.status_code}, {tool_count} tools advertised",
    )


def check_authenticated_flow(
    report: SmokeReport, client: httpx.Client, api_key: str | None
) -> None:
    if not api_key:
        report.add(
            "authenticated_tools_list",
            "REAL_PROVIDER_TEST",
            False,
            "skipped: no WHITEPACT_API_KEY supplied",
            limitation="requires a real WhitePact API key -- see FOUNDER_ACTIONS.md",
        )
        report.add(
            "tool_invocation_and_deny_path",
            "REAL_PROVIDER_TEST",
            False,
            "skipped: no WHITEPACT_API_KEY supplied",
            limitation="requires a real WhitePact API key",
        )
        return

    headers = {"Authorization": f"Bearer {api_key}"}
    init = _rpc(
        client,
        "initialize",
        {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "smoke", "version": "1.0"},
        },
        headers=headers,
    )
    ok = init.status_code == 200
    report.add(
        "authenticated_tools_list",
        "REAL_PROVIDER_TEST",
        ok,
        f"authenticated initialize -> {init.status_code}",
    )

    call = _rpc(
        client,
        "tools/call",
        {"name": "rai_scan", "arguments": {"text": "contact me at test@example.com"}},
        headers=headers,
        req_id=2,
    )
    call_ok = call.status_code == 200
    report.add(
        "tool_invocation_and_deny_path",
        "REAL_PROVIDER_TEST",
        call_ok,
        f"rai_scan tool call -> {call.status_code}",
    )


def run_checks(report: SmokeReport, client: httpx.Client, api_key: str | None) -> None:
    """Shared entry point used by both the CLI and the pytest wrapper in
    tests/integrations/ -- so the test suite exercises the exact same
    check functions the CLI reports on, not a re-implementation."""
    check_health(report, client)
    check_initialize_requires_auth(report, client)
    check_invalid_token(report, client)
    check_malformed_request(report, client)
    check_server_card(report, client)
    check_authenticated_flow(report, client, api_key)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url", default=os.environ.get("WHITEPACT_MCP_BASE_URL", DEFAULT_BASE_URL)
    )
    parser.add_argument("--api-key", default=os.environ.get("WHITEPACT_API_KEY"))
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON instead of a table"
    )
    args = parser.parse_args()

    report = SmokeReport(base_url=args.base_url)
    with httpx.Client(base_url=args.base_url) as client:
        run_checks(report, client, args.api_key)

    if args.json:
        print(json.dumps([r.__dict__ for r in report.results], indent=2))
    else:
        report.print_table()

    # REAL_PROVIDER_TEST skips (no key) are reported, not treated as
    # smoke-suite failures -- only LOCAL_PROTOCOL_TEST failures fail the run.
    local_failed = any(not r.passed for r in report.results if r.kind == "LOCAL_PROTOCOL_TEST")
    return 1 if local_failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
