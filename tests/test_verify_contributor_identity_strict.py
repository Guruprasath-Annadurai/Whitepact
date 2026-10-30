# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real disposable Git graphs; fixture identities are not human DCO declarations."""

import hashlib
import importlib.util
import os
import subprocess
import sys

import pytest
from scripts.engineering import verify_contributor_identity as current

NAME = "Synthetic checker fixture"
EMAIL = "fixture@invalid.example"
IDENTITY = f"{NAME} <{EMAIL}>"
SIGNOFF = "Signed-off-by: " + IDENTITY
VALID = "Synthetic test only\n\n" + SIGNOFF + "\n"
OTHER = "Unapproved synthetic fixture <other@invalid.example>"


def git(*args, input=None, env=None):
    return (
        subprocess.check_output(
            ["git", *args], input=None if input is None else input.encode("utf-8"), env=env
        )
        .decode("utf-8")
        .strip()
    )


@pytest.fixture
def graph(tmp_path, monkeypatch):
    # Never attribute test objects or signoffs to the founder or another real human.
    for key in list(os.environ):
        if key.startswith(("GIT_AUTHOR_", "GIT_COMMITTER_", "GIT_CONFIG_")):
            monkeypatch.delenv(key)
    monkeypatch.chdir(tmp_path)
    git("init", "--quiet")
    git("config", "user.name", NAME)
    git("config", "user.email", EMAIL)
    tree = git("hash-object", "-t", "tree", "-w", "--stdin", input="")

    def commit(message=VALID, parents=(), author=None, committer=None):
        args = ["commit-tree", tree]
        for parent in parents:
            args.extend(["-p", parent])
        env = os.environ.copy()
        for kind, identity in (("AUTHOR", author), ("COMMITTER", committer)):
            if identity:
                env[f"GIT_{kind}_NAME"] = identity.split(" <")[0]
                env[f"GIT_{kind}_EMAIL"] = identity.split("<")[1].rstrip(">")
        return git(*args, input=message, env=env)

    base = commit()
    git("update-ref", "refs/heads/main", base)
    source = os.environ.get("WHITEPACT_DCO_CHECKER_SOURCE")
    if source:
        spec = importlib.util.spec_from_file_location("baseline_checker", source)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
    else:
        checker = current
    monkeypatch.setattr(checker, "IDENTITY", IDENTITY)
    return checker, commit, base, tmp_path


def run(graph, monkeypatch, head, base=None):
    checker, _, initial, _ = graph
    monkeypatch.setattr(sys, "argv", ["checker", "--base", base or initial, "--head", head])
    try:
        return checker.main()
    except SystemExit as exc:
        return exc.code
    except (ValueError, subprocess.CalledProcessError, OSError, UnicodeError):
        # The published CLI's original entrypoint translates these failures to refusal.
        return 1


def test_valid_authorized_contribution(graph, monkeypatch):
    assert run(graph, monkeypatch, graph[1](parents=[graph[2]])) == 0


def test_valid_crlf_message(graph, monkeypatch):
    assert run(graph, monkeypatch, graph[1](VALID.replace("\n", "\r\n"), [graph[2]])) == 0


@pytest.mark.parametrize(
    "message",
    [
        "No signoff\n",
        "Body impersonation\n\n" + SIGNOFF + "\n\nUnrelated prose.\n",
        VALID + "Signed-off-by: " + OTHER + "\n",
        VALID + SIGNOFF + "\n",
        "Malformed\n\nSigned-off-by " + IDENTITY + "\n",
        "Malformed\n\nSigned-off-by: " + NAME + " fixture@invalid.example\n",
        "Malformed extra\n\n" + SIGNOFF + "\nSigned-off-by invalid\n",
        "Folded identity\n\nSigned-off-by: " + NAME + "\n <" + EMAIL + ">\n",
        "Body plus real\n\n" + SIGNOFF + "\n\nProse\n\n" + SIGNOFF + "\n",
        "Divider ambiguity\n\n" + SIGNOFF + "\n---\nUnsigned trailing prose\n",
    ],
)
def test_refuses_missing_forged_mixed_or_malformed_signoffs(graph, monkeypatch, message):
    assert run(graph, monkeypatch, graph[1](message, [graph[2]])) == 1


@pytest.mark.parametrize("field", ["author", "committer"])
def test_author_and_committer_independently_refused(graph, monkeypatch, field):
    assert run(graph, monkeypatch, graph[1](parents=[graph[2]], **{field: OTHER})) == 1


def test_git_conventional_key_case_and_spacing(graph, monkeypatch):
    message = "Valid Git syntax\n\nsigned-off-by :\t" + IDENTITY + "\n"
    assert run(graph, monkeypatch, graph[1](message, [graph[2]])) == 0


def test_merge_with_signed_introduced_parents_without_own_signoff(graph, monkeypatch, capsys):
    checker, commit, base, _ = graph
    left, right = commit(parents=[base]), commit("Side\n\n" + SIGNOFF, [base])
    assert run(graph, monkeypatch, commit("Synthetic merge\n", [left, right])) == 0
    assert "Metadata PASS: 3 commits" in capsys.readouterr().out


def test_merge_with_valid_own_signoff(graph, monkeypatch):
    _, commit, base, _ = graph
    left, right = commit(parents=[base]), commit("Side\n\n" + SIGNOFF, [base])
    assert run(graph, monkeypatch, commit(VALID, [left, right])) == 0


@pytest.mark.parametrize("field", ["author", "committer"])
def test_unauthorized_merge_metadata(graph, monkeypatch, field):
    _, commit, base, _ = graph
    left, right = commit(parents=[base]), commit("Side\n\n" + SIGNOFF, [base])
    assert run(graph, monkeypatch, commit("Merge\n", [left, right], **{field: OTHER})) == 1


@pytest.mark.parametrize(
    "message", ["Merge\n\nSigned-off-by: " + OTHER, "Merge\n\nSigned-off-by invalid"]
)
def test_merge_cannot_smuggle_unauthorized_or_malformed_signoffs(graph, monkeypatch, message):
    _, commit, base, _ = graph
    left, right = commit(parents=[base]), commit("Side\n\n" + SIGNOFF, [base])
    assert run(graph, monkeypatch, commit(message, [left, right])) == 1


@pytest.mark.parametrize("fault", ["unsigned", "unauthorized"])
def test_merge_does_not_hide_bad_second_parent(graph, monkeypatch, fault):
    _, commit, base, _ = graph
    left = commit(parents=[base])
    right = commit(
        "Unsigned\n" if fault == "unsigned" else VALID,
        [base],
        author=OTHER if fault == "unauthorized" else None,
    )
    assert run(graph, monkeypatch, commit("Merge\n", [left, right])) == 1


@pytest.mark.parametrize("head", ["HEAD", "abc123", "0" * 40, "f" * 40])
def test_invalid_or_unavailable_commit_sha(graph, monkeypatch, head):
    assert run(graph, monkeypatch, head) != 0


def test_empty_range_refused(graph, monkeypatch):
    assert run(graph, monkeypatch, graph[2]) == 1


def test_unrelated_base_refused(graph, monkeypatch):
    _, commit, base, _ = graph
    unrelated = commit("Independent root\n\n" + SIGNOFF)
    assert run(graph, monkeypatch, commit(parents=[base]), base=unrelated) == 1


@pytest.mark.parametrize("kind", ["AUTHOR", "COMMITTER"])
def test_effective_environment_identity_override_refused(graph, monkeypatch, kind):
    head = graph[1](parents=[graph[2]])
    monkeypatch.setenv(f"GIT_{kind}_NAME", "Unapproved synthetic fixture")
    assert run(graph, monkeypatch, head) == 1


def test_parser_error_fails_closed(graph, monkeypatch):
    checker, commit, base, _ = graph
    head = commit(parents=[base])
    original = checker.git

    def fail_parser(*args, **kwargs):
        if "interpret-trailers" in args:
            raise subprocess.CalledProcessError(1, ["git", "interpret-trailers"])
        return original(*args, **kwargs)

    monkeypatch.setattr(checker, "git", fail_parser)
    assert run(graph, monkeypatch, head) == 1


@pytest.mark.parametrize("fault", ["output", "timeout", "encoding"])
def test_parser_ambiguity_fails_closed(graph, monkeypatch, fault):
    checker, commit, base, _ = graph
    head = commit(parents=[base])
    original = checker.git

    def bad_parser(*args, **kwargs):
        if "interpret-trailers" in args:
            if fault == "timeout":
                raise subprocess.TimeoutExpired("git", 30)
            if fault == "encoding":
                raise UnicodeDecodeError("utf8", b"\xff", 0, 1, "synthetic invalid output")
            return "malformed parser output\n"
        return original(*args, **kwargs)

    monkeypatch.setattr(checker, "git", bad_parser)
    assert run(graph, monkeypatch, head) == 1


def test_duplicate_identity_header_refused(graph, monkeypatch):
    original = git("cat-file", "commit", graph[1](parents=[graph[2]]))
    author = next(line for line in original.splitlines() if line.startswith("author "))
    malformed = original.replace(author, author + "\n" + author, 1)
    bad = git("hash-object", "-t", "commit", "--literally", "-w", "--stdin", input=malformed)
    assert run(graph, monkeypatch, bad) == 1


def test_shallow_history_refused(graph, monkeypatch):
    _, commit, base, repo = graph
    hidden = commit("Unsigned\n", [base])
    head = commit(parents=[hidden])
    (repo / ".git" / "shallow").write_text(head + "\n", encoding="ascii")
    assert run(graph, monkeypatch, head) == 1


def test_local_trailer_separator_config_cannot_redefine_dco(graph, monkeypatch):
    git("config", "trailer.separators", "=")
    assert run(graph, monkeypatch, graph[1](parents=[graph[2]])) == 0


@pytest.mark.parametrize("fault", ["diagnostic", "missing-executable", "timeout"])
def test_git_parser_process_faults_fail_closed(graph, monkeypatch, fault):
    checker, commit, base, _ = graph
    head = commit(parents=[base])
    original = subprocess.run

    def process_fault(args, *a, **kwargs):
        if "interpret-trailers" in args:
            if fault == "missing-executable":
                raise FileNotFoundError("Synthetic missing executable")
            if fault == "timeout":
                raise subprocess.TimeoutExpired(args, 30)
            return subprocess.CompletedProcess(args, 0, b"", b"Synthetic parser diagnostic")
        return original(args, *a, **kwargs)

    monkeypatch.setattr(checker.subprocess, "run", process_fault)
    assert run(graph, monkeypatch, head) == 1


def test_commit_read_integrity_mismatch_refused(graph, monkeypatch):
    checker, commit, base, _ = graph
    head = commit(parents=[base])
    original = checker.git

    def changed_object(*args, **kwargs):
        raw = original(*args, **kwargs)
        return raw + "\n" if args[:2] == ("cat-file", "commit") else raw

    monkeypatch.setattr(checker, "git", changed_object)
    assert run(graph, monkeypatch, head) == 1


def test_ambiguous_history_output_refused(graph, monkeypatch):
    checker, commit, base, _ = graph
    head = commit(parents=[base])
    original = checker.git

    def changed_walk(*args, **kwargs):
        raw = original(*args, **kwargs)
        return raw + raw if args[0] == "rev-list" else raw

    monkeypatch.setattr(checker, "git", changed_walk)
    assert run(graph, monkeypatch, head) == 1


def test_malformed_commit_object_refused(graph, monkeypatch):
    tree = git("rev-parse", graph[2] + "^{tree}")
    raw = f"tree {tree}\nparent {graph[2]}\nauthor broken\n\n" + VALID
    bad = git("hash-object", "-t", "commit", "--literally", "-w", "--stdin", input=raw)
    assert run(graph, monkeypatch, bad) == 1


def test_checker_does_not_mutate_git_files(graph, monkeypatch):
    _, commit, base, repo = graph
    head = commit(parents=[base])
    git("update-ref", "refs/heads/main", head)

    def snapshot():
        return {
            str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in (repo / ".git").rglob("*")
            if p.is_file()
        }

    before = snapshot()
    assert run(graph, monkeypatch, head) == 0
    assert snapshot() == before
