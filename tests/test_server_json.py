# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Drift guard for server.json (MCP registry manifest, Phase 17): its
version and tool/resource counts must stay in sync with the real
source of truth (pyproject.toml, TOOL_DEFS, RESOURCE_DEFS) the same
way governance/risk.py's tier table is checked against TOOL_DEFS.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent


def _load_server_json() -> dict:
    return json.loads((_REPO_ROOT / "server.json").read_text())


def _version_tuple(v: str) -> tuple[int, ...]:
    return tuple(int(part) for part in v.split("."))


class TestServerJsonShape:
    def test_is_valid_json(self) -> None:
        _load_server_json()  # raises if malformed

    def test_has_required_top_level_fields(self) -> None:
        d = _load_server_json()
        for field in ("name", "description", "version", "repository", "packages"):
            assert field in d, f"server.json missing required field: {field}"

    def test_description_within_registry_length_limit(self) -> None:
        # The official registry's schema caps this at 100 chars --
        # verified against the live schema when this file was written.
        assert len(_load_server_json()["description"]) <= 100

    def test_no_remotes_without_a_real_url(self) -> None:
        """See MCP_DISTRIBUTION_GUIDE.md: `remotes` is deliberately
        omitted until a real, publicly reachable hosted MCP URL exists.
        This guards against someone adding a placeholder/example.com URL
        later without updating that reasoning."""
        d = _load_server_json()
        if "remotes" in d:
            for remote in d["remotes"]:
                assert "example.com" not in remote.get("url", "")


class TestServerJsonVersionSync:
    """server.json carries two version numbers on purpose, and they're
    allowed to diverge in one direction only:

    - `packages[0].version` names the PyPI release the `stdio` transport
      actually installs. It must never be ahead of pyproject.toml's
      version -- that would point installers at a release that was
      never built from the code currently checked in.
    - top-level `version` is the *registry listing* version. The
      registry rejects republishing under an unchanged version, so this
      gets bumped for listing-only metadata changes (e.g. adding
      `remotes`) without cutting a full PyPI release -- see
      FOUNDER_ACTION_CHECKLIST.md's MCP distribution section. It can
      therefore run ahead of both pyproject.toml and the published
      package, but never fall behind the package version it describes.
    """

    def test_package_version_does_not_outrun_pyproject(self) -> None:
        pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
        d = _load_server_json()
        pkg_version = _version_tuple(d["packages"][0]["version"])
        pyproject_version = _version_tuple(pyproject["project"]["version"])
        assert pkg_version <= pyproject_version, (
            f"server.json packages[0].version ({d['packages'][0]['version']}) is "
            f"ahead of pyproject.toml ({pyproject['project']['version']}) -- that "
            "release was never built from this source."
        )

    def test_listing_version_is_at_least_the_package_version(self) -> None:
        d = _load_server_json()
        listing_version = _version_tuple(d["version"])
        pkg_version = _version_tuple(d["packages"][0]["version"])
        assert listing_version >= pkg_version, (
            f"server.json top-level version ({d['version']}) is behind its own "
            f"packages[0].version ({d['packages'][0]['version']})."
        )

    def test_pypi_package_identifier_matches_pyproject_name(self) -> None:
        pyproject = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text())
        d = _load_server_json()
        pypi_package = next(p for p in d["packages"] if p["registryType"] == "pypi")
        assert pypi_package["identifier"] == pyproject["project"]["name"]


class TestServerJsonToolCounts:
    def test_tool_count_matches_live_tool_defs(self) -> None:
        from responsibleai.mcp.tools import TOOL_DEFS

        d = _load_server_json()
        meta = d["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]
        assert meta["tool_count"] == len(TOOL_DEFS)

    def test_resource_counts_match_live_resource_defs(self) -> None:
        from responsibleai.mcp.resources import _CANONICAL_RESOURCE_DEFS, RESOURCE_DEFS

        d = _load_server_json()
        meta = d["_meta"]["io.modelcontextprotocol.registry/publisher-provided"]
        assert meta["resource_count_canonical"] == len(_CANONICAL_RESOURCE_DEFS)
        assert meta["resource_count_advertised"] == len(RESOURCE_DEFS)
