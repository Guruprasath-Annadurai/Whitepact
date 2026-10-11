#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Reject two distributions that both ship the WhitePact import tree.

A later rename may publish the code under one new name. The legacy project
must then be a dependency shim with no import packages of its own. This
script does not upload anything.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import sys
import zipfile
from pathlib import Path

CODE_PACKAGES = frozenset({"responsibleai", "whitepact", "biasbuster", "privacylabel"})


class DualOwnershipError(RuntimeError):
    """Two wheels both contain the same import package."""


def distribution_name(wheel: Path) -> str:
    stem = wheel.name
    if stem.endswith(".whl"):
        stem = stem[: -len(".whl")]
    # {distribution}-{version}-{python}-{abi}-{platform}
    parts = stem.split("-")
    if len(parts) < 2:
        return stem
    return parts[0]


def code_packages_in_wheel(wheel: Path) -> set[str]:
    found: set[str] = set()
    with zipfile.ZipFile(wheel) as archive:
        for name in archive.namelist():
            if name.endswith("/") or ".dist-info/" in name or ".data/" in name:
                continue
            top = name.split("/", 1)[0]
            if top in CODE_PACKAGES:
                found.add(top)
    return found


def dual_code_conflicts(wheels: list[Path]) -> dict[str, list[str]]:
    owners: dict[str, list[str]] = {}
    for wheel in wheels:
        dist = distribution_name(wheel)
        for package in code_packages_in_wheel(wheel):
            owners.setdefault(package, []).append(dist)
    return {package: dists for package, dists in owners.items() if len(dists) > 1}


def assert_exclusive_code_ownership(wheels: list[Path]) -> None:
    conflicts = dual_code_conflicts(wheels)
    if conflicts:
        detail = ", ".join(
            f"{package}: {' + '.join(dists)}" for package, dists in sorted(conflicts.items())
        )
        raise DualOwnershipError(f"dual code ownership rejected: {detail}")


def _record_hash(payload: bytes) -> str:
    digest = hashlib.sha256(payload).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def write_wheel(
    path: Path,
    *,
    distribution: str,
    version: str,
    files: dict[str, bytes],
    requires: list[str] | None = None,
) -> None:
    """Write a pure-Python wheel. ``files`` keys are archive paths."""
    dist_info = f"{distribution.replace('-', '_')}-{version}.dist-info"
    metadata_lines = [
        "Metadata-Version: 2.1",
        f"Name: {distribution}",
        f"Version: {version}",
    ]
    for requirement in requires or []:
        metadata_lines.append(f"Requires-Dist: {requirement}")
    metadata = ("\n".join(metadata_lines) + "\n").encode("utf-8")
    wheel_meta = (
        "Wheel-Version: 1.0\n"
        "Generator: whitepact-dual-ownership\n"
        "Root-Is-Purelib: true\n"
        "Tag: py3-none-any\n"
    ).encode("utf-8")
    payload = {
        f"{dist_info}/METADATA": metadata,
        f"{dist_info}/WHEEL": wheel_meta,
        **files,
    }
    record_lines: list[str] = []
    for name, body in sorted(payload.items()):
        record_lines.append(f"{name},{_record_hash(body)},{len(body)}")
    record_name = f"{dist_info}/RECORD"
    record_lines.append(f"{record_name},,")
    payload[record_name] = ("\n".join(record_lines) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w") as archive:
        for name, body in sorted(payload.items()):
            archive.writestr(name, body)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("wheels", nargs="+", type=Path)
    args = parser.parse_args(argv)
    try:
        assert_exclusive_code_ownership(args.wheels)
    except DualOwnershipError as exc:
        print(f"DUAL_CODE_OWNERSHIP=REJECTED {exc}")
        return 2
    print("DUAL_CODE_OWNERSHIP=EXCLUSIVE")
    return 0


if __name__ == "__main__":
    sys.exit(main())
