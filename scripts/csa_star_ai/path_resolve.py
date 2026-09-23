# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Resolve repository-relative paths cited in CAIQ evidence descriptions."""

from __future__ import annotations

import re
from pathlib import Path

_REPO = Path(__file__).resolve().parents[2]

_PATH_TOKEN = re.compile(
    r"(?:"
    r"[\w./-]+\.(?:py|yml|yaml|md|sh|sql|toml)"
    r"|\.github/workflows/[\w./-]+\.yml"
    r")"
)

_WORKFLOW_ALIASES = {
    "security-scan.yml": ".github/workflows/security-scan.yml",
    "dependency-review.yml": ".github/workflows/dependency-review.yml",
    "ci.yml": ".github/workflows/ci.yml",
}


def extract_path_tokens(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for raw in _PATH_TOKEN.findall(text):
        token = raw.strip(".,;:")
        if token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def resolve_repo_path(token: str) -> Path | None:
    if token in _WORKFLOW_ALIASES:
        token = _WORKFLOW_ALIASES[token]
    candidates = [
        _REPO / token,
        _REPO / "tests" / token,
        _REPO / "src" / "responsibleai" / token,
        _REPO / ".github" / "workflows" / token,
    ]
    if token.startswith(".github/"):
        candidates.insert(0, _REPO / token)
    if token.startswith("tests/"):
        candidates.insert(0, _REPO / token)
    if token.startswith("src/"):
        candidates.insert(0, _REPO / token)
    for path in candidates:
        if path.is_file():
            return path
    return None


def classify_paths(tokens: list[str]) -> tuple[list[str], bool, bool, bool, bool]:
    """Return (resolved_refs, has_src, has_tests, has_workflow, has_compliance_doc_only)."""
    refs: list[str] = []
    has_src = has_tests = has_workflow = False
    compliance_only = True
    for token in tokens:
        resolved = resolve_repo_path(token)
        if not resolved:
            continue
        rel = resolved.relative_to(_REPO).as_posix()
        refs.append(rel)
        if rel.startswith("src/"):
            has_src = True
            compliance_only = False
        if rel.startswith("tests/"):
            has_tests = True
            compliance_only = False
        if rel.startswith(".github/workflows/"):
            has_workflow = True
            compliance_only = False
        if not rel.startswith("compliance/"):
            compliance_only = False
    if not refs:
        compliance_only = False
    return refs, has_src, has_tests, has_workflow, compliance_only and bool(refs)
