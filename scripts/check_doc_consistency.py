"""Documentation-currency checker (OpenSSF Silver, documentation_current).

Validates a small set of high-value invariants that are cheap to check and
expensive to leave stale: the package version quoted in README.md's ASCII
banner must match pyproject.toml/src/responsibleai/__init__.py, and the
canonical project name/domain/repo identity must appear consistently.
Deliberately narrow -- it does not try to parse every number in every doc
(that's what made README's stale "1725 tests" and CONTRIBUTING.md's stale
"1,538 tests" possible in the first place; this script checks facts that
have one unambiguous source of truth instead).

Usage: python scripts/check_doc_consistency.py
Exits non-zero with a list of every mismatch found.
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CANONICAL_DOMAIN = "whitepact.com"
CANONICAL_REPO = "Guruprasath-Annadurai/Whitepact"
CANONICAL_NAME = "WhitePact"


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _pyproject_version() -> str:
    data = tomllib.loads(_read("pyproject.toml"))
    return data["project"]["version"]


def _init_version() -> str:
    text = _read("src/responsibleai/__init__.py")
    m = re.search(r'__version__\s*=\s*"([^"]+)"', text)
    if not m:
        raise RuntimeError("Could not find __version__ in src/responsibleai/__init__.py")
    return m.group(1)


def _readme_banner_version() -> str | None:
    text = _read("README.md")
    m = re.search(r"WhitePact\s+v(\d+\.\d+\.\d+(?:rc\d+)?)", text)
    return m.group(1) if m else None


def main() -> int:
    problems: list[str] = []

    pyproject_version = _pyproject_version()
    init_version = _init_version()
    readme_version = _readme_banner_version()

    if init_version != pyproject_version:
        problems.append(
            f"src/responsibleai/__init__.py __version__ ({init_version!r}) does not "
            f"match pyproject.toml version ({pyproject_version!r})."
        )

    if readme_version is None:
        problems.append(
            "README.md's ASCII banner no longer contains a 'WhitePact vX.Y.Z' line "
            "-- update this check if the banner format changed intentionally."
        )
    elif readme_version != pyproject_version:
        problems.append(
            f"README.md banner shows v{readme_version}, but pyproject.toml's "
            f"version is {pyproject_version!r}. Update README.md's ASCII banner."
        )

    readme_text = _read("README.md")
    if CANONICAL_DOMAIN not in readme_text:
        problems.append(f"README.md does not mention the canonical domain {CANONICAL_DOMAIN}.")
    if CANONICAL_REPO not in readme_text:
        problems.append(f"README.md does not mention the canonical repo {CANONICAL_REPO}.")

    if problems:
        print("Documentation consistency check FAILED:\n")
        for p in problems:
            print(f"  - {p}")
        print(
            "\nThese are real, checkable facts with one source of truth "
            "(pyproject.toml's version, the canonical domain/repo) -- fix the "
            "stale doc rather than this script, unless the source of truth "
            "itself changed."
        )
        return 1

    print(f"Documentation consistency OK (version {pyproject_version}, domain {CANONICAL_DOMAIN}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
