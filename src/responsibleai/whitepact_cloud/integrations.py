# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""External identity/provider hooks — no live credentials in repository."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExternalIntegrationStatus:
    name: str
    implemented: bool
    blocker: str | None = None


CLOUDFLARE_ACCESS_API = ExternalIntegrationStatus(
    name="cloudflare_access_admin_api",
    implemented=False,
    blocker="OWNER_APPROVAL_REQUIRED: scoped API token + account id for session revocation",
)

CLOUDFLARE_ZERO_TRUST_DEVICE = ExternalIntegrationStatus(
    name="cloudflare_device_posture",
    implemented=False,
    blocker="OWNER_APPROVAL_REQUIRED: Zero Trust plan + device posture policies",
)

WEBAUTHN_ENROLLMENT = ExternalIntegrationStatus(
    name="employee_passkey_enrollment",
    implemented=False,
    blocker="BLOCKED: no live WebAuthn RP deployment; use Cloudflare Access IdP passkeys when connected",
)

HETZNER_TOKEN_REVOKE = ExternalIntegrationStatus(
    name="hetzner_api_token_rotation",
    implemented=False,
    blocker="OWNER_APPROVAL_REQUIRED: automation must call Hetzner API with owner-held tokens",
)
