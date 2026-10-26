# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M13-H1: Tenant Identifier Collision Invariance & Registration Boundary Suite.

Mandatory 20-Scenario Verification Matrix:
1.  Distinct tenant/execution pairs never accidentally resolve to same filename.
2.  Organization identifiers containing underscores.
3.  Execution identifiers containing underscores.
4.  Identifiers containing double underscores.
5.  Unicode identifiers (CJK, Arabic, Cyrillic, emoji).
6.  Percent characters (%20, %2F, %00).
7.  Slashes and traversal attempts (../../etc/passwd).
8.  Empty identifiers ("", "exec").
9.  Very long identifiers (10,000 characters).
10. Case and Unicode normalization (NFC equivalence).
11. Concurrent registrations across tenants.
12. Existing valid registrations readable and exact.
13. Legacy filename migration and coexistence.
14. Legacy tracking reads without data leakage.
15. Malformed/conflicting legacy records quarantined, not deleted.
16. Cross-tenant denial in distributed scans.
17. Process-death recovery preserves unconfirmed containment.
18. Unresolved-container retention policy.
19. Filesystem permission failures handled gracefully.
20. No unauthorized tracking deletion across tenants.
"""

from __future__ import annotations

import asyncio
import json
import os
import time
import unicodedata
from unittest.mock import patch

import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.isolation.in_flight import (
    InFlightExecution,
    _check_remote_worker_active,
    _record_cross_worker_registration,
    _remove_cross_worker_registration,
    _tracking_filename,
)


@pytest.fixture()
def isolated_tracking_dir(tmp_path, monkeypatch):
    t_dir = tmp_path / "distributed_tracking"
    t_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", t_dir)
    return t_dir


def _make_in_flight(org_id: str, exec_id: str, pid: int | None = None) -> InFlightExecution:
    return InFlightExecution(
        execution_id=exec_id,
        organization_id=org_id,
        action_id=f"act-{exec_id}",
        authorization_id=f"authz-{exec_id}",
        task=None,
        terminate_callback=None,
        created_at=time.time(),
        containment_status="active",
    )


def _scan_remote(org_id: str | None, scanner_pid: int = 999999):
    """Simulate a remote worker scanning the distributed directory.

    Sets current scanner PID to a distinct value and mocks os.kill to return None (process alive).
    """
    with patch("os.getpid", return_value=scanner_pid), patch("os.kill", return_value=None):
        return _check_remote_worker_active(org_id)


# Scenario 1: Distinct tenant/execution pairs never accidentally resolve to same filename
def test_01_distinct_pairs_never_collide():
    # The canonical counterexample from CTO Directive:
    # org="a_", exec="b" vs org="a", exec="_b"
    f1 = _tracking_filename("a_", "b")
    f2 = _tracking_filename("a", "_b")
    assert f1 != f2
    assert len(f1) == 141
    assert len(f2) == 141

    pairs = [
        ("tenant", "1_2"),
        ("tenant_1", "2"),
        ("org", "sub_exec"),
        ("org_sub", "exec"),
        ("acme", "__task__"),
        ("acme__task", "__"),
    ]
    seen = set()
    for o, e in pairs:
        fn = _tracking_filename(o, e)
        assert fn not in seen, f"Collision detected for pair ({o}, {e})"
        seen.add(fn)


# Scenario 2: Organization identifiers containing underscores
def test_02_org_ids_containing_underscores():
    orgs = ["org_a", "org_a_b", "org_a_b_c", "finance_eu_prod_cluster_1"]
    filenames = {_tracking_filename(org, "exec1") for org in orgs}
    assert len(filenames) == len(orgs)


# Scenario 3: Execution identifiers containing underscores
def test_03_execution_ids_containing_underscores():
    execs = ["exec_1", "exec_1_2", "exec_1_2_3", "task_worker_background_99"]
    filenames = {_tracking_filename("org1", ex) for ex in execs}
    assert len(filenames) == len(execs)


# Scenario 4: Identifiers containing double underscores
def test_04_identifiers_containing_double_underscores():
    f1 = _tracking_filename("org__alpha", "exec__beta")
    f2 = _tracking_filename("org", "alpha__exec__beta")
    f3 = _tracking_filename("org__alpha__exec", "beta")
    assert len({f1, f2, f3}) == 3


# Scenario 5: Unicode identifiers (CJK, Arabic, Cyrillic, emoji)
def test_05_unicode_identifiers(isolated_tracking_dir):
    unicode_orgs = ["org-🏢-japan", "tenant_日本語", "user_مرحبا", "организация_тест", "éxec_ñ"]
    for org in unicode_orgs:
        entry = _make_in_flight(org, "exec-unicode")
        _record_cross_worker_registration(entry)

    # All files written successfully with valid POSIX filenames
    files = list(isolated_tracking_dir.glob("trk_v2_*.json"))
    assert len(files) == len(unicode_orgs)
    # Scan matches specific unicode tenant exactly
    res = _scan_remote("org-🏢-japan")
    assert len(res) == 1
    assert res[0]["organization_id"] == "org-🏢-japan"


# Scenario 6: Percent characters (%20, %2F, %00)
def test_06_percent_characters():
    f1 = _tracking_filename("org%20name", "exec%2Fpath")
    f2 = _tracking_filename("org name", "exec/path")
    assert f1 != f2
    # Filename contains only hex and delimiters, no raw %
    assert "%" not in f1
    assert "/" not in f1


# Scenario 7: Slashes and traversal attempts (../../etc/passwd)
def test_07_slashes_and_traversal_attempts(isolated_tracking_dir):
    entry = _make_in_flight("../../../etc/passwd", "malicious/exec/id")
    _record_cross_worker_registration(entry)

    # File must be strictly inside isolated_tracking_dir, not escaped
    files = list(isolated_tracking_dir.iterdir())
    assert len(files) == 1
    assert files[0].parent.resolve() == isolated_tracking_dir.resolve()
    assert "passwd" not in files[0].name


# Scenario 8: Empty identifiers ("", "exec")
def test_08_empty_identifiers():
    f_empty_org = _tracking_filename("", "exec1")
    f_empty_exec = _tracking_filename("org1", "")
    f_both_empty = _tracking_filename("", "")
    assert len({f_empty_org, f_empty_exec, f_both_empty}) == 3
    assert all(len(f) == 141 for f in [f_empty_org, f_empty_exec, f_both_empty])


# Scenario 9: Very long identifiers (10,000 characters)
def test_09_very_long_identifiers(isolated_tracking_dir):
    huge_org = "o" * 10000
    huge_exec = "e" * 10000
    fn = _tracking_filename(huge_org, huge_exec)
    # Must fit strictly within POSIX 255-byte limit
    assert len(fn) == 141
    entry = _make_in_flight(huge_org, huge_exec)
    _record_cross_worker_registration(entry)
    assert (isolated_tracking_dir / fn).exists()


# Scenario 10: Case and Unicode normalization (NFC equivalence)
def test_10_unicode_normalization_nfc():
    # 'é' as single code point U+00E9 vs 'e' + U+0301 (combining acute accent)
    nfc = "café"
    nfd = unicodedata.normalize("NFD", nfc)
    assert nfc != nfd
    # Exact database tenant identifiers must not alias through normalization.
    assert _tracking_filename(nfc, "exec") != _tracking_filename(nfd, "exec")


# Scenario 11: Concurrent registrations across tenants
@pytest.mark.asyncio
async def test_11_concurrent_registrations(isolated_tracking_dir):
    async def register(idx: int):
        org = f"tenant_{idx % 5}"
        exec_id = f"exec_{idx}"
        entry = _make_in_flight(org, exec_id)
        await asyncio.to_thread(_record_cross_worker_registration, entry)

    await asyncio.gather(*(register(i) for i in range(25)))
    files = list(isolated_tracking_dir.glob("trk_v2_*.json"))
    assert len(files) == 25


# Scenario 12: Existing valid registrations readable and exact
def test_12_existing_valid_registrations_readable(isolated_tracking_dir):
    entry = _make_in_flight("org-exact", "exec-exact")
    _record_cross_worker_registration(entry)

    res = _scan_remote("org-exact")
    assert len(res) == 1
    assert res[0]["organization_id"] == "org-exact"
    assert res[0]["execution_id"] == "exec-exact"
    assert res[0]["action_id"] == "act-exec-exact"


# Scenario 13: Legacy filename migration and coexistence
def test_13_legacy_filename_migration(isolated_tracking_dir):
    # Old legacy file
    legacy_file = isolated_tracking_dir / "legacyorg_legacyexec.json"
    legacy_data = {
        "execution_id": "legacyexec",
        "organization_id": "legacyorg",
        "action_id": "act-leg",
        "pid": 55555,
        "created_at": time.time(),
        "containment_status": "active",
    }
    legacy_file.write_text(json.dumps(legacy_data), encoding="utf-8")

    # New modern file
    modern_entry = _make_in_flight("legacyorg", "modernexec")
    _record_cross_worker_registration(modern_entry)

    res = _scan_remote("legacyorg")
    assert len(res) == 2
    exec_ids = {r["execution_id"] for r in res}
    assert exec_ids == {"legacyexec", "modernexec"}


# Scenario 14: Legacy tracking reads without data leakage
def test_14_legacy_tracking_reads_isolation(isolated_tracking_dir):
    legacy_file = isolated_tracking_dir / "orgA_exec1.json"
    legacy_file.write_text(
        json.dumps({"execution_id": "exec1", "organization_id": "orgA", "pid": 44444}),
        encoding="utf-8",
    )

    # orgB query must NOT see orgA legacy file
    assert len(_scan_remote("orgB")) == 0
    # orgA query sees it
    assert len(_scan_remote("orgA")) == 1


# Scenario 15: Malformed/conflicting legacy records quarantined, not deleted
def test_15_malformed_legacy_records_quarantined(isolated_tracking_dir):
    corrupt_file = isolated_tracking_dir / "unknown_corrupt.json"
    corrupt_file.write_text("{corrupt: json syntax error", encoding="utf-8")

    # Admin scan detects unresolved containment
    admin_scan = _check_remote_worker_active(None)
    assert len(admin_scan) == 1
    assert admin_scan[0]["containment_status"] == "unresolved"
    # Corrupt file is strictly preserved, NEVER deleted!
    assert corrupt_file.exists()


# Scenario 16: Cross-tenant denial in distributed scans
def test_16_cross_tenant_denial(isolated_tracking_dir):
    for i in range(10):
        entry = _make_in_flight(f"org-{i}", f"exec-{i}")
        _record_cross_worker_registration(entry)

    # Querying org-3 only sees org-3
    res = _scan_remote("org-3")
    assert len(res) == 1
    assert res[0]["organization_id"] == "org-3"


# Scenario 17: Process-death recovery preserves unconfirmed containment
def test_17_process_death_recovery(isolated_tracking_dir):
    # PID 99999999 does not exist
    entry = _make_in_flight("org-dead-worker", "exec-dead")
    _record_cross_worker_registration(entry)

    # Modify stored PID to a non-existent PID
    fn = _tracking_filename("org-dead-worker", "exec-dead")
    f_path = isolated_tracking_dir / fn
    data = json.loads(f_path.read_text())
    data["pid"] = 99999999
    f_path.write_text(json.dumps(data))

    res = _check_remote_worker_active("org-dead-worker")
    assert len(res) == 1
    # Process death cannot confirm container shutdown; retained with error flag
    assert "Worker exited; containment unconfirmed" in res[0].get("error", "")


# Scenario 18: Unresolved-container retention policy
def test_18_unresolved_container_retention(isolated_tracking_dir):
    entry = _make_in_flight("org-unres", "exec-unres")
    entry.containment_status = "unresolved"
    _record_cross_worker_registration(entry)

    res = _check_remote_worker_active("org-unres")
    assert len(res) == 1
    assert res[0]["containment_status"] == "unresolved"


# Scenario 19: Filesystem permission failures handled gracefully
def test_19_filesystem_permission_failures(isolated_tracking_dir, monkeypatch):
    def mock_scandir(_path):
        raise PermissionError("EACCES: tracking directory unreadable")

    monkeypatch.setattr(os, "scandir", mock_scandir)
    res = _check_remote_worker_active("org-perm")
    assert len(res) == 1
    assert res[0]["execution_id"] == "scan_failure"
    assert "EACCES" in res[0]["error"]


# Scenario 20: No unauthorized tracking deletion across tenants
def test_20_no_unauthorized_tracking_deletion(isolated_tracking_dir):
    entry_a = _make_in_flight("org_a", "task_1")
    entry_b = _make_in_flight("org_b", "task_1")
    _record_cross_worker_registration(entry_a)
    _record_cross_worker_registration(entry_b)

    # Tenant A attempts to delete its own task
    _remove_cross_worker_registration("org_a", "task_1")

    # Tenant B task file must remain intact
    fn_b = _tracking_filename("org_b", "task_1")
    assert (isolated_tracking_dir / fn_b).exists()
    assert not (isolated_tracking_dir / _tracking_filename("org_a", "task_1")).exists()
