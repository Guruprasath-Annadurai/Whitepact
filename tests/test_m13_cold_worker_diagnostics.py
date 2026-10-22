# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Crash-test diagnostics must be actionable without disclosing runtime secrets."""

import pytest
from scripts.engineering.m13_absolute_cold_worker import record_failure

from tests.test_m13_absolute_cold_restart_native import safe_worker_failure


def test_worker_diagnostic_retains_only_exception_class(tmp_path, monkeypatch):
    path = tmp_path / "diagnostic"
    monkeypatch.setenv("WP_ABSOLUTE_FAILURE_FILE", str(path))
    record_failure(PermissionError("postgresql://private:secret@host/private"))
    assert path.read_text() == "PermissionError"
    assert path.stat().st_mode & 0o777 == 0o600
    assert safe_worker_failure(path).endswith(": PermissionError")
    record_failure(RuntimeError("must not overwrite evidence"))
    assert path.read_text() == "PermissionError"


@pytest.mark.parametrize("contents", ["secret://private:value", "é", "a" * 81])
def test_arbitrary_worker_diagnostic_text_is_not_reprinted(tmp_path, contents):
    path = tmp_path / "diagnostic"
    path.write_text(contents)
    assert safe_worker_failure(path).endswith(": InvalidDiagnostic")
