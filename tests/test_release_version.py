from __future__ import annotations

from pathlib import Path

import pytest
from scripts.check_release_version import release_version, validate_release_tag


def test_release_version_reads_project_metadata(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "example"\nversion = "2.4.0rc1"\n')
    assert release_version(pyproject) == "2.4.0rc1"


def test_release_tag_must_exactly_match_project_version() -> None:
    validate_release_tag("v2.4.0rc1", "2.4.0rc1")
    with pytest.raises(ValueError, match="does not match"):
        validate_release_tag("v2.4.0", "2.4.0rc1")


@pytest.mark.parametrize("tag", ["2.4.0", "release-2.4.0", "v", ""])
def test_release_tag_requires_v_prefix_and_version(tag: str) -> None:
    with pytest.raises(ValueError, match="must be v"):
        validate_release_tag(tag, "2.4.0")
