# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real private SQLite receipt ledger; no execution-admission side effects."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from responsibleai.data_governance.operator_recovery import (
    RecoveryAuthorizationError,
    RecoveryReceiptLedger,
)
from tests.test_operator_recovery_authorization import fixture_request


def consume(ledger, manifest, trust, signatures):
    return ledger.consume_approvals(
        manifest,
        trust,
        signatures,
        now=1010,
        deployment_id="isolated-test",
        environment="test",
        current_evidence_digest=manifest.evidence_digest,
    )


def test_consumption_survives_reopen_and_rejects_replay(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    digest = consume(RecoveryReceiptLedger(path), manifest, trust, signatures)
    assert digest == manifest.digest()
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        consume(RecoveryReceiptLedger(path), manifest, trust, signatures)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT state FROM recovery_receipts").fetchall() == [
            ("CONSUMED",)
        ]


def test_missing_ledger_never_implicitly_reinitialized(tmp_path):
    with pytest.raises(RecoveryAuthorizationError):
        RecoveryReceiptLedger(tmp_path / "missing.sqlite3")


def test_initialization_never_overwrites_existing_ledger(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    with pytest.raises(FileExistsError):
        RecoveryReceiptLedger.initialize(path)


def test_failed_signature_burns_authorization(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    with pytest.raises(RecoveryAuthorizationError):
        consume(RecoveryReceiptLedger(path), manifest, trust, {})
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        consume(RecoveryReceiptLedger(path), manifest, trust, signatures)
    with sqlite3.connect(path) as connection:
        assert connection.execute("SELECT state FROM recovery_receipts").fetchone() == ("REJECTED",)


def test_changed_evidence_burns_authorization(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    ledger = RecoveryReceiptLedger(path)
    with pytest.raises(RecoveryAuthorizationError, match="Evidence changed"):
        ledger.consume_approvals(
            manifest,
            trust,
            signatures,
            now=1010,
            deployment_id="isolated-test",
            environment="test",
            current_evidence_digest="f" * 64,
        )
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        consume(ledger, manifest, trust, signatures)


def test_nonce_cannot_be_rebound_to_another_request(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    ledger = RecoveryReceiptLedger(path)
    consume(ledger, manifest, trust, signatures)
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        consume(ledger, replace(manifest, request_id="another"), trust, signatures)


def test_concurrent_consumption_has_exactly_one_winner(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()

    def attempt():
        try:
            consume(RecoveryReceiptLedger(path), manifest, trust, signatures)
            return "consumed"
        except RecoveryAuthorizationError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as workers:
        results = list(workers.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["consumed", "rejected"]


def test_interrupted_attempt_stays_consumed_after_restart(tmp_path):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO recovery_receipts(request_id,nonce,manifest_digest,state) "
            "VALUES(?,?,?,'ATTEMPTED')",
            (manifest.request_id, manifest.nonce, manifest.digest()),
        )
    with pytest.raises(RecoveryAuthorizationError, match="already consumed"):
        consume(RecoveryReceiptLedger(path), manifest, trust, signatures)


@pytest.mark.parametrize("case", ["corrupt", "symlink", "public_mode"])
def test_invalid_ledger_state_fails_closed(tmp_path, case):
    path = tmp_path / "operator-ledger.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    manifest, trust, signatures = fixture_request()
    if case == "corrupt":
        path.write_bytes(b"not a sqlite database")
    elif case == "public_mode":
        path.chmod(0o644)
    else:
        link = tmp_path / "link.sqlite3"
        link.symlink_to(path)
        path = link
    with pytest.raises(RecoveryAuthorizationError):
        consume(RecoveryReceiptLedger(path), manifest, trust, signatures)
