# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated backup encryption.

Ciphertext is a Fernet token (AES-128-CBC with HMAC-SHA256), the published
Fernet spec. Passphrases are turned into a Fernet key with PBKDF2-HMAC-SHA256.
A value that is already a Fernet key is used directly. This module does not
define its own cipher.
"""

from __future__ import annotations

import base64
import gzip
import hashlib
import json
import os
import re
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

PBKDF2_ITERATIONS = 600_000
MAGIC_DUMP = b"PostgreSQL database dump"
TOOL_NAME = "whitepact-backup"
SCHEMA_VERSION = "1"
_PAYLOAD_PREFIX = b"WPBAK1\n"
_CREATED_AT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
# Inside the Fernet token: schema version, database, compression, pg_dump format,
# required_relations, plaintext SHA-256, and plaintext length.
# Sidecar only, shape-checked, not authenticated: created_at, tool, tool_version.
# ciphertext_sha256 is compared to the token bytes and is not inside the token.


class BackupRejectedError(Exception):
    """A backup or restore input failed closed. The message has no key material."""


@dataclass(frozen=True)
class BackupArtifact:
    ciphertext_path: Path
    manifest_path: Path
    ciphertext_sha256: str
    plaintext_sha256: str


@dataclass(frozen=True)
class BoundBackupClaims:
    """Claims covered by the Fernet HMAC, not merely copied into the sidecar."""

    version: str
    database: str
    compression: str
    pg_dump_format: str
    required_relations: tuple[str, ...]
    plaintext_sha256: str
    plaintext_bytes: int


def _chmod_private(path: Path) -> None:
    path.chmod(stat.S_IRUSR | stat.S_IWUSR)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _fernet(secret: str, salt: bytes | None) -> tuple[Fernet, bytes, str]:
    if "\n" in secret or "\r" in secret:
        raise BackupRejectedError("Encryption secret must be a single line.")
    stripped = secret.strip()
    if not stripped:
        raise BackupRejectedError("Encryption secret is empty.")
    if salt is None:
        try:
            return Fernet(stripped.encode("ascii")), b"", "fernet-key"
        except (ValueError, TypeError):
            salt = os.urandom(16)
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=PBKDF2_ITERATIONS,
    )
    derived = base64.urlsafe_b64encode(kdf.derive(stripped.encode("utf-8")))
    return Fernet(derived), salt, "pbkdf2-hmac-sha256"


def assert_dump_bytes(plain: bytes) -> None:
    if not plain or not plain.strip():
        raise BackupRejectedError("Backup plaintext is empty.")
    if MAGIC_DUMP not in plain[:8192]:
        raise BackupRejectedError("Backup is not a PostgreSQL plain dump.")


def encrypt_dump(
    plain: bytes,
    secret: str,
    destination: Path,
    *,
    database: str,
    tool_version: str,
    required_relations: list[str] | None = None,
) -> BackupArtifact:
    assert_dump_bytes(plain)
    return seal_compressed(
        gzip.compress(plain, mtime=0),
        plain,
        secret,
        destination,
        database=database,
        tool_version=tool_version,
        required_relations=required_relations,
    )


def _bound_header(
    *,
    schema_version: str,
    database: str,
    plaintext: bytes,
    required_relations: list[str],
) -> dict[str, object]:
    return {
        "compression": "gzip",
        "database": database,
        "pg_dump_format": "plain",
        "plaintext_bytes": len(plaintext),
        "plaintext_sha256": _sha256(plaintext),
        "required_relations": required_relations,
        "version": schema_version,
    }


def _encode_payload(header: dict[str, object], compressed: bytes) -> bytes:
    line = json.dumps(header, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if b"\n" in line:
        raise BackupRejectedError("Authenticated backup header is not a single line.")
    return _PAYLOAD_PREFIX + line + b"\n" + compressed


def _split_payload(payload: bytes) -> tuple[dict[str, object], bytes]:
    if not payload.startswith(_PAYLOAD_PREFIX):
        raise BackupRejectedError("Backup payload is an unsupported or downgraded format.")
    rest = payload[len(_PAYLOAD_PREFIX) :]
    newline = rest.find(b"\n")
    if newline < 0:
        raise BackupRejectedError("Authenticated backup header is truncated.")
    try:
        parsed = json.loads(rest[:newline].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BackupRejectedError("Authenticated backup header is not JSON.") from exc
    if not isinstance(parsed, dict):
        raise BackupRejectedError("Authenticated backup header must be an object.")
    return parsed, rest[newline + 1 :]


def _claims_from_header(header: dict[str, object]) -> BoundBackupClaims:
    version = header.get("version")
    if not isinstance(version, str) or version != SCHEMA_VERSION:
        raise BackupRejectedError("Unsupported backup schema version.")
    database = header.get("database")
    compression = header.get("compression")
    dump_format = header.get("pg_dump_format")
    digest = header.get("plaintext_sha256")
    size = header.get("plaintext_bytes")
    relations = header.get("required_relations")
    if not isinstance(database, str) or not database:
        raise BackupRejectedError("Authenticated database name is invalid.")
    if compression != "gzip" or dump_format != "plain":
        raise BackupRejectedError("Authenticated backup format is unsupported.")
    if not isinstance(compression, str) or not isinstance(dump_format, str):
        raise BackupRejectedError("Authenticated backup format is unsupported.")
    if not isinstance(digest, str) or isinstance(size, bool) or not isinstance(size, int):
        raise BackupRejectedError("Authenticated plaintext metadata is invalid.")
    if not isinstance(relations, list):
        raise BackupRejectedError("Authenticated required_relations is invalid.")
    names: list[str] = []
    for item in relations:
        if not isinstance(item, str):
            raise BackupRejectedError("Authenticated required_relations is invalid.")
        names.append(item)
    return BoundBackupClaims(
        version=version,
        database=database,
        compression=compression,
        pg_dump_format=dump_format,
        required_relations=tuple(names),
        plaintext_sha256=digest,
        plaintext_bytes=size,
    )


def _sidecar_matches_claims(manifest: dict[str, object], claims: BoundBackupClaims) -> None:
    expected = {
        "version": claims.version,
        "database": claims.database,
        "compression": claims.compression,
        "pg_dump_format": claims.pg_dump_format,
        "plaintext_sha256": claims.plaintext_sha256,
        "plaintext_bytes": claims.plaintext_bytes,
        "required_relations": list(claims.required_relations),
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise BackupRejectedError(
                f"Manifest {key} does not match the authenticated backup header."
            )
    created_at = manifest.get("created_at")
    tool = manifest.get("tool")
    tool_version = manifest.get("tool_version")
    if not isinstance(created_at, str) or _CREATED_AT.fullmatch(created_at) is None:
        raise BackupRejectedError("Manifest created_at is invalid.")
    if not isinstance(tool, str) or not tool.strip():
        raise BackupRejectedError("Manifest tool name is invalid.")
    if not isinstance(tool_version, str) or not tool_version.strip():
        raise BackupRejectedError("Manifest tool_version is invalid.")


def seal_compressed(
    compressed: bytes,
    plaintext: bytes,
    secret: str,
    destination: Path,
    *,
    database: str,
    tool_version: str,
    required_relations: list[str] | None = None,
    schema_version: str = SCHEMA_VERSION,
) -> BackupArtifact:
    if not compressed:
        raise BackupRejectedError("Refusing to encrypt an empty dump.")
    fernet, salt, kdf_name = _fernet(secret, None)
    relations = list(required_relations or [])
    header = _bound_header(
        schema_version=schema_version,
        database=database,
        plaintext=plaintext,
        required_relations=relations,
    )
    token = fernet.encrypt(_encode_payload(header, compressed))
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(token)
    _chmod_private(destination)
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    ciphertext_sha = _sha256(token)
    plaintext_sha = _sha256(plaintext)
    manifest = {
        "version": schema_version,
        "created_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tool": TOOL_NAME,
        "tool_version": tool_version,
        "cipher": "fernet",
        "authenticated": True,
        "kdf": kdf_name,
        "kdf_iterations": PBKDF2_ITERATIONS if kdf_name != "fernet-key" else 0,
        "kdf_salt_b64": base64.b64encode(salt).decode("ascii"),
        "compression": "gzip",
        "pg_dump_format": "plain",
        "database": database,
        "ciphertext_sha256": ciphertext_sha,
        "plaintext_sha256": plaintext_sha,
        "plaintext_bytes": len(plaintext),
        "required_relations": relations,
    }
    encoded = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    manifest_path.write_text(encoded, encoding="utf-8")
    _chmod_private(manifest_path)
    return BackupArtifact(destination, manifest_path, ciphertext_sha, plaintext_sha)


def load_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise BackupRejectedError(f"Backup manifest is missing: {path.name}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackupRejectedError("Backup manifest is not JSON.") from exc
    if not isinstance(data, dict):
        raise BackupRejectedError("Backup manifest must be an object.")
    return data


def decrypt_dump(
    ciphertext_path: Path, manifest_path: Path, secret: str, work_dir: Path
) -> tuple[Path, BoundBackupClaims]:
    if not ciphertext_path.is_file():
        raise BackupRejectedError("Backup file does not exist.")
    token = ciphertext_path.read_bytes()
    if not token:
        raise BackupRejectedError("Backup file is empty.")
    manifest = load_manifest(manifest_path)
    expected = manifest.get("ciphertext_sha256")
    actual = _sha256(token)
    if not isinstance(expected, str) or expected != actual:
        raise BackupRejectedError("Backup ciphertext checksum does not match the manifest.")
    if manifest.get("authenticated") is not True or manifest.get("cipher") != "fernet":
        raise BackupRejectedError("Backup manifest is not an authenticated Fernet artifact.")
    salt_b64 = manifest.get("kdf_salt_b64")
    salt = b""
    if isinstance(salt_b64, str) and salt_b64:
        try:
            salt = base64.b64decode(salt_b64)
        except ValueError as exc:
            raise BackupRejectedError("Backup manifest salt is invalid.") from exc
    kdf_name = manifest.get("kdf")
    fernet, _, _ = _fernet(secret, None if kdf_name == "fernet-key" else salt)
    try:
        payload = fernet.decrypt(token)
    except (InvalidToken, ValueError) as exc:
        raise BackupRejectedError(
            "Backup decryption failed. The key does not match this artifact."
        ) from exc
    header, compressed = _split_payload(payload)
    claims = _claims_from_header(header)
    try:
        plain = gzip.decompress(compressed)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise BackupRejectedError("Decrypted backup is truncated or not gzip.") from exc
    if _sha256(plain) != claims.plaintext_sha256 or len(plain) != claims.plaintext_bytes:
        raise BackupRejectedError("Decrypted backup does not match the authenticated header.")
    _sidecar_matches_claims(manifest, claims)
    assert_dump_bytes(plain)
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(work_dir, stat.S_IRWXU)
    plain_path = work_dir / "restore.sql"
    plain_path.write_bytes(plain)
    _chmod_private(plain_path)
    return plain_path, claims


def assert_upload_allowed(path: Path) -> Path:
    """Return the manifest path when the object is an encrypted artifact."""
    name = path.name
    if name.endswith(".sql.gz") or name.endswith(".sql"):
        raise BackupRejectedError("Refusing to upload a plaintext SQL backup.")
    if not name.endswith(".enc"):
        raise BackupRejectedError("Upload requires an encrypted .enc artifact.")
    manifest_path = path.with_name(name + ".manifest.json")
    manifest = load_manifest(manifest_path)
    token = path.read_bytes()
    expected = manifest.get("ciphertext_sha256")
    if not isinstance(expected, str) or hashlib.sha256(token).hexdigest() != expected:
        raise BackupRejectedError("Refusing to upload an artifact whose checksum does not match.")
    if manifest.get("cipher") != "fernet" or manifest.get("authenticated") is not True:
        raise BackupRejectedError("Refusing to upload an unauthenticated backup.")
    return manifest_path
