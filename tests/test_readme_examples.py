# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Published README code must run exactly as written and print what it says it prints.

A first-time developer copies the first example. Importing the right names is not
enough: the original quickstart imported valid names and then crashed on a wrong
constructor call, and four more README examples called APIs that do not exist. So every
Python block is classified here and the offline-runnable ones are executed verbatim in a
fresh interpreter. A block that is added to the README without being classified fails.

Blocks that need credentials or user code cannot run offline; they are recorded as
skipped with a reason. A skip is not a pass.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
QUICKSTART = ROOT / "examples" / "00_quickstart.py"


@dataclass(frozen=True)
class Example:
    marker: str  # a string that uniquely identifies the block
    expected: tuple[str, ...]  # substrings that must appear in stdout
    produces_files: tuple[str, ...] = ()


RUNNABLE = (
    Example(
        "WhitePactRuntimeGateway",
        (
            "ALLOW                            -> ALLOW",
            "DENY (no delegated authority)    -> DENY",
            "REQUIRE_APPROVAL                 -> REQUIRE_APPROVAL",
            "ALLOW_WITH_REDACTION             -> ALLOW_WITH_REDACTION",
            "QUARANTINE (repeated denials)    -> QUARANTINE",
            "evidence chain intact: True",
        ),
    ),
    Example(
        "PassportGenerator",
        ("83.7 / 100  Grade: B  Risk: LOW",),
        produces_files=("passport.html",),
    ),
    Example(
        "GuardrailsEngine",
        ("True", "2", "Customer SSN is [REDACTED], email: [REDACTED]"),
    ),
    Example("HallucinationDetector", ("Risk:", "Level:")),
    Example("ComplianceEngine", ("Score: 100.0%", "EU AI Act tier: HIGH")),
    Example(
        "RedTeamSimulator",
        ("Security score: 100.0/100", "Vulnerabilities: 0"),
    ),
    Example("TrustDriftMonitor", ("Drift alert! high: 11.0 pt drop",)),
)

SKIPPED = {
    "CostTracker": "writes a database under the user's home directory",
    "BiasBusterRunner": "needs a live OpenAI API key",
    "FederatedClient": "needs the reader's own provider class (MyProvider)",
}


def _python_blocks() -> list[tuple[int, str]]:
    text = README.read_text()
    return [
        (text[: m.start()].count("\n") + 2, m.group(1))
        for m in re.finditer(r"```python\n(.*?)```", text, re.S)
    ]


def _find(marker: str) -> tuple[int, str]:
    matches = [(line, code) for line, code in _python_blocks() if marker in code]
    assert len(matches) == 1, f"marker {marker!r} must identify exactly one README block"
    return matches[0]


def _run(code: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    script = cwd / "readme_example.py"
    script.write_text(code)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(ROOT / "src"), env.get("PYTHONPATH")]))
    env["PYTHONWARNINGS"] = "ignore"
    return subprocess.run(  # noqa: S603
        [sys.executable, str(script)],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


def test_every_readme_python_block_is_classified() -> None:
    """A new example cannot be published without either running or being justified."""
    unclassified = []
    for line, code in _python_blocks():
        known = [e.marker for e in RUNNABLE if e.marker in code] + [m for m in SKIPPED if m in code]
        if len(known) != 1:
            unclassified.append((line, known))
    assert not unclassified, f"README python blocks not classified exactly once: {unclassified}"


@pytest.mark.parametrize("example", RUNNABLE, ids=lambda e: e.marker)
def test_readme_example_runs_verbatim(example: Example, tmp_path: Path) -> None:
    line, code = _find(example.marker)
    result = _run(code, tmp_path)
    assert result.returncode == 0, f"README:{line} crashed:\n{result.stderr[-1500:]}"
    for expected in example.expected:
        assert expected in result.stdout, (
            f"README:{line} no longer prints {expected!r}.\nstdout:\n{result.stdout}"
        )
    for name in example.produces_files:
        produced = tmp_path / name
        assert produced.is_file() and produced.stat().st_size > 0, f"{name} was not written"


def test_quickstart_is_deterministic(tmp_path: Path) -> None:
    _, code = _find("WhitePactRuntimeGateway")
    first_dir, second_dir = tmp_path / "a", tmp_path / "b"
    first_dir.mkdir()
    second_dir.mkdir()
    first, second = _run(code, first_dir), _run(code, second_dir)
    assert first.returncode == 0 and second.returncode == 0, first.stderr[-800:]
    assert first.stdout == second.stdout


def test_readme_quickstart_matches_the_shipped_example_file() -> None:
    """examples/00_quickstart.py and the README must not drift apart."""
    _, code = _find("WhitePactRuntimeGateway")
    assert code.strip() in QUICKSTART.read_text()


@pytest.mark.parametrize("marker,reason", sorted(SKIPPED.items()))
def test_readme_example_not_executable_offline(marker: str, reason: str) -> None:
    _find(marker)  # still must exist exactly once
    pytest.skip(f"DOC_EXAMPLE_NOT_EXECUTED {marker}: {reason}. A skip is not a pass.")
