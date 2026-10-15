# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only local SDK evidence probe; no tool execution or response-body output."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import os
from collections.abc import Mapping
from urllib.parse import urlsplit

import httpx

from rai_client import GovernanceRequestError, GovernanceRuntimeClient


def local_origin(value: str) -> bool:
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        return bool(
            value
            and not any(c.isspace() or ord(c) < 32 for c in value)
            and parsed.scheme in ("http", "https")
            and host
            and (host == "localhost" or ipaddress.ip_address(host).is_loopback)
            and parsed.port != 0
            and not parsed.username
            and not parsed.password
            and not parsed.query
            and not parsed.fragment
            and parsed.path in ("", "/")
        )
    except (ValueError, UnicodeError):
        return False


async def probe(environ: Mapping[str, str]) -> str:
    origin = environ.get("WHITEPACT_DEVELOPER_URL", "")
    key = environ.get("WHITEPACT_DEVELOPER_API_KEY", "")
    if not local_origin(origin) or not key.strip():
        return "LOCAL_CONFIGURATION_REQUIRED"
    try:
        client = GovernanceRuntimeClient(api_key=key, base_url=origin, timeout=10.0)
        await client.list_evidence(limit=1)
    except GovernanceRequestError as exc:
        if exc.status_code == 401:
            return "AUTHENTICATION_REQUIRED"
        if exc.status_code == 403:
            return "ACCESS_DENIED"
        return "READ_REQUEST_FAILED"
    except (httpx.RequestError, ValueError):
        return "READ_UNAVAILABLE"
    return "READ_RESPONSE_RECEIVED"


def main() -> int:
    status = asyncio.run(probe(os.environ))
    print(json.dumps({"status": status, "execution_attempted": False}))
    return 0 if status == "READ_RESPONSE_RECEIVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
