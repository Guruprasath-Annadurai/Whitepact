# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Runtime SDK identity must agree with its distribution metadata."""

import ast
import tomllib
from pathlib import Path

from sdk.python import rai_client


def test_python_sdk_runtime_version_matches_package_metadata():
    package = tomllib.loads(Path("sdk/python/pyproject.toml").read_text())
    assert "version" in package["project"]["dynamic"]
    source = ast.parse(
        (Path("sdk/python") / package["tool"]["hatch"]["version"]["path"]).read_text()
    )
    version = next(node.value.value for node in source.body if isinstance(node, ast.Assign))
    assert rai_client.__version__ == version == "1.3.1"
