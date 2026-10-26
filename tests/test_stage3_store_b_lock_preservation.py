# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Existing Store B validation must not release another SQLite transaction's locks."""

import sqlite3
import stat
import subprocess
import sys
from contextlib import closing

import pytest

from responsibleai.data_governance.backup_defense import (
    MissingLifecycleProviderError,
    SqliteDurableLifecycleStateProvider,
    _secure_create_store_b_file,
)


def competing_lock(path):
    # Observe only the POSIX lock range used by SQLite; never write database
    # bytes or let a second writer corrupt even this disposable test database.
    code = """
import fcntl, os, sys
fd = os.open(sys.argv[1], os.O_RDWR)
try:
    try:
        fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB, 510, 0x40000002, os.SEEK_SET)
    except BlockingIOError:
        print('BLOCKED')
    else:
        print('ACQUIRED')
finally:
    os.close(fd)
"""
    result = subprocess.run(
        [sys.executable, "-c", code, str(path)],
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert result.stdout.strip() in {"BLOCKED", "ACQUIRED"}
    return result.stdout.strip()


def test_existing_store_validation_preserves_live_sqlite_exclusive_lock(tmp_path):
    path = tmp_path / "owned-lifecycle.sqlite3"
    _secure_create_store_b_file(path)
    with closing(sqlite3.connect(path, isolation_level=None)) as holder:
        holder.execute("PRAGMA journal_mode=DELETE")
        holder.execute("CREATE TABLE lock_probe (value INTEGER)")
        holder.execute("BEGIN EXCLUSIVE")
        assert competing_lock(path) == "BLOCKED"
        _secure_create_store_b_file(path)
        assert competing_lock(path) == "BLOCKED", "Store validation released an active SQLite lock"
        holder.execute("ROLLBACK")
    assert competing_lock(path) == "ACQUIRED"


def test_existing_private_store_validation_preserves_inode_and_data(tmp_path):
    path = tmp_path / "private.sqlite3"
    provider = SqliteDurableLifecycleStateProvider(path)
    before = path.stat()
    data = path.read_bytes()
    _secure_create_store_b_file(path)
    assert path.stat().st_ino == before.st_ino
    assert path.read_bytes() == data
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert provider.verify_integrity()


@pytest.mark.parametrize("kind", ["public_file", "directory", "symlink", "dangling_symlink"])
def test_existing_unsafe_store_is_rejected_without_repair(tmp_path, kind):
    path = tmp_path / "unsafe.sqlite3"
    if kind == "directory":
        path.mkdir()
    elif kind in {"symlink", "dangling_symlink"}:
        target = tmp_path / "target.sqlite3"
        if kind == "symlink":
            target.write_bytes(b"unchanged")
        path.symlink_to(target)
    else:
        path.write_bytes(b"unchanged")
        path.chmod(0o644)
    with pytest.raises(MissingLifecycleProviderError):
        _secure_create_store_b_file(path)
    if kind == "public_file":
        assert path.read_bytes() == b"unchanged"
        assert stat.S_IMODE(path.stat().st_mode) == 0o644


def test_corrupt_private_store_is_not_recreated(tmp_path):
    path = tmp_path / "corrupt.sqlite3"
    path.write_bytes(b"invalid-lifecycle-evidence")
    path.chmod(0o600)
    with pytest.raises(sqlite3.DatabaseError):
        SqliteDurableLifecycleStateProvider(path)
    assert path.read_bytes() == b"invalid-lifecycle-evidence"
