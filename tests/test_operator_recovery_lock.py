# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real nonblocking flock refusal; no mocked recovery authorization."""

import multiprocessing
from types import SimpleNamespace

import pytest

from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from tests.stage3_restore_transport import _exclusive_restore_operation as _exclusive_operation


def test_competing_operation_has_deterministic_refusal_and_cannot_enter(tmp_path):
    profile = SimpleNamespace(ledger_path=tmp_path / "receipts.sqlite3")
    entered = False
    with _exclusive_operation(profile):
        with pytest.raises(RecoveryAuthorizationError, match="already in progress"):
            with _exclusive_operation(profile):
                entered = True
        assert not entered
        # Refusal must not release the original owner's lock.
        with pytest.raises(RecoveryAuthorizationError, match="already in progress"):
            with _exclusive_operation(profile):
                entered = True
    assert not entered
    with _exclusive_operation(profile):
        entered = True
    assert entered


def test_body_io_failure_is_not_misclassified_as_lock_contention(tmp_path):
    profile = SimpleNamespace(ledger_path=tmp_path / "receipts.sqlite3")
    with pytest.raises(BlockingIOError, match="body failure"):
        with _exclusive_operation(profile):
            raise BlockingIOError("body failure")
    with _exclusive_operation(profile):
        pass


def _hold_in_worker(path, ready, release):
    with _exclusive_operation(SimpleNamespace(ledger_path=path)):
        ready.set()
        if not release.wait(15):
            raise RuntimeError("Test owner release timed out")


def test_separate_process_owner_prevents_overlap_and_restart_reacquires(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    profile = SimpleNamespace(ledger_path=tmp_path / "receipts.sqlite3")
    worker = context.Process(target=_hold_in_worker, args=(profile.ledger_path, ready, release))
    worker.start()
    try:
        assert ready.wait(15)
        with pytest.raises(RecoveryAuthorizationError, match="already in progress"):
            with _exclusive_operation(profile):
                pytest.fail("Competing recovery entered the critical section")
        release.set()
        worker.join(15)
        assert worker.exitcode == 0
        with _exclusive_operation(profile):
            pass
    finally:
        release.set()
        if worker.is_alive():
            worker.terminate()
        worker.join(5)
