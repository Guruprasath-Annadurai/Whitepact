# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The DCO workflow exempts two historical SHAs and nothing else.

The shell in ``.github/workflows/dco.yml`` is executed, not reimplemented.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DCO_PATH = ROOT / ".github" / "workflows" / "dco.yml"
RECORD = ROOT / "compliance" / "DCO_HISTORICAL_EXCEPTION_2026-10-09.md"

HISTORICAL = (
    "015fab741427a5a9cae5bca7adaa9729c78da9e5",
    "681ce9566f0ef9b68b6fc97212cc2fb7a44135e3",
)
HISTORICAL_PARENT = "5d317d5a03cf335ec8ca09536c2911b5762daa7c"
SIGN_OFF_RE = r"^Signed-off-by: .+ <.+@.+>$"


def _workflow() -> dict:
    return yaml.load(DCO_PATH.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _check_script() -> str:
    steps = _workflow()["jobs"]["dco-check"]["steps"]
    step = next(item for item in steps if item["name"] == "Check every commit is signed off")
    script = step["run"]
    assert isinstance(script, str)
    return script


def _exception_arms(script: str) -> set[str]:
    match = re.search(r'case "\$sha" in\n\s+([0-9a-f|]+)\)', script)
    assert match is not None
    return set(match.group(1).split("|"))


def _run_check(repo: Path, base: str, head: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DCO_BASE_SHA"] = base
    env["DCO_HEAD_SHA"] = head
    return subprocess.run(
        ["bash", "-c", _check_script()],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def _git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def _object_exists(sha: str) -> bool:
    return (
        subprocess.run(["git", "cat-file", "-e", sha], cwd=ROOT, capture_output=True).returncode
        == 0
    )


def _ref_exists(ref: str) -> bool:
    return (
        subprocess.run(
            ["git", "rev-parse", "--verify", "--quiet", ref],
            cwd=ROOT,
            capture_output=True,
        ).returncode
        == 0
    )


def _ensure_pr_history() -> None:
    """The CI checkout is depth 1, so October 5 ancestors are not local yet.

    Those commits are ancestors of this pull request, not advertised tips.
    Deepen this clone instead of asking GitHub for an unadvertised object.
    """
    needed = (*HISTORICAL, HISTORICAL_PARENT)
    notes: list[str] = []
    if not all(_object_exists(sha) for sha in needed):
        fetched = subprocess.run(
            ["git", "fetch", "--no-tags", "--unshallow", "origin"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if fetched.returncode != 0:
            notes.append(fetched.stderr.strip())
            deepened = subprocess.run(
                ["git", "fetch", "--no-tags", "--deepen=400", "origin"],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            if deepened.returncode != 0:
                notes.append(deepened.stderr.strip())
    if not _ref_exists("refs/remotes/origin/main"):
        fetched_main = subprocess.run(
            ["git", "fetch", "--no-tags", "origin", "main:refs/remotes/origin/main"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if fetched_main.returncode != 0:
            notes.append(fetched_main.stderr.strip())
    missing = [sha for sha in needed if not _object_exists(sha)]
    if missing or not _ref_exists("refs/remotes/origin/main"):
        detail = "\n".join(note for note in notes if note)
        pytest.fail(f"DCO history is not available: {missing or ['origin/main']}\n{detail}")


def _init_repo(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "DCO Fixture"], cwd=path, check=True)
    subprocess.run(["git", "config", "user.email", "dco-fixture@example.com"], cwd=path, check=True)


def _commit(repo: Path, message: str, filename: str = "note.txt") -> str:
    target = repo / filename
    target.write_text(message + "\n", encoding="utf-8")
    subprocess.run(["git", "add", filename], cwd=repo, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", message],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    return _git(repo, "rev-parse", "HEAD")


def test_exception_set_is_exactly_two_full_shas() -> None:
    script = _check_script()
    arms = _exception_arms(script)
    assert arms == set(HISTORICAL)
    assert all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in arms)
    assert "*" not in script.split('case "$sha" in', 1)[1].split("esac", 1)[0]
    assert "cursoragent" not in script.lower()
    assert not re.search(r"git (?:log|rev-list)[^\n]*(?:--until|--since|--after|--before)", script)
    assert "git rev-list --no-merges" in script
    assert SIGN_OFF_RE in script

    workflow = _workflow()
    step = next(
        item
        for item in workflow["jobs"]["dco-check"]["steps"]
        if item["name"] == "Check every commit is signed off"
    )
    assert step["env"]["DCO_BASE_SHA"] == "${{ github.event.pull_request.base.sha }}"
    assert step["env"]["DCO_HEAD_SHA"] == "${{ github.event.pull_request.head.sha }}"


def test_governance_record_names_the_same_commits_and_denies_signoff() -> None:
    text = RECORD.read_text(encoding="utf-8")
    for sha in HISTORICAL:
        assert sha in text
    assert "October 9, 2026" in text
    assert "not a retrospective DCO sign-off" in text
    assert "Co-authored-by: Guruprasath Annadurai <Guruprasathannadurai.official@gmail.com>" in text
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    for sha in HISTORICAL:
        assert sha in contributing


def test_historical_commits_have_no_signoff_and_are_recognized() -> None:
    _ensure_pr_history()
    for sha in HISTORICAL:
        message = _git(ROOT, "log", "-1", "--format=%B", sha)
        assert re.search(SIGN_OFF_RE, message, flags=re.MULTILINE) is None
        assert "Co-authored-by: Guruprasath Annadurai <" in message
        assert _git(ROOT, "rev-parse", f"{sha}^")
    result = _run_check(ROOT, HISTORICAL_PARENT, HISTORICAL[1])
    assert result.returncode == 0, result.stdout + result.stderr
    for sha in HISTORICAL:
        assert f"Owner-approved historical DCO exception for {sha}." in result.stdout
    assert "This exception is not a Signed-off-by trailer." in result.stdout
    assert "All commits are signed off." not in result.stdout
    assert "DCO check passed." in result.stdout


def test_candidate_range_passes_with_only_those_exceptions(tmp_path: Path) -> None:
    del tmp_path
    _ensure_pr_history()
    base = _git(ROOT, "rev-parse", "origin/main")
    result = _run_check(ROOT, base, "HEAD")
    assert result.returncode == 0, result.stdout + result.stderr
    unsigned = []
    listed = _git(ROOT, "rev-list", "--no-merges", f"{base}..HEAD").split()
    for sha in listed:
        message = _git(ROOT, "log", "-1", "--format=%B", sha)
        if re.search(SIGN_OFF_RE, message, flags=re.MULTILINE) is None:
            unsigned.append(sha)
    assert set(unsigned) == set(HISTORICAL)


def test_other_unsigned_commit_is_rejected(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    base = _commit(tmp_path, "root\n\nSigned-off-by: DCO Fixture <dco-fixture@example.com>\n")
    child = _commit(
        tmp_path,
        "unsigned change\n\nCo-authored-by: Someone Else <else@example.com>\n",
        filename="change.txt",
    )
    result = _run_check(tmp_path, base, child)
    assert result.returncode == 1
    assert child in result.stdout
    assert "missing a 'Signed-off-by:' trailer." in result.stdout
    assert "historical DCO exception" not in result.stdout


def test_signed_commit_passes_without_using_the_exception(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    base = _commit(tmp_path, "root\n")
    child = _commit(
        tmp_path,
        "signed change\n\nSigned-off-by: DCO Fixture <dco-fixture@example.com>\n",
        filename="signed.txt",
    )
    result = _run_check(tmp_path, base, child)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "historical DCO exception" not in result.stdout
    assert "DCO check passed." in result.stdout


def test_signoff_must_be_a_trailer_line(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    base = _commit(tmp_path, "root\n")
    child = _commit(
        tmp_path,
        "mentions Signed-off-by: DCO Fixture <dco-fixture@example.com> in prose\n",
        filename="prose.txt",
    )
    result = _run_check(tmp_path, base, child)
    assert result.returncode == 1
    assert child in result.stdout


def test_unsigned_merge_is_still_ignored_and_unsigned_parent_is_not(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    base = _commit(
        tmp_path,
        "root\n\nSigned-off-by: DCO Fixture <dco-fixture@example.com>\n",
    )
    signed = _commit(
        tmp_path,
        "feature\n\nSigned-off-by: DCO Fixture <dco-fixture@example.com>\n",
        filename="feature.txt",
    )
    trunk = _git(tmp_path, "branch", "--show-current")
    subprocess.run(["git", "checkout", "-b", "side"], cwd=tmp_path, check=True, capture_output=True)
    side = _commit(
        tmp_path,
        "side\n\nSigned-off-by: DCO Fixture <dco-fixture@example.com>\n",
        filename="side.txt",
    )
    subprocess.run(["git", "checkout", trunk], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "merge", "--no-ff", "-m", "unsigned merge", "side"],
        cwd=tmp_path,
        check=True,
        capture_output=True,
    )
    merge = _git(tmp_path, "rev-parse", "HEAD")
    passed = _run_check(tmp_path, base, merge)
    assert passed.returncode == 0, passed.stdout + passed.stderr
    assert side in _git(tmp_path, "rev-list", "--no-merges", f"{base}..{merge}").split()

    subprocess.run(["git", "checkout", signed], cwd=tmp_path, check=True, capture_output=True)
    unsigned = _commit(tmp_path, "unsigned follow-up\n", filename="follow.txt")
    rejected = _run_check(tmp_path, base, unsigned)
    assert rejected.returncode == 1
    assert unsigned in rejected.stdout
