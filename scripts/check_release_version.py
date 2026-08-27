#!/usr/bin/env python3
"""Fail a release when its Git tag and package metadata disagree."""

from __future__ import annotations

import sys
import tomllib
from pathlib import Path


def release_version(pyproject: Path = Path("pyproject.toml")) -> str:
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    version = data.get("project", {}).get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError("pyproject.toml is missing project.version")
    return version.strip()


def validate_release_tag(tag: str, version: str) -> None:
    if not tag.startswith("v") or len(tag) == 1:
        raise ValueError(f"release tag must be v<version>; received {tag!r}")
    expected = f"v{version}"
    if tag != expected:
        raise ValueError(f"release tag {tag!r} does not match package version {version!r}")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        print("usage: check_release_version.py v<version>", file=sys.stderr)
        return 2
    try:
        version = release_version()
        validate_release_tag(args[0], version)
    except (OSError, KeyError, ValueError, tomllib.TOMLDecodeError) as exc:
        print(f"release version check failed: {exc}", file=sys.stderr)
        return 1
    print(f"release tag {args[0]} matches project version {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
