# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolated nonproduction bootstrap authorization POC. NEVER publishes READY.

Signed external installation registration and durable consumption are implemented.
Store verification, publication CAS and admission integration remain deliberately
unavailable: authorization alone cannot establish readiness or execution authority.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from responsibleai.environment import is_production

DOMAIN = b"WHITEPACT-M13-FIRST-DEPLOYMENT-BOOTSTRAP-V1\0"
ROLES = ("SECURITY_OWNER", "DEPLOYMENT_OPERATOR")


class BootstrapRefusedError(ValueError):
    """No bootstrap publication or execution authority has been granted."""


@dataclass(frozen=True)
class BootstrapManifest:
    installation_id: str
    deployment_id: str
    environment: str
    postgres_identity: str
    store_b_identity: str
    evidence_digest: str
    nonce: str
    created_at: int
    expires_at: int
    purpose: str = "FIRST_DEPLOYMENT_BOOTSTRAP"
    schema_revision: str = "0067"

    def canonical_bytes(self):
        if self.purpose != "FIRST_DEPLOYMENT_BOOTSTRAP":
            raise BootstrapRefusedError("Wrong bootstrap purpose")
        if self.schema_revision != "0067":
            raise BootstrapRefusedError("Unsupported bootstrap schema")
        if self.environment not in {"development", "staging"}:
            raise BootstrapRefusedError("Production bootstrap is unavailable")
        for name in ("created_at", "expires_at"):
            value = getattr(self, name)
            if type(value) is not int or not 0 <= value <= 2**63 - 1:
                raise BootstrapRefusedError("Invalid bootstrap time")
        if not 0 < self.expires_at - self.created_at <= 300:
            raise BootstrapRefusedError("Invalid bootstrap lifetime")
        for name in ("installation_id", "evidence_digest", "nonce"):
            value = getattr(self, name)
            if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise BootstrapRefusedError("Invalid bootstrap digest/identity")
        for name in ("deployment_id", "postgres_identity", "store_b_identity"):
            value = getattr(self, name)
            if (
                type(value) is not str
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}", value) is None
            ):
                raise BootstrapRefusedError("Invalid bootstrap target")
        return DOMAIN + json.dumps(
            asdict(self), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("ascii")


def _unique_object(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise BootstrapRefusedError("Duplicate trust configuration field")
        result[name] = value
    return result


def _private_file(path):
    path = Path(path)
    if not path.is_absolute() or path.is_symlink():
        raise BootstrapRefusedError("Protected absolute operator path required")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    info = os.fstat(descriptor)
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o600
    ):
        os.close(descriptor)
        raise BootstrapRefusedError("Unprotected operator file")
    return descriptor


def _profile(path):
    if is_production():
        raise BootstrapRefusedError("Production bootstrap is unavailable")
    try:
        with os.fdopen(_private_file(path)) as stream:
            profile = json.load(stream, object_pairs_hook=_unique_object)
        expected = {
            "purpose",
            "installation_id",
            "deployment_id",
            "environment",
            "postgres_identity",
            "store_b_identity",
            "registry",
            "operators",
        }
        if (
            type(profile) is not dict
            or set(profile) != expected
            or profile["purpose"] != "NONPRODUCTION_BOOTSTRAP_QUALIFICATION"
        ):
            raise BootstrapRefusedError("Invalid operator profile")
        if profile["environment"] not in {"development", "staging"}:
            raise BootstrapRefusedError("Production bootstrap is unavailable")
        registry = Path(profile["registry"])
        parent = registry.parent.stat()
        if (
            not registry.is_absolute()
            or registry.parent.resolve() != registry.parent
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o022
        ):
            raise BootstrapRefusedError("Unprotected external registry directory")
        operators = profile["operators"]
        if type(operators) is not dict or set(operators) != set(ROLES):
            raise BootstrapRefusedError("Two designated operator roles required")
        for key in operators.values():
            if (
                type(key) is not dict
                or set(key) != {"identity", "public_key", "revoked"}
                or type(key["revoked"]) is not bool
                or key["revoked"]
            ):
                raise BootstrapRefusedError("Invalid or revoked operator")
            if type(key["identity"]) is not str or not key["identity"]:
                raise BootstrapRefusedError("Invalid operator identity")
            if type(key["public_key"]) is not str or not re.fullmatch(
                r"[0-9a-f]{64}", key["public_key"]
            ):
                raise BootstrapRefusedError("Invalid operator key")
        a, b = (operators[role] for role in ROLES)
        if a["identity"] == b["identity"] or a["public_key"] == b["public_key"]:
            raise BootstrapRefusedError("Distinct enrolled identities and keys required")
        return profile
    except (OSError, TypeError, KeyError, json.JSONDecodeError) as exc:
        raise BootstrapRefusedError("Operator trust evidence unavailable") from exc


def _verify(profile, manifest, signatures, *, now=None):
    if type(manifest) is not BootstrapManifest:
        raise BootstrapRefusedError("Bootstrap manifest required, not a recovery grant")
    payload = manifest.canonical_bytes()
    for field in (
        "installation_id",
        "deployment_id",
        "environment",
        "postgres_identity",
        "store_b_identity",
    ):
        if getattr(manifest, field) != profile[field]:
            raise BootstrapRefusedError("Cross-deployment bootstrap refused")
    now = int(time.time()) if now is None else now
    if manifest.created_at > now or manifest.expires_at <= now:
        raise BootstrapRefusedError("Bootstrap approval expired or not current")
    operators = profile["operators"]
    if type(signatures) is not dict or set(signatures) != {
        key["identity"] for key in operators.values()
    }:
        raise BootstrapRefusedError("Both distinct operator approvals required")
    try:
        for key in operators.values():
            signature = base64.b64decode(signatures[key["identity"]], validate=True)
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(key["public_key"])).verify(
                signature, payload
            )
    except (ValueError, TypeError, InvalidSignature) as exc:
        raise BootstrapRefusedError("Bootstrap signature refused") from exc
    return hashlib.sha256(payload).hexdigest()


@contextmanager
def _registry(profile):
    path = Path(profile["registry"])
    try:
        descriptor = _private_file(path)
        os.close(descriptor)
        connection = sqlite3.connect(
            path.as_uri() + "?mode=rw", uri=True, isolation_level=None, timeout=1
        )
        try:
            connection.execute("PRAGMA synchronous=FULL")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()
    except (OSError, sqlite3.Error) as exc:
        raise BootstrapRefusedError("External installation history unavailable or busy") from exc


def register_signed_new_installation(profile_path, manifest, signatures):
    """Explicit two-operator registration; never infer newness from empty stores.

    The signatures attest a new installation. Production registry custody and
    anti-rollback administration are NOT qualified by this local POC.
    """
    profile = _profile(profile_path)
    digest = _verify(profile, manifest, signatures)
    path = Path(profile["registry"])
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(descriptor)
    except OSError as exc:
        raise BootstrapRefusedError(
            "Installation registration exists or cannot be established"
        ) from exc
    with _registry(profile) as connection:
        connection.execute(
            "CREATE TABLE installation(id TEXT PRIMARY KEY,digest TEXT NOT NULL,manifest BLOB NOT NULL,state TEXT NOT NULL CHECK(state IN ('UNINITIALIZED','BOOTSTRAP_AUTHORIZED')),consumed_nonce TEXT UNIQUE)"
        )
        connection.execute(
            "INSERT INTO installation VALUES(?,?,?,'UNINITIALIZED',NULL)",
            (manifest.installation_id, digest, manifest.canonical_bytes()),
        )
    return digest


def consume_bootstrap_approval(profile_path, manifest, signatures):
    """One durable consumption. NEVER a permission to publish READY."""
    profile = _profile(profile_path)
    digest = _verify(profile, manifest, signatures)
    with _registry(profile) as connection:
        row = connection.execute(
            "SELECT digest,manifest,state FROM installation WHERE id=?", (manifest.installation_id,)
        ).fetchone()
        if row is None or row != (digest, manifest.canonical_bytes(), "UNINITIALIZED"):
            raise BootstrapRefusedError("Missing, changed or consumed installation authorization")
        updated = connection.execute(
            "UPDATE installation SET state='BOOTSTRAP_AUTHORIZED',consumed_nonce=? WHERE id=? AND state='UNINITIALIZED' AND consumed_nonce IS NULL",
            (manifest.nonce, manifest.installation_id),
        ).rowcount
        if updated != 1:
            raise BootstrapRefusedError("Bootstrap approval already consumed")
    return {"manifest_digest": digest, "state": "BOOTSTRAP_AUTHORIZED", "ready": False}


def require_ready_verified(profile_path):
    _profile(profile_path)
    raise BootstrapRefusedError(
        "Bootstrap publication and admission integration are not implemented"
    )
