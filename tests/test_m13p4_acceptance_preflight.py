# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only preflight tests; no security reproductions or privileged actions."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts/engineering/m13p4_security_acceptance.py"
SPEC = importlib.util.spec_from_file_location("m13p4_acceptance_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
preflight = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(preflight)
CANDIDATE = "a" * 40
TREE = "b" * 40


@pytest.fixture
def git_environment(monkeypatch, tmp_path):
    state = {
        "head": CANDIDATE,
        "dirty": "",
        "altered": False,
        "origin": "https://github.com/Guruprasath-Annadurai/Whitepact.git",
        "calls": [],
    }

    def run(command, **kwargs):
        assert command[:4] == ["git", "--no-optional-locks", "-C", str(tmp_path)]
        assert kwargs["check"] and kwargs["capture_output"] and kwargs["timeout"] == 20
        args = command[4:]
        state["calls"].append(args)
        if args == ["rev-parse", "--show-toplevel"]:
            output = str(tmp_path)
        elif args == ["rev-parse", "HEAD"]:
            output = state["head"]
        elif args == ["rev-parse", "HEAD^{tree}"]:
            output = TREE
        elif args[0] == "rev-parse" and args[1].startswith(preflight.SECURITY_REFERENCE + ":"):
            output = preflight.ORIGINAL_BLOBS[Path(args[1]).name]
        elif args[0] == "status":
            output = state["dirty"]
        elif args == ["remote", "get-url", "origin"]:
            output = state["origin"]
        elif args == ["ls-tree", "-r", CANDIDATE, "--", preflight.REPRODUCER_DIRECTORY]:
            blobs = dict(preflight.ORIGINAL_BLOBS)
            if state["altered"]:
                blobs["test_durable_crash_probe.py"] = "c" * 40
            output = "\n".join(
                f"100644 blob {blob}\t{preflight.REPRODUCER_DIRECTORY}/{name}"
                for name, blob in blobs.items()
            )
        elif args[:2] == ["ls-tree", CANDIDATE]:
            output = f"100644 blob {'d' * 40}\t{args[-1]}"
        else:
            raise AssertionError(f"Unexpected command: {command!r}")
        return subprocess.CompletedProcess(command, 0, stdout=output + "\n", stderr="")

    monkeypatch.setattr(preflight.subprocess, "run", run)
    return tmp_path, state


def test_matching_candidate_emits_blocked_plan_without_execution(git_environment):
    repo, state = git_environment
    result = preflight.preflight(repo, CANDIDATE)
    assert result["candidate"] == CANDIDATE and result["tree"] == TREE
    assert result["acceptance"] == "BLOCKED"
    assert result["execution"] == "NOT EXECUTED"
    assert len(result["original_reproducer_blobs"]) == 8
    for path in preflight.PLANNED_TESTS:
        assert path in result["planned_command"]
    assert all(call[0] in {"rev-parse", "status", "remote", "ls-tree"} for call in state["calls"])


def test_wrong_head_is_refused(git_environment):
    repo, state = git_environment
    state["head"] = "e" * 40
    with pytest.raises(preflight.PreflightError, match="Actual HEAD"):
        preflight.preflight(repo, CANDIDATE)


@pytest.mark.parametrize("dirty", [" M src/file.py", "?? unexpected.txt"])
def test_tracked_and_untracked_changes_are_refused(git_environment, dirty):
    repo, state = git_environment
    state["dirty"] = dirty
    with pytest.raises(preflight.PreflightError, match="tracked or untracked"):
        preflight.preflight(repo, CANDIDATE)


def test_changed_original_blob_is_refused(git_environment):
    repo, state = git_environment
    state["altered"] = True
    with pytest.raises(preflight.PreflightError, match="pinned M13-R3 blob"):
        preflight.preflight(repo, CANDIDATE)


def test_noncanonical_origin_is_refused(git_environment):
    repo, state = git_environment
    state["origin"] = "https://github.com/example/other.git"
    with pytest.raises(preflight.PreflightError, match="canonical"):
        preflight.preflight(repo, CANDIDATE)


def test_abbreviated_candidate_is_refused_before_git(git_environment):
    repo, state = git_environment
    with pytest.raises(preflight.PreflightError, match="exact full"):
        preflight.preflight(repo, CANDIDATE[:7])
    assert not state["calls"]
