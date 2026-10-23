# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Canonical, scope-bound controller attestations for cross-store provisioning.

Verification is deliberately not activation. The protected publisher must also
lock and verify current PostgreSQL evidence, consume the attestation durably in
Store B, and require a matching COMPLETE receipt at admission. No signing keys
or automatic approval creation belong in this application module.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from dataclasses import asdict, dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_DIGEST = re.compile(r"[a-f0-9]{64}\Z")
_DOMAIN = b"WHITEPACT-TENANT-PROVISIONING-V1\x00"


class ProvisioningAuthorizationError(ValueError):
    """No publication or execution authority may be inferred from this failure."""


@dataclass(frozen=True)
class ProvisioningManifest:
    deployment_id: str
    environment: str
    postgres_identity: str
    store_b_identity: str
    request_id: str
    principal_id: str
    tenant_id: str
    generation_id: str
    operation_digest: str
    pending_receipt_digest: str
    readiness_epoch: int
    security_epoch: int
    revocation_floor: int
    created_at: int
    expires_at: int
    nonce: str
    controller_id: str
    action: str = "PUBLISH_TENANT_LIFECYCLE"
    publication_digest: str = ""
    completion_digest: str = ""

    def canonical_bytes(self) -> bytes:
        values = asdict(self)
        integers = {
            "readiness_epoch",
            "security_epoch",
            "revocation_floor",
            "created_at",
            "expires_at",
        }
        digests = {
            "generation_id",
            "operation_digest",
            "pending_receipt_digest",
            "nonce",
            "publication_digest",
            "completion_digest",
        }
        for name, value in values.items():
            if name in integers:
                valid = type(value) is int and 0 <= value <= 2**63 - 1
            else:
                valid = type(value) is str and bool(
                    (_DIGEST if name in digests else _LABEL).fullmatch(value)
                )
                if name in {"publication_digest", "completion_digest"} and value == "":
                    valid = True
            if not valid:
                raise ProvisioningAuthorizationError("Invalid provisioning manifest field")
        if self.action not in {"PUBLISH_TENANT_LIFECYCLE", "COMPLETE_TENANT_PROVISIONING"}:
            raise ProvisioningAuthorizationError("Unsupported provisioning action")
        if self.action == "PUBLISH_TENANT_LIFECYCLE":
            if self.publication_digest or self.completion_digest:
                raise ProvisioningAuthorizationError("Unexpected completion evidence")
        elif not self.publication_digest or not self.completion_digest:
            raise ProvisioningAuthorizationError("Exact completion evidence required")
        if not 0 < self.expires_at - self.created_at <= 60:
            raise ProvisioningAuthorizationError("Invalid provisioning authorization lifetime")
        if self.security_epoch < 1 or self.revocation_floor < 1:
            raise ProvisioningAuthorizationError("Invalid initial authority floors")
        return _DOMAIN + json.dumps(
            values, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


@dataclass(frozen=True)
class ProvisionerTrust:
    """Public configuration; callers must not supply trust to a publication API.

    The verification primitive is independently testable with disposable keys.
    Operational trust must be loaded by the protected controller boundary, not
    obtained from a browser request or a restored Store A record.
    """

    controller_id: str
    public_key: bytes
    deployment_id: str
    environment: str
    postgres_identity: str
    store_b_identity: str
    revoked: bool = False


def verify_provisioning_manifest(
    manifest: ProvisioningManifest,
    signature: str,
    trust: ProvisionerTrust,
    *,
    now: int,
    current_readiness_epoch: int,
) -> str:
    """Check an exact controller attestation; return a digest, never a grant.

    Replay prevention and live Store A comparison cannot be proved by a pure
    signature verifier. They are mandatory transactional publisher checks.
    """
    payload = manifest.canonical_bytes()
    if (
        type(now) is not int
        or type(current_readiness_epoch) is not int
        or not manifest.created_at <= now < manifest.expires_at
        or manifest.readiness_epoch != current_readiness_epoch
        or trust.revoked is not False
        or type(trust.public_key) is not bytes
        or len(trust.public_key) != 32
        or (
            manifest.controller_id,
            manifest.deployment_id,
            manifest.environment,
            manifest.postgres_identity,
            manifest.store_b_identity,
        )
        != (
            trust.controller_id,
            trust.deployment_id,
            trust.environment,
            trust.postgres_identity,
            trust.store_b_identity,
        )
    ):
        raise ProvisioningAuthorizationError("Provisioning authority is not current or scoped")
    try:
        decoded = base64.b64decode(signature, validate=True)
        if len(decoded) != 64:
            raise ValueError("Invalid signature length")
        Ed25519PublicKey.from_public_bytes(trust.public_key).verify(decoded, payload)
    except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
        raise ProvisioningAuthorizationError("Invalid provisioning signature") from exc
    return hashlib.sha256(payload).hexdigest()
