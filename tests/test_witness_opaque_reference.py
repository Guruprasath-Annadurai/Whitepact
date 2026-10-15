# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Witness record v2: the public record names no tenant; verification stays public and independent."""

from __future__ import annotations

import json
import os
import shutil
import stat

import pytest

from responsibleai.governance.evidence_publication import (
    AppendOnlyWitnessLog,
    FileWitnessKeyStore,
    WitnessPublicationError,
    publish_evidence_head,
    verify_publication_chain,
    verify_published_head,
)

ORG_A, ORG_B = "acme-corp-secret-name", "globex-industries"


def _pub(store, log, org: str, seq: int, head: str, **kw):
    return publish_evidence_head(
        store,
        log,
        organization_id=org,
        chain_sequence=seq,
        head_hash=head,
        witnessed_at="2026-10-11T00:00:00+00:00",
        required=True,
        **kw,
    )


@pytest.fixture()
def world(tmp_path):
    store = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "log")
    return store, log, tmp_path


def test_v2_is_the_default_and_the_public_tree_contains_no_tenant_identifier(world) -> None:
    store, log, root = world
    first = _pub(store, log, ORG_A, 1, "a" * 64)
    _pub(store, log, ORG_A, 2, "b" * 64)
    _pub(store, log, ORG_B, 1, "c" * 64)
    assert first.record_version == 2 and first.organization_id.startswith("wr1_")
    for path in (root / "log").rglob("*"):
        assert ORG_A not in str(path) and ORG_B not in str(path)  # directory and file names
        if path.is_file():
            text = path.read_text()
            assert ORG_A not in text and ORG_B not in text
    for path in (root / "keys" / "public").rglob("*"):
        assert path.is_file() and ORG_A.encode() not in path.read_bytes()


def test_v2_record_has_exactly_the_documented_fields(world) -> None:
    store, log, root = world
    ref = _pub(store, log, ORG_A, 1, "a" * 64).organization_id
    data = json.loads((root / "log" / ref / "1.json").read_text())
    assert set(data) == {
        "record_version",
        "witness_ref",
        "chain_sequence",
        "head_hash",
        "witnessed_at",
        "key_id",
        "public_key_hex",
        "signature_hex",
        "previous_publication_hash",
        "publication_hash",
    }
    assert "organization_id" not in data


def test_references_are_stable_distinct_and_depend_on_a_secret(world, tmp_path) -> None:
    store, _log, _ = world
    a, b = store.witness_reference(ORG_A), store.witness_reference(ORG_B)
    assert a != b and a == store.witness_reference(ORG_A)
    assert a == FileWitnessKeyStore(tmp_path / "keys").witness_reference(ORG_A)  # survives reopen
    other = FileWitnessKeyStore.create(tmp_path / "other-keys")
    assert other.witness_reference(ORG_A) != a  # not derivable without this store's secret
    assert len(a) <= 40 and a.isascii() and a == a.lower()


def test_reference_secret_is_private_and_never_published(world) -> None:
    store, log, root = world
    _pub(store, log, ORG_A, 1, "a" * 64)
    secret_path = root / "keys" / "private" / "witness_ref.key"
    assert stat.S_IMODE(secret_path.stat().st_mode) == 0o600
    secret = secret_path.read_bytes()
    for path in (root / "log").rglob("*"):
        if path.is_file():
            blob = path.read_bytes()
            assert secret not in blob and secret.hex().encode() not in blob
    os.chmod(secret_path, 0o644)
    with pytest.raises(Exception, match="group or world"):
        store.reference_secret()


def test_independent_verification_works_from_the_reference_alone(world) -> None:
    store, log, root = world
    ref = _pub(store, log, ORG_A, 1, "a" * 64).organization_id
    _pub(store, log, ORG_A, 2, "b" * 64)
    # A verifier is given only the reference and the claimed head; it reopens the log from disk.
    reopened = AppendOnlyWitnessLog(root / "log")
    assert verify_published_head(
        reopened, organization_id=ref, chain_sequence=2, head_hash="b" * 64
    )
    verify_publication_chain(reopened.history(ref))
    with pytest.raises(WitnessPublicationError, match="rolled back"):
        verify_published_head(reopened, organization_id=ref, chain_sequence=1, head_hash="a" * 64)
    with pytest.raises(WitnessPublicationError, match="does not match"):
        verify_published_head(reopened, organization_id=ref, chain_sequence=2, head_hash="f" * 64)
    # The real organization id names nothing in the public log.
    with pytest.raises(WitnessPublicationError, match="missing"):
        verify_published_head(reopened, organization_id=ORG_A, chain_sequence=2, head_hash="b" * 64)


def test_tampering_with_a_v2_record_is_detected(world) -> None:
    store, log, root = world
    ref = _pub(store, log, ORG_A, 1, "a" * 64).organization_id
    path = root / "log" / ref / "1.json"
    data = json.loads(path.read_text())
    data["head_hash"] = "d" * 64
    path.write_text(json.dumps(data))
    with pytest.raises(WitnessPublicationError):
        verify_publication_chain(AppendOnlyWitnessLog(root / "log").history(ref))
    data["head_hash"] = "a" * 64
    data["record_version"] = 1  # downgrade attempt
    path.write_text(json.dumps(data))
    with pytest.raises((WitnessPublicationError, KeyError)):
        verify_publication_chain(AppendOnlyWitnessLog(root / "log").history(ref))


def test_a_record_copied_into_another_tenants_directory_is_refused(world) -> None:
    store, log, root = world
    ref_a = _pub(store, log, ORG_A, 1, "a" * 64).organization_id
    ref_b = _pub(store, log, ORG_B, 1, "c" * 64).organization_id
    (root / "log" / ref_b / "1.json").unlink()
    shutil.copy(root / "log" / ref_a / "1.json", root / "log" / ref_b / "1.json")
    with pytest.raises(WitnessPublicationError, match="does not match its location"):
        AppendOnlyWitnessLog(root / "log").history(ref_b)


def test_legacy_v1_records_still_read_and_verify(world) -> None:
    store, log, root = world
    legacy = _pub(store, log, ORG_A, 1, "a" * 64, opaque_reference=False)
    assert legacy.record_version == 1 and legacy.organization_id == ORG_A
    assert json.loads((root / "log" / ORG_A / "1.json").read_text())["organization_id"] == ORG_A
    verify_publication_chain(AppendOnlyWitnessLog(root / "log").history(ORG_A))
