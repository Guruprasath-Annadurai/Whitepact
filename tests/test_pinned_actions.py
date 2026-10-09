# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The pin checker must see YAML list-form `uses` entries."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "check_pinned_actions",
    Path(__file__).resolve().parents[1] / "scripts" / "check_pinned_actions.py",
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

PINNED = "actions/checkout@11d5960a326750d5838078e36cf38b85af677262"


def test_dash_uses_movable_tag_is_rejected() -> None:
    text = "      - uses: actions/checkout@v4\n"
    hits = _MODULE.unpinned_references(text)
    assert len(hits) == 1
    assert "actions/checkout@v4" in hits[0]


def test_dash_uses_full_sha_is_accepted() -> None:
    text = f"      - uses: {PINNED} # v4\n"
    assert _MODULE.unpinned_references(text) == []


def test_indented_uses_still_checked() -> None:
    text = "        uses: actions/checkout@v4\n"
    assert _MODULE.unpinned_references(text)


def test_local_action_is_ignored() -> None:
    text = "      - uses: ./.github/actions/local\n"
    assert _MODULE.unpinned_references(text) == []


def test_repository_workflows_are_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        failures.extend(
            _MODULE.unpinned_references(path.read_text(encoding="utf-8"), label=str(path))
        )
    assert failures == []
