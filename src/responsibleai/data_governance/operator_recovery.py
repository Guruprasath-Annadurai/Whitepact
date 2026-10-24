# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline recovery authorization primitives (engineering candidate only).

Signature verification is NOT a recovery grant or permission to enter READY.
The controller, durable consumption and cross-store enforcement are deliberately
not exposed until their integration is qualified. No private-key operations or
public recovery endpoints belong in this module.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import os
import re
import sqlite3
import stat
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_HEX = re.compile(r"[0-9a-f]{64}\Z")
_LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")
_DOMAIN = b"WHITEPACT-M13-R1-RECOVERY-V1\x00"


class RecoveryAuthorizationError(ValueError):
    """Approval rejected; no execution authority has been granted."""


@dataclass(frozen=True)
class OperatorKey:
    """A public trust entry; its protected source must be verified by the controller."""

    identity: str
    role: str
    public_key: bytes
    revoked: bool = False


@dataclass(frozen=True)
class RecoveryManifest:
    request_id: str
    deployment_id: str
    environment: str
    incident_id: str
    postgres_identity: str
    schema_revision: str
    store_b_identity: str
    readiness_epoch: int
    journal_digest: str
    revocation_digest: str
    docker_identity: str
    inventory_digest: str
    evidence_digest: str
    action: str
    scope: str
    security_owner: str
    recovery_operator: str
    created_at: int
    expires_at: int
    nonce: str

    def canonical_bytes(self) -> bytes:
        """Fixed schema, domain-separated UTF-8; no floats or ambiguous encodings."""
        values = asdict(self)
        digest_fields = {
            "journal_digest",
            "revocation_digest",
            "inventory_digest",
            "evidence_digest",
            "nonce",
        }
        integer_fields = {"created_at", "expires_at", "readiness_epoch"}
        for name, value in values.items():
            if name in integer_fields:
                if type(value) is not int or value < 0 or value > 2**63 - 1:
                    raise RecoveryAuthorizationError("Invalid manifest integer")
            elif not isinstance(value, str) or not (
                _HEX.fullmatch(value) if name in digest_fields else _LABEL.fullmatch(value)
            ):
                raise RecoveryAuthorizationError("Invalid manifest field")
        if self.action != "RECONCILE_EXECUTION_ADMISSION" or self.scope != "SINGLE_HOST":
            raise RecoveryAuthorizationError("Unsupported recovery action or scope")
        if self.security_owner == self.recovery_operator:
            raise RecoveryAuthorizationError("Distinct operator identities required")
        if not 0 < self.expires_at - self.created_at <= 300:
            raise RecoveryAuthorizationError("Recovery approval lifetime exceeds policy")
        return _DOMAIN + json.dumps(
            values, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


def verify_operator_approvals(
    manifest: RecoveryManifest,
    trust: tuple[OperatorKey, ...],
    signatures: Mapping[str, str],
    *,
    now: int,
    deployment_id: str,
    environment: str,
) -> str:
    """Verify two approvals, returning only a digest—not a trusted grant object.

    Caller-provided trust is suitable for unit qualification only. A future
    controller MUST load protected, externally enrolled keys itself, recheck
    evidence, durably consume authorization and enforce every READY boundary.
    This function does not implement replay prevention or production enrollment.
    """
    payload = manifest.canonical_bytes()
    if type(now) is not int or not manifest.created_at <= now < manifest.expires_at:
        raise RecoveryAuthorizationError("Recovery approval is not current")
    if manifest.deployment_id != deployment_id or manifest.environment != environment:
        raise RecoveryAuthorizationError("Recovery target mismatch")
    required = {
        manifest.security_owner: "SECURITY_OWNER",
        manifest.recovery_operator: "RECOVERY_OPERATOR",
    }
    if set(signatures) != set(required):
        raise RecoveryAuthorizationError("Exact designated approvals required")
    entries = {key.identity: key for key in trust}
    if len(entries) != len(trust):
        raise RecoveryAuthorizationError("Ambiguous operator trust configuration")
    used: set[bytes] = set()
    for identity, role in required.items():
        key = entries.get(identity)
        if (
            key is None
            or key.revoked is not False
            or key.role != role
            or type(key.public_key) is not bytes
            or len(key.public_key) != 32
            or key.public_key in used
        ):
            raise RecoveryAuthorizationError("Operator credential is not authorized")
        used.add(key.public_key)
        try:
            signature = base64.b64decode(signatures[identity], validate=True)
            if len(signature) != 64:
                raise RecoveryAuthorizationError("Invalid operator signature")
            Ed25519PublicKey.from_public_bytes(key.public_key).verify(signature, payload)
        except (InvalidSignature, ValueError, TypeError, binascii.Error) as exc:
            raise RecoveryAuthorizationError("Invalid operator signature") from exc
    return hashlib.sha256(payload).hexdigest()


class RecoveryReceiptLedger:
    """Single-host receipt persistence, NOT an execution-admission authority.

    The operator must place this private ledger outside Store A's rollback
    domain. This class cannot establish that deployment property or defend
    against a privileged operator rolling back the entire ledger. Missing state
    never bootstraps implicitly. An interrupted attempt remains consumed.
    Production enrollment, anti-rollback anchoring and READY enforcement remain
    separate mandatory integration gates.
    """

    def __init__(self, path: Path) -> None:
        self.path = path.absolute()
        self._validate_path()

    @staticmethod
    def initialize(path: Path) -> None:
        """Explicit nonproduction provisioning; never replace existing state."""
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
        ledger = RecoveryReceiptLedger(path)
        with ledger._connect() as connection:
            connection.execute(
                "CREATE TABLE recovery_receipts ("
                "epoch INTEGER PRIMARY KEY AUTOINCREMENT, "
                "request_id TEXT NOT NULL UNIQUE, nonce TEXT NOT NULL UNIQUE, "
                "manifest_digest TEXT NOT NULL, state TEXT NOT NULL "
                "CHECK(state IN ('ATTEMPTED','REJECTED','CONSUMED')))"
            )

    def _validate_path(self) -> None:
        try:
            info = self.path.lstat()
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
                or info.st_nlink != 1
            ):
                raise RecoveryAuthorizationError("Recovery ledger is not a private regular file")
            # Parent components are trusted local operator configuration, not
            # caller/browser input. Reject a symlinked ledger path nonetheless.
            if self.path.resolve() != self.path:
                raise RecoveryAuthorizationError("Recovery ledger path must be canonical")
        except OSError as exc:
            raise RecoveryAuthorizationError("Recovery ledger is unavailable") from exc

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        self._validate_path()
        connection = sqlite3.connect(self.path.as_uri() + "?mode=rw", uri=True, timeout=1)
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("PRAGMA journal_mode=DELETE")
            with connection:
                yield connection
        finally:
            connection.close()

    def consume_approvals(
        self,
        manifest: RecoveryManifest,
        trust: tuple[OperatorKey, ...],
        signatures: Mapping[str, str],
        *,
        now: int,
        deployment_id: str,
        environment: str,
        current_evidence_digest: str,
    ) -> str:
        """Persist the attempt before verification; reject replay even on failure.

        Returned digest is a receipt identifier, never a VerifiedRecoveryGrant.
        This does not hold the required whole-recovery operation lock.
        """
        digest = manifest.digest()
        try:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                connection.execute(
                    "INSERT INTO recovery_receipts(request_id,nonce,manifest_digest,state) "
                    "VALUES(?,?,?,'ATTEMPTED')",
                    (manifest.request_id, manifest.nonce, digest),
                )
        except sqlite3.IntegrityError as exc:
            raise RecoveryAuthorizationError("Recovery authorization already consumed") from exc
        except sqlite3.Error as exc:
            raise RecoveryAuthorizationError(
                "Recovery ledger cannot durably record attempt"
            ) from exc
        try:
            if current_evidence_digest != manifest.evidence_digest:
                raise RecoveryAuthorizationError("Evidence changed since approval")
            verify_operator_approvals(
                manifest,
                trust,
                signatures,
                now=now,
                deployment_id=deployment_id,
                environment=environment,
            )
        except RecoveryAuthorizationError:
            self._record_state(manifest.request_id, "REJECTED")
            raise
        self._record_state(manifest.request_id, "CONSUMED")
        return digest

    def _record_state(self, request_id: str, state: str) -> None:
        try:
            with self._connect() as connection:
                result = connection.execute(
                    "UPDATE recovery_receipts SET state=? WHERE request_id=? AND state='ATTEMPTED'",
                    (state, request_id),
                )
                if result.rowcount != 1:
                    raise RecoveryAuthorizationError("Recovery receipt transition rejected")
        except sqlite3.Error as exc:
            raise RecoveryAuthorizationError("Recovery receipt finalization failed") from exc
