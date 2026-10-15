# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Bash 3.2 discovery for Gate 2 qualification. These tests do not change restore."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from tests.gate2_bash32 import (
    Bash32RejectedError,
    Bash32UnavailableError,
    bash_version,
    discover_bash32,
)

ROOT = Path(__file__).resolve().parents[1]
RESTORE = ROOT / "scripts" / "restore-postgres.sh"


def _probe(versions: dict[Path, tuple[int, int] | None]):
    def probe(path: Path) -> tuple[int, int] | None:
        return versions.get(path)

    return probe


def test_whitepact_bash32_override_is_used(tmp_path: Path) -> None:
    chosen = tmp_path / "bash"
    found = discover_bash32(
        {"WHITEPACT_BASH32": str(chosen)},
        probe=_probe({chosen: (3, 2)}),
    )
    assert found == chosen


def test_invalid_override_path_is_rejected(tmp_path: Path) -> None:
    missing = tmp_path / "missing-bash"
    with pytest.raises(Bash32RejectedError, match="WHITEPACT_BASH32=.*is not Bash 3.2"):
        discover_bash32({"WHITEPACT_BASH32": str(missing)}, probe=_probe({}))


def test_override_pointing_at_bash5_does_not_qualify(tmp_path: Path) -> None:
    bash5 = tmp_path / "bash"
    with pytest.raises(Bash32RejectedError, match=r"Bash 5\.2"):
        discover_bash32(
            {"WHITEPACT_BASH32": str(bash5)},
            probe=_probe({bash5: (5, 2)}),
        )


def test_opt_bash32_remains_supported() -> None:
    opt = Path("/opt/bash32/bin/bash")
    system = Path("/bin/bash")
    found = discover_bash32(
        {},
        candidates=(opt, system),
        probe=_probe({opt: (3, 2), system: (5, 2)}),
    )
    assert found == opt


def test_macos_bin_bash_32_is_accepted_when_opt_path_is_absent() -> None:
    opt = Path("/opt/bash32/bin/bash")
    macos = Path("/bin/bash")
    found = discover_bash32(
        {},
        candidates=(opt, macos),
        probe=_probe({opt: None, macos: (3, 2)}),
    )
    assert found == macos


def test_no_bash32_is_unavailable_and_does_not_pass() -> None:
    opt = Path("/opt/bash32/bin/bash")
    system = Path("/bin/bash")
    with pytest.raises(Bash32UnavailableError, match="No Bash 3.2 executable found"):
        discover_bash32(
            {},
            candidates=(opt, system),
            probe=_probe({opt: None, system: (5, 2)}),
        )


def test_filename_bash_without_gnu_banner_is_not_version_32(tmp_path: Path) -> None:
    fake = tmp_path / "bash"
    fake.write_text("#!/bin/sh\necho 3.2\n", encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    assert bash_version(fake) is None
    with pytest.raises(Bash32RejectedError, match="missing or not executable"):
        discover_bash32({"WHITEPACT_BASH32": str(fake)})


def test_gnu_bash_banner_reports_major_minor(tmp_path: Path) -> None:
    fake = tmp_path / "bash"
    fake.write_text(
        "#!/bin/sh\necho 'GNU bash, version 3.2.57(1)-release (x86_64-apple-darwin)'\n",
        encoding="utf-8",
    )
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    assert bash_version(fake) == (3, 2)


def test_real_bash32_parses_and_runs_restore_script(tmp_path: Path) -> None:
    try:
        bash32 = discover_bash32()
    except Bash32UnavailableError as exc:
        pytest.skip(str(exc))
    assert bash_version(bash32) == (3, 2)
    text = RESTORE.read_text(encoding="utf-8")
    assert "mapfile" not in text
    assert "readarray" not in text
    syntax = subprocess.run(
        [str(bash32), "-n", str(RESTORE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    missing = tmp_path / "missing.sql.gz.enc"
    ran = subprocess.run(
        [str(bash32), str(RESTORE), str(missing)],
        check=False,
        capture_output=True,
        text=True,
        env={**os.environ, "WHITEPACT_RESTORE_LOCAL": "1"},
    )
    assert ran.returncode == 2
    assert "backup file not found" in ran.stderr


def test_bash5_still_parses_restore_script() -> None:
    system = Path("/usr/bin/bash")
    version = bash_version(system)
    if version is None or version[0] < 5:
        pytest.skip("This host has no Bash 5 at /usr/bin/bash")
    syntax = subprocess.run(
        [str(system), "-n", str(RESTORE)],
        check=False,
        capture_output=True,
        text=True,
    )
    assert syntax.returncode == 0, syntax.stderr
    assert version[0] >= 5
