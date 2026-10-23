# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""One-shot application client for the separate single-host provisioning process."""

import hashlib
import json
import os
import stat
from pathlib import Path

import httpx


class TenantProvisioningUnavailableError(RuntimeError):
    """No success or authority may be inferred; explicit reconciliation required."""


class TenantCreationDeniedError(PermissionError):
    """The controller did not authenticate/authorize this creation operation."""


async def provision_organization(
    *,
    name: str,
    slug: str,
    session_token: str,
    csrf: str,
    kind: str = "ORGANIZATION",
    attach_session: bool = False,
    request_id: str | None = None,
    monthly_budget_usd: float = 10000.0,
) -> str:
    """Never forward tenant/generation/entitlement IDs or raw database credentials.

    No automatic retry. On a lost response, the authenticated caller can repeat
    this exact request ID and operation: the controller reconciles its durable
    records. A different operation is not a retry. This is a provisioning-only
    guarantee, not general execution/billing idempotency.
    """
    if not session_token or not csrf:
        raise TenantCreationDeniedError(
            "Verified session and CSRF are required for tenant creation"
        )
    socket_path = Path(os.environ.get("WHITEPACT_TENANT_CONTROLLER_SOCKET", ""))
    try:
        expected_uid = int(os.environ["WHITEPACT_TENANT_CONTROLLER_UID"])
        info = socket_path.lstat()
        parent = socket_path.parent.stat()
        if (
            not socket_path.is_absolute()
            or not stat.S_ISSOCK(info.st_mode)
            or info.st_uid != expected_uid
            or stat.S_IMODE(info.st_mode) & 0o007
            or parent.st_uid not in {0, expected_uid}
            or stat.S_IMODE(parent.st_mode) & 0o022
        ):
            raise ValueError("Untrusted controller socket")
    except (OSError, KeyError, ValueError) as exc:
        raise TenantProvisioningUnavailableError(
            "Protected provisioning controller is unavailable"
        ) from exc
    operation = {
        "name": name,
        "slug": slug,
        "kind": kind,
        "attach_session": attach_session,
        "monthly_budget_usd": monthly_budget_usd,
    }
    if request_id is None:
        # Opaque stable operation ID, never a browser-selected tenant identity.
        request_id = hashlib.sha256(
            b"WHITEPACT-CREATION-REQUEST-V1\x00"
            + hashlib.sha256(session_token.encode()).digest()
            + json.dumps(operation, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    payload = operation | {"request_id": request_id, "session_token": session_token, "csrf": csrf}
    try:
        async with httpx.AsyncClient(
            transport=httpx.AsyncHTTPTransport(uds=str(socket_path), retries=0),
            base_url="http://provisioning-controller",
            timeout=30,
            follow_redirects=False,
        ) as client:
            response = await client.post("/internal/provision", json=payload)
        if response.status_code in {401, 403}:
            raise TenantCreationDeniedError("Tenant creation authorization was rejected")
        if response.status_code != 200:
            raise TenantProvisioningUnavailableError(
                "Tenant completion is unconfirmed; reconcile exact request"
            )
        result = response.json()
        if (
            type(result) is not dict
            or set(result) != {"tenant_id", "state"}
            or result["state"] != "COMPLETE"
            or type(result["tenant_id"]) is not str
        ):
            raise ValueError("Unverified controller response")
        return result["tenant_id"]
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        raise TenantProvisioningUnavailableError(
            "Tenant completion is unconfirmed; reconcile exact request"
        ) from exc
