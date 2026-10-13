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


def test_mutable_third_party_tags_are_rejected_in_both_forms() -> None:
    mutations = (
        "uses: actions/checkout@v4",
        "- uses: actions/checkout@v4",
        "uses: actions/checkout@main",
        "- uses: actions/setup-python@master",
        "uses: azure/setup-helm@v4.2.0",
        "- uses: docker/setup-buildx-action@latest",
        "uses: actions/checkout@11d5960a326750d5838078e36cf38b85af67726",
        "- uses: actions/checkout",
        'uses: "actions/checkout@v4"',
    )
    for text in mutations:
        hits = _MODULE.unpinned_references(f"      {text}\n")
        assert hits, text
        assert "actions/" in hits[0] or "azure/" in hits[0] or "docker/" in hits[0]


def test_pinned_forms_survive_the_same_mutations() -> None:
    pinned = (
        f"uses: {PINNED}",
        f"- uses: {PINNED} # v4",
        "uses: ./.github/actions/local",
        "- uses: ./.github/actions/local",
    )
    for text in pinned:
        assert _MODULE.unpinned_references(f"      {text}\n") == []


def test_repository_workflows_are_pinned() -> None:
    root = Path(__file__).resolve().parents[1]
    failures: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        failures.extend(
            _MODULE.unpinned_references(path.read_text(encoding="utf-8"), label=str(path))
        )
    assert failures == []
