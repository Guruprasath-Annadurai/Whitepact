#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Verify the public WhitePact Streamable HTTP endpoint for OpenAI review.

The API key is read only from ``WHITEPACT_API_KEY`` and is never included
in command-line arguments or output. The command exits non-zero unless every real MCP
operation succeeds and returns the expected review behavior.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

DEFAULT_BASE_URL = "https://whitepact-mcp-http.onrender.com"
EXPECTED_TOOLS = 30
EXPECTED_RESOURCES = 20

REVIEW_CALLS: tuple[tuple[str, dict[str, Any]], ...] = (
    ("rai_health", {}),
    (
        "rai_scan",
        {
            "text": (
                "Contact John at john@example.com or 555-123-4567. His employee ID is EMP-2048."
            ),
            "redact": True,
        },
    ),
    (
        "rai_trust_score",
        {
            "fairness": 0.80,
            "privacy": 0.90,
            "security": 0.70,
            "robustness": 0.85,
            "compliance": 0.90,
            "authenticity": 0.95,
        },
    ),
    (
        "rai_eu_ai_act_classify",
        {
            "system_description": (
                "An automated resume-screening system used by employers to rank "
                "candidates and decide who proceeds to interviews."
            ),
            "deployment_sector": "employment",
            "affects_natural_persons": True,
            "is_fully_automated": True,
        },
    ),
    (
        "rai_hallucination",
        {
            "source": "The project review meeting is scheduled for Tuesday at 3 PM.",
            "text": "The project review meeting is scheduled for Wednesday at 3 PM.",
        },
    ),
)


@dataclass(frozen=True)
class Check:
    name: str
    passed: bool
    latency_ms: float
    detail: str


def _payload(result: Any) -> dict[str, Any]:
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", [])
    if content and isinstance(getattr(content[0], "text", None), str):
        parsed = json.loads(content[0].text)
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("tool result has no JSON object payload")


def _valid_result(name: str, payload: dict[str, Any]) -> bool:
    validators: dict[str, Callable[[dict[str, Any]], bool]] = {
        "rai_health": lambda value: (
            value.get("status") == "ok" and value.get("tools") == EXPECTED_TOOLS
        ),
        "rai_scan": lambda value: (
            value.get("has_pii") is True
            and isinstance(value.get("redacted_text"), str)
            and "john@example.com" not in value["redacted_text"]
            and "555-123-4567" not in value["redacted_text"]
        ),
        "rai_trust_score": lambda value: (
            isinstance(value.get("score"), (int, float)) and isinstance(value.get("risk_tier"), str)
        ),
        "rai_eu_ai_act_classify": lambda value: value.get("risk_tier") == "HIGH",
        "rai_hallucination": lambda value: (
            value.get("source_contradiction_detected") is True
            and value.get("hallucination_detected") is True
        ),
    }
    return validators[name](payload)


def _annotations_are_explicit(tool: Any) -> bool:
    annotations = getattr(tool, "annotations", None)
    return annotations is not None and all(
        getattr(annotations, field, None) is not None
        for field in ("readOnlyHint", "openWorldHint", "destructiveHint")
    )


async def verify(base_url: str, api_key: str | None, repetitions: int, timeout: float) -> dict:
    checks: list[Check] = []
    http_5xx = 0

    async def capture_status(response: httpx.Response) -> None:
        nonlocal http_5xx
        if response.status_code >= 500:
            http_5xx += 1

    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    client_timeout = httpx.Timeout(timeout)
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=client_timeout,
            follow_redirects=False,
            event_hooks={"response": [capture_status]},
        ) as http_client:
            health_started = time.perf_counter()
            health = await http_client.get("/health")
            health_ms = (time.perf_counter() - health_started) * 1000
            health_ok = health.status_code == 200 and health.json().get("status") == "ok"
            checks.append(Check("https_health", health_ok, health_ms, f"HTTP {health.status_code}"))

            async with streamable_http_client("/mcp", http_client=http_client) as (
                read_stream,
                write_stream,
                _get_session_id,
            ):
                async with ClientSession(read_stream, write_stream) as session:
                    init_started = time.perf_counter()
                    await session.initialize()
                    checks.append(
                        Check(
                            "initialize",
                            True,
                            (time.perf_counter() - init_started) * 1000,
                            "Streamable HTTP MCP session initialized",
                        )
                    )

                    list_started = time.perf_counter()
                    tools = (await session.list_tools()).tools
                    checks.append(
                        Check(
                            "tools/list",
                            len(tools) == EXPECTED_TOOLS
                            and all(_annotations_are_explicit(tool) for tool in tools),
                            (time.perf_counter() - list_started) * 1000,
                            f"{len(tools)} tools; explicit review annotations checked",
                        )
                    )

                    resources_started = time.perf_counter()
                    resources = (await session.list_resources()).resources
                    checks.append(
                        Check(
                            "resources/list",
                            len(resources) == EXPECTED_RESOURCES,
                            (time.perf_counter() - resources_started) * 1000,
                            f"{len(resources)} resources",
                        )
                    )

                    for repetition in range(1, repetitions + 1):
                        for name, arguments in REVIEW_CALLS:
                            call_started = time.perf_counter()
                            result = await session.call_tool(name, arguments)
                            latency_ms = (time.perf_counter() - call_started) * 1000
                            payload = _payload(result)
                            passed = result.isError is not True and _valid_result(name, payload)
                            detail = (
                                "real handler output validated"
                                if passed
                                else "MCP tool returned an error or unexpected output"
                            )
                            checks.append(
                                Check(
                                    f"{name}#{repetition}",
                                    passed,
                                    latency_ms,
                                    detail,
                                )
                            )
    except Exception as exc:
        checks.append(
            Check(
                "transport",
                False,
                (time.perf_counter() - started) * 1000,
                f"{type(exc).__name__}: {exc}",
            )
        )

    # HTTPS health + initialize + tools/list + resources/list, followed by
    # every review call in each requested repetition.
    expected_operations = 4 + repetitions * len(REVIEW_CALLS)
    passed_operations = sum(check.passed for check in checks)
    return {
        "base_url": base_url,
        "protocol": "MCP Streamable HTTP",
        "repetitions": repetitions,
        "expected_operations": expected_operations,
        "passed_operations": passed_operations,
        "timeouts": sum("timeout" in check.detail.casefold() for check in checks),
        "http_5xx": http_5xx,
        "success": len(checks) == expected_operations and passed_operations == expected_operations,
        "checks": [asdict(check) for check in checks],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    report = asyncio.run(
        verify(args.base_url, os.environ.get("WHITEPACT_API_KEY"), args.repetitions, args.timeout)
    )
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
