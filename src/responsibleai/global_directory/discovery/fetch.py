# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import hashlib
import logging

import httpx

from responsibleai.net.egress import DestinationPolicy, create_safe_async_client, validate_outbound_url

logger = logging.getLogger(__name__)


class DiscoveryFetchError(Exception):
    """Fail-closed discovery fetch error."""


async def fetch_public_document(
    url: str,
    *,
    max_bytes: int,
    timeout_seconds: float = 10.0,
) -> tuple[bytes, str]:
    validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
    async with create_safe_async_client(timeout=timeout_seconds) as client:
        response = await client.get(url, follow_redirects=True)
        if response.status_code >= 400:
            raise DiscoveryFetchError(f"HTTP {response.status_code} for discovery URL")
        content_type = response.headers.get("content-type", "")
        if "text" not in content_type and "json" not in content_type:
            raise DiscoveryFetchError("Unsupported content type for discovery")
        body = response.content[:max_bytes]
        if len(response.content) > max_bytes:
            logger.info("global_directory_fetch_truncated url=%s", url)
        return body, content_type


def content_hash(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()
