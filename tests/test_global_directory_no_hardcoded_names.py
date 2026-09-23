# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from pathlib import Path

# Demo names allowed only in tests/fixtures — not in runtime resolver logic.
_FORBIDDEN_IN_RUNTIME = (
    "Guruprasath Annadurai",
    "Guruprasath-Annadurai",
    "Alex Smith",
    "Priya Sharma",
    "John Smith",
)

_RUNTIME_ROOT = Path(__file__).resolve().parents[1] / "src" / "responsibleai" / "global_directory"


def test_no_demo_person_names_in_runtime_modules() -> None:
    offenders: list[str] = []
    for path in _RUNTIME_ROOT.rglob("*.py"):
        if "fixtures" in path.parts:
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if line.strip().startswith("# Copyright"):
                continue
            for name in _FORBIDDEN_IN_RUNTIME:
                if name in line:
                    offenders.append(f"{path}:{line_no}: {name}")
    assert not offenders, "Hardcoded demo person names in runtime: " + "; ".join(offenders)
