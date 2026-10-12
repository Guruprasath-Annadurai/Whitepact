# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SDK distributions must be buildable outside the repository root."""

import tomllib
from pathlib import Path


def test_python_sdk_license_is_self_contained_and_matches_repository():
    project = Path("sdk/python")
    metadata = tomllib.loads((project / "pyproject.toml").read_text())
    license_path = project / metadata["project"]["license"]["file"]
    assert license_path.resolve().is_relative_to(project.resolve())
    assert license_path.read_bytes() == Path("LICENSE").read_bytes()
