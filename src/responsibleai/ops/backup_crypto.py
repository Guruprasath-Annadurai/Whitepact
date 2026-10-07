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


class BackupRejectedError(Exception):
    """A backup or restore input failed closed. The message has no key material."""


@dataclass(frozen=True)
class BackupArtifact:
    ciphertext_path: Path
    manifest_path: Path
    ciphertext_sha256: str
    plaintext_sha256: str


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


def seal_compressed(
    compressed: bytes,
    plaintext: bytes,
    secret: str,
    destination: Path,
    *,
    database: str,
    tool_version: str,
    required_relations: list[str] | None = None,
) -> BackupArtifact:
    if not compressed:
        raise BackupRejectedError("Refusing to encrypt an empty dump.")
    fernet, salt, kdf_name = _fernet(secret, None)
    token = fernet.encrypt(compressed)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(token)
    _chmod_private(destination)
    manifest_path = destination.with_name(destination.name + ".manifest.json")
    ciphertext_sha = _sha256(token)
    plaintext_sha = _sha256(plaintext)
    manifest = {
        "version": "1",
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
        "required_relations": list(required_relations or []),
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


def decrypt_dump(ciphertext_path: Path, manifest_path: Path, secret: str, work_dir: Path) -> Path:
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
        compressed = fernet.decrypt(token)
    except (InvalidToken, ValueError) as exc:
        raise BackupRejectedError(
            "Backup decryption failed. The key does not match this artifact."
        ) from exc
    try:
        plain = gzip.decompress(compressed)
    except (OSError, EOFError, gzip.BadGzipFile) as exc:
        raise BackupRejectedError("Decrypted backup is truncated or not gzip.") from exc
    expected_plain = manifest.get("plaintext_sha256")
    if not isinstance(expected_plain, str) or _sha256(plain) != expected_plain:
        raise BackupRejectedError("Decrypted backup checksum does not match the manifest.")
    assert_dump_bytes(plain)
    work_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(work_dir, stat.S_IRWXU)
    plain_path = work_dir / "restore.sql"
    plain_path.write_bytes(plain)
    _chmod_private(plain_path)
    return plain_path


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
