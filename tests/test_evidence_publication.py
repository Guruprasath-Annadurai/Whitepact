# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent evidence publication. Local files are not a live object-store witness."""

from __future__ import annotations

import json
import os
import stat
from datetime import UTC, datetime, timedelta
from urllib.request import Request

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from responsibleai.governance.evidence_publication import (
    LIVE_OBJECT_STORE_STATUS,
    AppendOnlyWitnessLog,
    FileWitnessKeyStore,
    WitnessPublicationError,
    WitnessRequiredUnavailableError,
    live_object_store_status,
    object_lock_headers,
    publish_evidence_head,
    put_object_lock,
    verify_published_head,
)
from responsibleai.governance.evidence_witness import LIVE_ANCHOR_STATUS
from responsibleai.isolation.environment import build_isolated_environment


def _publish(store: FileWitnessKeyStore, log: AppendOnlyWitnessLog, sequence: int, head: str):
    return publish_evidence_head(
        store,
        log,
        organization_id="org-a",
        chain_sequence=sequence,
        head_hash=head,
        witnessed_at="2026-10-09T00:00:00+00:00",
        required=True,
    )


def test_live_anchor_constants_do_not_claim_a_provisioned_witness() -> None:
    assert LIVE_ANCHOR_STATUS == "EXTERNAL_BLOCKER"
    assert LIVE_OBJECT_STORE_STATUS == "NOT_PROVISIONED"
    assert live_object_store_status({}) == "NOT_PROVISIONED"
    configured = {
        "WHITEPACT_EVIDENCE_S3_ENDPOINT": "https://example.r2.cloudflarestorage.com",
        "WHITEPACT_EVIDENCE_S3_BUCKET": "witness",
        "WHITEPACT_EVIDENCE_S3_ACCESS_KEY_ID": "access",
        "WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY": "secret",
    }
    assert live_object_store_status(configured) == "CONFIGURED_UNVERIFIED"


def test_publication_verifies_outside_the_database_and_survives_reopen(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    directory = tmp_path / "log"
    first = _publish(store, AppendOnlyWitnessLog(directory), 1, "a" * 64)
    second = _publish(store, AppendOnlyWitnessLog(directory), 2, "b" * 64)
    reopened = AppendOnlyWitnessLog(directory)
    verified = verify_published_head(
        reopened,
        organization_id="org-a",
        chain_sequence=2,
        head_hash="b" * 64,
    )
    assert verified.publication_hash == second.publication_hash
    assert verified.previous_publication_hash == first.publication_hash
    assert verified.key_id == store.current_key_id()


def test_rollback_rewrite_gap_and_missing_publication_are_detected(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    _publish(store, log, 1, "a" * 64)
    _publish(store, log, 2, "b" * 64)
    with pytest.raises(WitnessPublicationError, match="rolled back"):
        verify_published_head(
            log,
            organization_id="org-a",
            chain_sequence=1,
            head_hash="a" * 64,
        )
    with pytest.raises(WitnessPublicationError, match="does not match"):
        verify_published_head(
            log,
            organization_id="org-a",
            chain_sequence=2,
            head_hash="c" * 64,
        )
    with pytest.raises(WitnessPublicationError, match="missing"):
        verify_published_head(
            AppendOnlyWitnessLog(tmp_path / "empty"),
            organization_id="org-a",
            chain_sequence=1,
            head_hash="a" * 64,
        )
    with pytest.raises(WitnessPublicationError, match="strictly newer"):
        publish_evidence_head(
            store,
            log,
            organization_id="org-a",
            chain_sequence=2,
            head_hash="b" * 64,
            witnessed_at="2026-10-09T00:00:00+00:00",
            required=False,
        )


def test_rewritten_publication_file_breaks_the_publication_hash(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    _publish(store, log, 1, "a" * 64)
    path = tmp_path / "log" / "org-a" / "1.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["head_hash"] = "d" * 64
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(WitnessPublicationError, match="publication hash"):
        verify_published_head(
            log,
            organization_id="org-a",
            chain_sequence=1,
            head_hash="d" * 64,
        )


def test_key_rotation_keeps_the_previous_public_key(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    first = _publish(store, log, 1, "a" * 64)
    rotated = store.rotate()
    second = _publish(store, log, 2, "b" * 64)
    assert first.key_id != rotated
    assert second.key_id == rotated
    store.public_key(first.key_id)
    verify_published_head(
        log,
        organization_id="org-a",
        chain_sequence=2,
        head_hash="b" * 64,
    )


def test_private_key_mode_and_required_failure(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    key_path = tmp_path / "keys" / "private" / "current.key"
    assert stat.S_IMODE(key_path.stat().st_mode) == 0o600
    os.chmod(key_path, 0o644)
    with pytest.raises(WitnessRequiredUnavailableError):
        _publish(store, AppendOnlyWitnessLog(tmp_path / "log"), 1, "a" * 64)


def test_witness_material_is_not_copied_into_agent_execution(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("WHITEPACT_EVIDENCE_WITNESS_KEY_DIR", str(tmp_path))
    monkeypatch.setenv("WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY", "super-secret")
    monkeypatch.setenv("PATH", "/usr/bin")
    clean = build_isolated_environment(
        organization_id="org-a",
        action_id="act",
        extra_env={
            "WHITEPACT_EVIDENCE_WITNESS_KEY_DIR": str(tmp_path),
            "WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY": "super-secret",
            "LANG": "C",
        },
    )
    assert "WHITEPACT_EVIDENCE_WITNESS_KEY_DIR" not in clean
    assert "WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY" not in clean
    assert "super-secret" not in clean.values()


def test_object_lock_put_sends_retention_and_fails_closed() -> None:
    headers = object_lock_headers(retain_until=datetime.now(UTC) + timedelta(days=30))
    assert headers["x-amz-object-lock-mode"] == "COMPLIANCE"
    assert headers["If-None-Match"] == "*"
    seen: dict[str, str] = {}

    def transport(request: Request) -> tuple[int, bytes]:
        headers = {name.lower(): value for name, value in request.header_items()}
        seen["mode"] = headers.get("x-amz-object-lock-mode", "")
        seen["match"] = headers.get("if-none-match", "")
        seen["authorization"] = headers.get("authorization", "")
        return 200, b""

    status = put_object_lock(
        endpoint="https://example.r2.cloudflarestorage.com",
        bucket="witness",
        key="org-a/1.json",
        body=b"{}",
        access_key_id="access",
        secret_access_key="secret",
        transport=transport,
    )
    assert status == 200
    assert seen["mode"] == "COMPLIANCE"
    assert seen["match"] == "*"
    assert seen["authorization"].startswith("AWS4-HMAC-SHA256 ")
    assert live_object_store_status({}) == "NOT_PROVISIONED"

    def rejected(_request: Request) -> tuple[int, bytes]:
        return 403, b"denied"

    with pytest.raises(WitnessRequiredUnavailableError, match="403"):
        put_object_lock(
            endpoint="https://example.r2.cloudflarestorage.com",
            bucket="witness",
            key="org-a/1.json",
            body=b"{}",
            access_key_id="access",
            secret_access_key="secret",
            transport=rejected,
        )


def test_signing_key_object_is_not_a_string_export(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys", Ed25519PrivateKey.generate())
    key_id, private = store.current_private()
    assert key_id
    assert not isinstance(private, str)


@pytest.mark.parametrize(
    "endpoint",
    [
        "file:///etc/passwd",
        "ftp://example.com",
        "http://example.r2.cloudflarestorage.com",
        "https://",
        "example.r2.cloudflarestorage.com",
        "https://user:pass@example.r2.cloudflarestorage.com",
        "https://example.r2.cloudflarestorage.com?x=1",
        "https://example.r2.cloudflarestorage.com#frag",
    ],
)
def test_object_store_endpoint_must_be_a_plain_https_origin(endpoint: str) -> None:
    """Bandit B310: the signed request must never reach file:, ftp:, http: or odd URLs."""
    called: list[Request] = []

    def transport(request: Request) -> tuple[int, bytes]:
        called.append(request)
        return 200, b""

    with pytest.raises(WitnessRequiredUnavailableError, match="https|credentials"):
        put_object_lock(
            endpoint=endpoint,
            bucket="witness",
            key="org-a/1.json",
            body=b"{}",
            access_key_id="access",
            secret_access_key="secret",
            transport=transport,
        )
    assert called == []


def test_real_transport_refuses_a_non_https_request_before_any_network_io() -> None:
    from responsibleai.governance import evidence_publication as ep

    with pytest.raises(WitnessRequiredUnavailableError, match="https"):
        ep._urllib_transport(Request("file:///etc/passwd", data=b"{}", method="PUT"))


def test_real_transport_never_follows_a_redirect() -> None:
    """A signed Authorization header must not be replayed to a redirect target."""
    from responsibleai.governance import evidence_publication as ep

    handler = ep._NoRedirect()
    request = Request("https://example.r2.cloudflarestorage.com/b/k", data=b"{}", method="PUT")
    assert (
        handler.redirect_request(
            request, None, 307, "Temporary Redirect", {}, "https://evil.example/"
        )
        is None
    )


def _mode(path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_public_witness_material_never_contains_private_key_bytes(tmp_path) -> None:
    """The log and public key directory are intentionally world-readable. They must stay public-only."""
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    private_raw = (store.private_dir / "current.key").read_bytes()
    log = AppendOnlyWitnessLog(tmp_path / "log")
    _publish(store, log, 1, "a" * 64)
    _publish(store, log, 2, "b" * 64)
    public_files = [p for p in (tmp_path / "log").rglob("*") if p.is_file()]
    public_files += [p for p in store.public_dir.rglob("*") if p.is_file()]
    assert public_files
    for path in public_files:
        data = path.read_bytes()
        assert private_raw not in data, path
        assert private_raw.hex().encode() not in data, path
        assert b"private" not in data.lower(), path
        assert _mode(path) == 0o644, (
            path
        )  # published records are read-only to everyone but the owner


def test_public_record_fields_are_exactly_the_documented_set(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    _publish(store, log, 1, "a" * 64)
    record = json.loads(next((tmp_path / "log").rglob("1.json")).read_text())
    assert set(record) == {
        "organization_id",
        "chain_sequence",
        "head_hash",
        "witnessed_at",
        "key_id",
        "public_key_hex",
        "signature_hex",
        "previous_publication_hash",
        "publication_hash",
    }


def test_witness_directories_are_not_writable_by_group_or_other_even_with_umask_zero(
    tmp_path,
) -> None:
    """Publication authority is write access to these directories. umask must not widen it."""
    previous = os.umask(0)
    try:
        store = FileWitnessKeyStore.create(tmp_path / "keys")
        log = AppendOnlyWitnessLog(tmp_path / "log")
        _publish(store, log, 1, "a" * 64)
    finally:
        os.umask(previous)
    assert _mode(store.private_dir) == 0o700
    assert _mode(store.private_dir / "current.key") == 0o600
    for directory in (
        tmp_path / "keys" / "public",
        tmp_path / "log",
        tmp_path / "log" / "org-a",
    ):
        assert _mode(directory) & 0o022 == 0, directory
    for path in (tmp_path / "log" / "org-a").iterdir():
        assert _mode(path) & 0o022 == 0, path


def test_a_published_sequence_cannot_be_overwritten_in_place(tmp_path) -> None:
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    _publish(store, log, 1, "a" * 64)
    with pytest.raises(WitnessPublicationError):
        _publish(store, log, 1, "c" * 64)
