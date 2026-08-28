#!/usr/bin/env python3
"""Manage WhitePact source-file copyright and SPDX headers.

OpenSSF Best Practices Gold requires each source file to identify its
copyright holder and license. This tool intentionally targets tracked,
first-party source under src/, tests/, scripts/, and examples/ and does
not rewrite generated/vendor/dependency content.
"""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

COPYRIGHT = "Copyright the WhitePact contributors."
SPDX = "SPDX-License-Identifier: MIT"
ROOTS = ("src/", "tests/", "scripts/", "examples/")
SUPPORTED = {".py", ".js", ".sh", ".css", ".html"}


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        check=True,
        capture_output=True,
        text=False,
    )
    paths = result.stdout.decode("utf-8").split("\0")
    return [
        Path(path)
        for path in paths
        if path
        and path.startswith(ROOTS)
        and Path(path).suffix.lower() in SUPPORTED
    ]


def header_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".py", ".sh"}:
        return f"# {COPYRIGHT}\n# {SPDX}\n"
    if suffix == ".js":
        return f"// {COPYRIGHT}\n// {SPDX}\n"
    if suffix == ".css":
        return f"/* {COPYRIGHT}\n * {SPDX}\n */\n"
    if suffix == ".html":
        return f"<!-- {COPYRIGHT} {SPDX} -->\n"
    raise ValueError(f"unsupported source type: {path}")


def has_required_header(text: str) -> bool:
    head = "\n".join(text.splitlines()[:20])
    return COPYRIGHT in head and SPDX in head


def insert_header(path: Path, text: str) -> str:
    header = header_for(path)
    suffix = path.suffix.lower()

    if suffix in {".py", ".sh"} and text.startswith("#!"):
        first, sep, rest = text.partition("\n")
        if not sep:
            return f"{first}\n{header}"
        return f"{first}\n{header}{rest}"

    if suffix == ".html" and text.lstrip().lower().startswith("<!doctype"):
        leading = len(text) - len(text.lstrip())
        prefix = text[:leading]
        body = text[leading:]
        first, sep, rest = body.partition("\n")
        if not sep:
            return f"{prefix}{first}\n{header}"
        return f"{prefix}{first}\n{header}{rest}"

    return header + text


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    args = parser.parse_args()

    missing: list[Path] = []
    changed = 0
    for path in tracked_files():
        text = path.read_text(encoding="utf-8")
        if has_required_header(text):
            continue
        missing.append(path)
        if args.write:
            path.write_text(insert_header(path, text), encoding="utf-8")
            changed += 1

    if args.write:
        print(f"Applied WhitePact copyright/SPDX headers to {changed} source files.")
        return 0

    if missing:
        print("Missing required WhitePact copyright/SPDX headers:")
        for path in missing:
            print(f"  {path}")
        return 1

    print("All tracked first-party source files contain WhitePact copyright/SPDX headers.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
