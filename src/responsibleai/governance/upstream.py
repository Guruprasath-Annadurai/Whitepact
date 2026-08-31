# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The MCP Upstream Gateway's domain model — v3 authority-layer work,
the largest single remaining gap the gap reports in this session
flagged repeatedly: WhitePact governed its own 27 in-process tools but
had no way to proxy a governed call to a *third-party* MCP server.

Scope, stated honestly: this closes the registry + SSRF-guarded, single-
tool-call proxy piece. It deliberately does NOT build a full MCP
gateway feature (dynamic upstream tool-list discovery, namespacing
remote tools as if they were first-class local ``rai_*`` tools, response
caching) — that's a materially larger, separate feature, and building it
ahead of a stated requirement would violate this project's own "no
unnecessary infrastructure" rule. What exists: an org registers a
specific upstream MCP server URL (SSRF-validated), then calls a specific
tool on it by name through the same five-way governance decision every
internal tool call goes through — see ``upstream_executor.py``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from responsibleai.webhooks.manager import UnsafeWebhookURLError, validate_webhook_url


class UnsafeUpstreamServerURLError(ValueError):
    """SSRF guard rejection for an upstream MCP server URL."""


def validate_upstream_server_url(url: str) -> None:
    """Reject an upstream MCP server URL that resolves to a private/
    loopback/link-local/reserved/multicast/unspecified address or the
    cloud-metadata endpoint — delegates to
    ``webhooks/manager.py``'s ``validate_webhook_url()`` rather than
    reimplementing the same check: "does this URL point somewhere this
    server shouldn't connect to" is one question, asked here for an
    outbound MCP client connection instead of a webhook delivery.
    Called at both registration time and immediately before every
    dispatch (DNS can resolve differently between the two — same
    reasoning ``validate_webhook_url``'s own docstring gives)."""
    try:
        validate_webhook_url(url)
    except UnsafeWebhookURLError as exc:
        raise UnsafeUpstreamServerURLError(str(exc)) from exc


@dataclass
class UpstreamServer:
    """One org-registered, admin-approved external MCP server. Registration
    itself *is* the approval step this platform's ``ReasonCode.
    UNAPPROVED_MCP_SERVER`` refers to — a call naming a ``server_id``
    that isn't registered (or belongs to a different org, or is
    disabled) is denied with that code before any network connection is
    attempted."""

    server_id: str
    org_id: str
    name: str
    url: str
    enabled: bool = True
    added_by: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    # Sent as `Authorization: Bearer {auth_token}` on every proxied call
    # (governance/upstream_executor.py's `_call_upstream_tool()`) --
    # almost every real MCP server an org would register requires
    # *some* credential; without this field the executor had no way to
    # authenticate to it at all, only to the SSRF-safe *address*.
    # Persisted encrypted at rest (EncryptedString, same as every other
    # credential/secret column in this schema, e.g.
    # webhook_configs.secret) and, like `ApprovalRequest.arguments`,
    # deliberately excluded from `to_dict()` — the registry list/get API
    # must never echo a credential back over HTTP.
    auth_token: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_id": self.server_id,
            "org_id": self.org_id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "added_by": self.added_by,
            "created_at": self.created_at.isoformat(),
            "has_auth_token": self.auth_token is not None,
        }


def build_upstream_server(
    org_id: str,
    name: str,
    url: str,
    *,
    added_by: str | None = None,
    auth_token: str | None = None,
) -> UpstreamServer:
    """Validates *url* (raises ``UnsafeUpstreamServerURLError``) before
    ever constructing the record — callers must not persist a server
    this check would reject."""
    validate_upstream_server_url(url)
    return UpstreamServer(
        server_id=str(uuid.uuid4()),
        org_id=org_id,
        name=name,
        url=url,
        added_by=added_by,
        auth_token=auth_token,
    )
