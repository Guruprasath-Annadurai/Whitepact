# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression guard for the reviewed NLTK sentiment dependency boundary.

NLTK is optional and currently has upstream path-security advisories with no
patched release. WhitePact's accepted temporary exception is only defensible
while production source uses NLTK solely for VADER sentiment and a hard-coded
VADER lexicon download. Any expansion of the NLTK API surface must force a
security re-review rather than silently inheriting this exception.
"""

import ast
from pathlib import Path


_SRC = Path("src")
_SCORING = Path("src/biasbuster/core/scoring.py")
_EXPECTED_NLTK_IMPORTS = {
    (_SCORING.as_posix(), "import", "nltk", ""),
    (
        _SCORING.as_posix(),
        "from",
        "nltk.sentiment.vader",
        "SentimentIntensityAnalyzer",
    ),
}


def _nltk_imports() -> set[tuple[str, str, str, str]]:
    imports: set[tuple[str, str, str, str]] = set()
    for path in _SRC.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "nltk" or alias.name.startswith("nltk."):
                        imports.add((path.as_posix(), "import", alias.name, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "nltk" or node.module.startswith("nltk."):
                    for alias in node.names:
                        imports.add((path.as_posix(), "from", node.module, alias.name))
    return imports


def test_nltk_imports_stay_inside_reviewed_vader_boundary() -> None:
    """A new NLTK import must trigger review of the vulnerability exception."""
    actual = _nltk_imports()

    # Normalize the plain ``import nltk`` tuple to the same explicit form as
    # the expected allow-list. Keeping this comparison exact means a new NLTK
    # module/class cannot be introduced without changing this security test.
    normalized = {
        (path, kind, module, "" if kind == "import" and module == "nltk" else symbol)
        for path, kind, module, symbol in actual
    }
    assert normalized == _EXPECTED_NLTK_IMPORTS


def test_nltk_download_uses_only_literal_vader_lexicon() -> None:
    """The generic nltk module may only download the fixed VADER resource."""
    tree = ast.parse(_SCORING.read_text(encoding="utf-8"), filename=str(_SCORING))
    calls: list[ast.Call] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "nltk":
            calls.append(node)

    assert len(calls) == 1
    call = calls[0]
    assert call.func.attr == "download"
    assert len(call.args) == 1
    assert isinstance(call.args[0], ast.Constant)
    assert call.args[0].value == "vader_lexicon"

    quiet = next((kw for kw in call.keywords if kw.arg == "quiet"), None)
    assert quiet is not None
    assert isinstance(quiet.value, ast.Constant)
    assert quiet.value.value is True
