"""Runtime SDK identity must agree with its distribution metadata."""

import tomllib
from pathlib import Path

from sdk.python import rai_client


def test_python_sdk_runtime_version_matches_package_metadata():
    package = tomllib.loads(Path("sdk/python/pyproject.toml").read_text())
    assert rai_client.__version__ == package["project"]["version"]
