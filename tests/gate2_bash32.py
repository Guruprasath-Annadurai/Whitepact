# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Locate a real Bash 3.2 for Gate 2 qualification.

The restore script is portable. Qualification must not assume one Linux path.
"""

from __future__ import annotations

import os
import re
import subprocess
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

BASH32_VERSION = (3, 2)
DEFAULT_CANDIDATES: tuple[Path, ...] = (
    Path("/opt/bash32/bin/bash"),
    Path("/bin/bash"),
)
_VERSION_RE = re.compile(r"\bGNU bash, version (\d+)\.(\d+)")
VersionProbe = Callable[[Path], tuple[int, int] | None]


class Bash32RejectedError(Exception):
    """WHITEPACT_BASH32 was set and is not a usable Bash 3.2."""


class Bash32UnavailableError(Exception):
    """No discovered executable is Bash 3.2."""


def bash_version(executable: Path) -> tuple[int, int] | None:
    """Return (major, minor) when `executable --version` is GNU Bash."""
    if not executable.is_file() or not os.access(executable, os.X_OK):
        return None
    result = subprocess.run(
        [str(executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    match = _VERSION_RE.search(result.stdout or result.stderr)
    if match is None:
        return None
    return int(match.group(1)), int(match.group(2))


def discover_bash32(
    environ: Mapping[str, str] | None = None,
    *,
    candidates: Sequence[Path] = DEFAULT_CANDIDATES,
    probe: VersionProbe = bash_version,
) -> Path:
    """Find Bash 3.2. An explicit override that is not Bash 3.2 is rejected."""
    env = os.environ if environ is None else environ
    override = env.get("WHITEPACT_BASH32", "").strip()
    if override:
        path = Path(override)
        found = probe(path)
        if found != BASH32_VERSION:
            detail = "missing or not executable" if found is None else f"Bash {found[0]}.{found[1]}"
            raise Bash32RejectedError(f"WHITEPACT_BASH32={override} is not Bash 3.2 ({detail}).")
        return path
    for candidate in candidates:
        if probe(candidate) == BASH32_VERSION:
            return candidate
    raise Bash32UnavailableError(
        "No Bash 3.2 executable found. Set WHITEPACT_BASH32, or provide Bash 3.2 "
        "at /opt/bash32/bin/bash or /bin/bash."
    )
