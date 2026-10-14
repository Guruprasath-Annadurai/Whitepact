# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Source-bound release metadata; not registry publication qualification."""

import json
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_mcp_uvx_from_argument_pins_the_manifest_package_not_an_uncontrolled_latest():
    manifest = json.loads((ROOT / "server.json").read_text())
    package = manifest["packages"][0]
    argument = next(value for value in package["runtimeArguments"] if value["name"] == "--from")
    assert argument["value"] == f"{package['identifier']}=={package['version']}"


def test_source_version_is_consistent_without_claiming_sdk_registry_publication():
    platform = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
    typescript = json.loads((ROOT / "sdk/typescript/package.json").read_text())
    python_version = (ROOT / "sdk/python/rai_client/_version.py").read_text()
    assert typescript["version"] == platform["version"]
    assert f'"{platform["version"]}"' in python_version
    assert (
        "packagePublication: PackagePublication | null = null"
        in (ROOT / "web/src/content/package-release.ts").read_text()
    )


def test_stdio_description_does_not_claim_unrestricted_execution():
    manifest = json.loads((ROOT / "server.json").read_text())
    description = manifest["packages"][0]["packageArguments"][0]["description"]
    assert "advisory" in description
    assert "not an independent" in description
    assert "unrestricted" not in description
