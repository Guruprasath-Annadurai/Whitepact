# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""In-process coverage of Gate 2 backup reject branches.

Shell drills invoke this code in a subprocess, which the parent coverage
run does not trace. These tests exercise the same reject paths directly.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from responsibleai.ops import __main__ as ops_main
from responsibleai.ops.backup_crypto import (
    SCHEMA_VERSION,
    TOOL_NAME,
    BackupRejectedError,
    _claims_from_header,
    _encode_payload,
    _fernet,
    _sidecar_matches_claims,
    _split_payload,
    assert_dump_bytes,
    assert_upload_allowed,
    decrypt_dump,
    encrypt_dump,
    load_manifest,
    seal_compressed,
)
from responsibleai.ops.restore_flow import (
    new_previous_name,
    prepare_restore,
    quote_ident,
)

DUMP = b"--\n-- PostgreSQL database dump\n--\nSELECT 1;\n"


def _key() -> str:
    return Fernet.generate_key().decode("ascii")


def _header(**overrides: object) -> dict[str, object]:
    header: dict[str, object] = {
        "version": SCHEMA_VERSION,
        "database": "fixture",
        "compression": "gzip",
        "pg_dump_format": "plain",
        "plaintext_sha256": "abc",
        "plaintext_bytes": 1,
        "required_relations": ["users"],
    }
    header.update(overrides)
    return header


def test_secret_and_plaintext_rejects() -> None:
    with pytest.raises(BackupRejectedError, match="single line"):
        _fernet("line\nbreak", None)
    with pytest.raises(BackupRejectedError, match="empty"):
        _fernet("  \t", None)
    fernet, salt, name = _fernet("not-a-fernet-key", None)
    assert name == "pbkdf2-hmac-sha256"
    assert salt and fernet
    with pytest.raises(BackupRejectedError, match="empty"):
        assert_dump_bytes(b" \n\t")
    with pytest.raises(BackupRejectedError, match="PostgreSQL"):
        assert_dump_bytes(b"not a dump")


def test_payload_and_claim_rejects() -> None:
    encoded = _encode_payload(_header(database="fixture"), b"abc")
    assert encoded.startswith(b"WPBAK1\n")
    with pytest.raises(BackupRejectedError, match="downgraded"):
        _split_payload(b"not-a-backup")
    with pytest.raises(BackupRejectedError, match="truncated"):
        _split_payload(b"WPBAK1\n{")
    with pytest.raises(BackupRejectedError, match="not JSON"):
        _split_payload(b"WPBAK1\n{bad\n")
    with pytest.raises(BackupRejectedError, match="object"):
        _split_payload(b"WPBAK1\n[]\n")
    with pytest.raises(BackupRejectedError, match="schema version"):
        _claims_from_header(_header(version=9))
    with pytest.raises(BackupRejectedError, match="database"):
        _claims_from_header(_header(database=""))
    with pytest.raises(BackupRejectedError, match="format"):
        _claims_from_header(_header(pg_dump_format="custom"))
    with pytest.raises(BackupRejectedError, match="metadata"):
        _claims_from_header(_header(plaintext_bytes=True))
    with pytest.raises(BackupRejectedError, match="required_relations"):
        _claims_from_header(_header(required_relations="users"))
    with pytest.raises(BackupRejectedError, match="required_relations"):
        _claims_from_header(_header(required_relations=["users", 1]))


def test_sidecar_shape_rejects() -> None:
    claims = _claims_from_header(_header())
    base = {
        "version": claims.version,
        "database": claims.database,
        "compression": claims.compression,
        "pg_dump_format": claims.pg_dump_format,
        "plaintext_sha256": claims.plaintext_sha256,
        "plaintext_bytes": claims.plaintext_bytes,
        "required_relations": list(claims.required_relations),
        "created_at": "2026-10-07T00:00:00Z",
        "tool": TOOL_NAME,
        "tool_version": "1.3.1",
    }
    with pytest.raises(BackupRejectedError, match="created_at"):
        _sidecar_matches_claims({**base, "created_at": "yesterday"}, claims)
    with pytest.raises(BackupRejectedError, match="tool name"):
        _sidecar_matches_claims({**base, "tool": "  "}, claims)
    with pytest.raises(BackupRejectedError, match="tool_version"):
        _sidecar_matches_claims({**base, "tool_version": ""}, claims)
    with pytest.raises(BackupRejectedError, match="database"):
        _sidecar_matches_claims({**base, "database": "other"}, claims)


def test_seal_manifest_and_upload_rejects(tmp_path: Path) -> None:
    with pytest.raises(BackupRejectedError, match="empty dump"):
        seal_compressed(b"", DUMP, _key(), tmp_path / "x.enc", database="fixture", tool_version="1")
    missing = tmp_path / "gone.manifest.json"
    with pytest.raises(BackupRejectedError, match="missing"):
        load_manifest(missing)
    bad = tmp_path / "bad.manifest.json"
    bad.write_text("{", encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="not JSON"):
        load_manifest(bad)
    listed = tmp_path / "list.manifest.json"
    listed.write_text("[]\n", encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="object"):
        load_manifest(listed)

    secret = _key()
    dest = tmp_path / "ok.sql.gz.enc"
    encrypt_dump(
        DUMP, secret, dest, database="fixture", tool_version="1.3.1", required_relations=["users"]
    )
    with pytest.raises(BackupRejectedError, match="plaintext SQL"):
        assert_upload_allowed(tmp_path / "plain.sql")
    other = tmp_path / "notes.txt"
    other.write_bytes(b"x")
    with pytest.raises(BackupRejectedError, match=".enc"):
        assert_upload_allowed(other)
    token = dest.read_bytes()
    dest.write_bytes(token + b"x")
    with pytest.raises(BackupRejectedError, match="checksum"):
        assert_upload_allowed(dest)
    dest.write_bytes(token)
    manifest_path = Path(str(dest) + ".manifest.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["authenticated"] = False
    manifest["ciphertext_sha256"] = hashlib.sha256(token).hexdigest()
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="unauthenticated"):
        assert_upload_allowed(dest)


def test_decrypt_rejects_before_restore(tmp_path: Path) -> None:
    secret = _key()
    dest = tmp_path / "ok.sql.gz.enc"
    encrypt_dump(DUMP, secret, dest, database="fixture", tool_version="1.3.1")
    manifest_path = Path(str(dest) + ".manifest.json")
    work = tmp_path / "work"
    missing = tmp_path / "absent.enc"
    with pytest.raises(BackupRejectedError, match="does not exist"):
        decrypt_dump(missing, manifest_path, secret, work)
    empty = tmp_path / "empty.enc"
    empty.write_bytes(b"")
    with pytest.raises(BackupRejectedError, match="empty"):
        decrypt_dump(empty, manifest_path, secret, work)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["ciphertext_sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="checksum"):
        decrypt_dump(dest, manifest_path, secret, work)
    manifest["ciphertext_sha256"] = hashlib.sha256(dest.read_bytes()).hexdigest()
    manifest["cipher"] = "none"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="authenticated"):
        decrypt_dump(dest, manifest_path, secret, work)
    manifest["cipher"] = "fernet"
    manifest["kdf"] = "pbkdf2-hmac-sha256"
    manifest["kdf_salt_b64"] = "abc"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(BackupRejectedError, match="salt"):
        decrypt_dump(dest, manifest_path, secret, work)


def test_restore_identifier_and_cli_rejects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(BackupRejectedError, match="safe identifier"):
        quote_ident("bad-name")
    previous = new_previous_name("a" * 63)
    assert previous.startswith("wp_prev_")
    secret = _key()
    dest = tmp_path / "ok.sql.gz.enc"
    encrypt_dump(
        DUMP,
        secret,
        dest,
        database="fixture",
        tool_version="1.3.1",
        required_relations=["bad-rel"],
    )
    with pytest.raises(BackupRejectedError, match="unsafe name"):
        prepare_restore(dest, secret, tmp_path / "work")
    monkeypatch.delenv("WHITEPACT_BACKUP_ENCRYPTION_KEY", raising=False)
    with pytest.raises(BackupRejectedError, match="is not set"):
        ops_main._secret()
    monkeypatch.setenv("WHITEPACT_BACKUP_ENCRYPTION_KEY", secret)
    plain = tmp_path / "plain.sql"
    plain.write_bytes(DUMP)
    out = tmp_path / "cli.sql.gz.enc"
    assert (
        ops_main.main(
            [
                "encrypt",
                "--input",
                str(plain),
                "--output",
                str(out),
                "--database",
                "fixture",
                "--relation",
                "users",
            ]
        )
        == 0
    )
    assert ops_main.main(["upload-check", "--backup", str(out)]) == 0
    assert (
        ops_main.main(
            ["prepare-restore", "--backup", str(out), "--work", str(tmp_path / "cli-work")]
        )
        == 0
    )
    assert ops_main.main(["upload-check", "--backup", str(tmp_path / "missing.enc")]) == 2


def test_truncated_gzip_is_rejected(tmp_path: Path) -> None:
    secret = _key()
    compressed = gzip.compress(DUMP, mtime=0)
    dest = tmp_path / "cut.sql.gz.enc"
    seal_compressed(
        compressed[:8],
        DUMP,
        secret,
        dest,
        database="fixture",
        tool_version="1.3.1",
    )
    with pytest.raises(BackupRejectedError, match="truncated|gzip|authenticated header"):
        decrypt_dump(dest, Path(str(dest) + ".manifest.json"), secret, tmp_path / "work")
