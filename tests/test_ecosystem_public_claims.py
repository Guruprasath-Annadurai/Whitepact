# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Guards for ecosystem submission copy and listing metadata.

These checks lock facts this lane verified. They do not fetch the network,
and they do not treat older evidence files elsewhere in the repository as
current submission copy.
"""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "docs" / "ecosystem" / "inventory.json"
MATRIX = ROOT / "docs" / "ecosystem" / "PLATFORM_ELIGIBILITY_MATRIX.md"
COPY = ROOT / "docs" / "ecosystem" / "copy" / "DESCRIPTIONS.md"
SERVER_JSON = ROOT / "server.json"
PYPROJECT = ROOT / "pyproject.toml"

STATUSES = {"GREEN", "YELLOW", "RED", "BLUE", "GREY"}
FORBIDDEN = (
    "SOC 2",
    "SOC2",
    "Fortune 500",
    "Guaranteed secure",
    "100% runtime",
    "Production SaaS available worldwide",
    "Globally production-certified",
    "pip install whitepact",
    "rai-governance-platform==1.3.1",
)


def _inventory() -> dict:
    return json.loads(INVENTORY.read_text())


def _section(heading: str) -> str:
    text = COPY.read_text()
    parts = re.split(r"\n## ", text)
    for part in parts[1:]:
        title, _, body = part.partition("\n")
        if title.strip() == heading:
            return body
    raise AssertionError(f"missing copy section: {heading}")


def _words(body: str) -> int:
    body = re.sub(r"```[\s\S]*?```", " ", body)
    return len(re.findall(r"[A-Za-z0-9][A-Za-z0-9'+./:=_-]*", body))


def test_inventory_ids_are_unique_and_cover_the_matrix() -> None:
    data = _inventory()
    platforms = data["platforms"]
    ids = [item["id"] for item in platforms]
    assert len(ids) == len(set(ids))
    assert len(platforms) == 45
    matrix = MATRIX.read_text()
    for item in platforms:
        assert item["status"] in STATUSES
        assert item["official_url"].startswith("https://")
        assert f"`{item['id']}`" in matrix
        assert item["status"] in matrix
    assert data["published_pypi_version"] == "1.2.6"
    assert data["source_version"] == "1.3.1"
    counts = data["classification_counts"]
    assert counts == {
        "external_directory_submission_ready": 2,
        "first_party_community_posting_ready": 1,
        "already_live": 7,
        "conditional": 5,
        "blocked": 10,
        "unverified": 20,
    }
    by_id = {item["id"]: item for item in platforms}
    assert by_id["future-tools"]["status"] == "GREEN"
    assert by_id["future-tools"]["channel"] == "external_directory"
    assert by_id["ignlab-launch"]["status"] == "GREEN"
    assert by_id["ignlab-launch"]["channel"] == "external_directory"
    assert by_id["github-discussions"]["status"] == "GREEN"
    assert by_id["github-discussions"]["channel"] == "first_party_community"
    assert "not an external directory" in matrix


def test_submission_copy_has_usable_lengths_and_no_forbidden_claims() -> None:
    assert _words(_section("50-word description")) == 50
    assert 95 <= _words(_section("100-word description")) <= 115
    assert 190 <= _words(_section("200-word description")) <= 230
    copy = COPY.read_text()
    for phrase in FORBIDDEN:
        assert phrase not in copy
    assert "1.2.6" in copy
    assert "1.3.1" in copy
    assert "bearer credential" in copy
    assert "does not support anonymous access" in copy
    assert "operational qualification" in copy
    assert "older ResponsibleAI governance dashboard" in copy
    assert "was not the page that host returned" in copy


def test_source_classifier_is_beta_and_does_not_rewrite_pypi() -> None:
    pyproject = tomllib.loads(PYPROJECT.read_text())
    classifiers = pyproject["project"]["classifiers"]
    assert "Development Status :: 4 - Beta" in classifiers
    assert "Development Status :: 5 - Production/Stable" not in classifiers
    ledger = (ROOT / "docs" / "ecosystem" / "PUBLIC_CLAIMS_LEDGER.md").read_text()
    assert "Development Status :: 5 - Production/Stable" in ledger
    assert "1.2.6" in ledger


def test_server_json_pins_the_published_package_not_source() -> None:
    server = json.loads(SERVER_JSON.read_text())
    pyproject = tomllib.loads(PYPROJECT.read_text())
    package = server["packages"][0]
    assert package["identifier"] == "rai-governance-platform"
    assert package["identifier"] == pyproject["project"]["name"]
    assert package["version"] == "1.2.6"
    assert server["version"] == "1.2.6"
    assert pyproject["project"]["version"] == "1.3.1"
    joined = json.dumps(server)
    assert "free org" not in joined
    assert "example.com" not in joined


def test_duplicate_listing_urls_are_rejected() -> None:
    urls = [item["official_url"] for item in _inventory()["platforms"]]
    assert len(urls) == len(set(urls))
