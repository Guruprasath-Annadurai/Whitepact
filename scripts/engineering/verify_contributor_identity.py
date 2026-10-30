# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only pre-publication metadata check; not proof of human DCO consent."""

import argparse
import hashlib
import os
import re
import subprocess
import sys

IDENTITY = "Guruprasath Annadurai <annaduraiguruprasath7@gmail.com>"


def git(*args, input=None):
    # Read-only subprocesses: no shell, replacement history, grafts or lazy fetching.
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_NO_LAZY_FETCH="1", GIT_GRAFT_FILE=os.devnull)
    result = subprocess.run(
        ["git", "--no-replace-objects", "-c", "advice.graftFileDeprecated=false", *args],
        input=None if input is None else input.encode("utf-8"),
        capture_output=True,
        check=True,
        timeout=30,
        env=env,
    )
    if result.stderr:
        raise ValueError("Git reported an ambiguous diagnostic.")
    return result.stdout.decode("utf-8", errors="strict")


def commit_data(sha):
    raw = git("cat-file", "commit", sha)
    data = raw.encode("utf-8")
    if hashlib.sha1(b"commit " + str(len(data)).encode() + b"\0" + data).hexdigest() != sha:
        raise ValueError("Commit object integrity mismatch.")
    header, separator, message = raw.partition("\n\n")
    message = message.replace("\r\n", "\n")
    if not separator or any(ord(c) < 32 and c not in "\n\t" for c in header + message):
        raise ValueError("Malformed commit object.")
    fields = {}
    previous = None
    for line in header.splitlines():
        if line.startswith(" "):
            if previous not in ("gpgsig", "gpgsig-sha256", "mergetag"):
                raise ValueError("Malformed commit header continuation.")
            continue
        key, space, value = line.partition(" ")
        if not space or not re.fullmatch(r"[a-zA-Z0-9-]+", key):
            raise ValueError("Malformed commit header.")
        fields.setdefault(key, []).append(value)
        previous = key
    for key in ("tree", "author", "committer"):
        if len(fields.get(key, [])) != 1:
            raise ValueError("Missing or duplicate commit identity/tree header.")
    tree = fields["tree"][0]
    parents = fields.get("parent", [])
    if any(not re.fullmatch(r"[0-9a-f]{40}", x) for x in [tree, *parents]):
        raise ValueError("Malformed tree/parent object ID.")
    if len(set(parents)) != len(parents) or git("cat-file", "-t", tree).strip() != "tree":
        raise ValueError("Invalid tree or duplicate parents.")
    encoding = fields.get("encoding", ["UTF-8"])
    if len(encoding) != 1 or encoding[0].casefold() not in ("utf-8", "utf8"):
        raise ValueError("Ambiguous commit encoding.")
    for key in ("author", "committer"):
        if not re.fullmatch(
            re.escape(IDENTITY) + r" -?\d+ [+-](?:[01]\d|2[0-3])[0-5]\d", fields[key][0]
        ):
            raise ValueError("Unauthorized or malformed " + key + ": " + sha)
    return parents, message


def verify_signoffs(message, merge):
    # --parse does not add configured trailers; --no-divider treats this as a
    # commit message, not a format-patch payload with a hidden unsigned suffix.
    parsed = git(
        "-c", "trailer.separators=:", "interpret-trailers", "--parse", "--no-divider", input=message
    )
    signoffs = []
    for line in parsed.splitlines():
        key, colon, value = line.partition(":")
        if not colon:
            raise ValueError("Malformed Git trailer parser output.")
        if key.casefold() == "signed-off-by":
            signoffs.append(value.strip())
    candidates = [
        line
        for line in message.splitlines()
        if re.match(r"\s*signed[\s_-]*off[\s_-]*by\b", line, re.IGNORECASE)
    ]
    valid_line = r"(?i:Signed-off-by)[ \t]*:[ \t]*" + re.escape(IDENTITY) + r"[ \t]*"
    if len(candidates) != len(signoffs) or any(
        not re.fullmatch(valid_line, line) for line in candidates
    ):
        raise ValueError("Body-only, malformed or ambiguous signoff.")
    if candidates:
        # Git also recognizes some mixed prose/trailer blocks heuristically.
        # A DCO block must be unambiguous: only trailer lines, not trailing prose.
        block = re.split(r"\n[ \t]*\n", message.rstrip("\n"))[-1]
        if any(not re.fullmatch(r"[A-Za-z0-9-]+[ \t]*:.*", line) for line in block.splitlines()):
            raise ValueError("Ambiguous prose or continuation in DCO trailer block.")
    if signoffs != [IDENTITY] and not (merge and not signoffs):
        raise ValueError("Missing, duplicate or unauthorized signoff.")


def verify_range(base, head):
    for sha in (base, head):
        if git("rev-parse", "--verify", sha + "^{commit}").strip() != sha:
            raise ValueError("Expected an exact commit object.")
    if git("rev-parse", "--is-shallow-repository").strip() != "false":
        raise ValueError("Complete history is required.")
    git("merge-base", "--is-ancestor", base, head)
    for field in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        if not re.fullmatch(re.escape(IDENTITY) + r" -?\d+ [+-]\d{4}", git("var", field).strip()):
            raise ValueError("Effective local identity is not approved: " + field)
    commits = git("rev-list", base + ".." + head).splitlines()
    if not commits:
        raise ValueError("Empty contribution range; nothing qualified.")
    if len(set(commits)) != len(commits) or any(
        not re.fullmatch(r"[0-9a-f]{40}", sha) for sha in commits
    ):
        raise ValueError("Malformed traversal output.")
    for sha in commits:
        parents, message = commit_data(sha)
        # A merge's own signoff stays optional; every introduced parent commit
        # is still traversed and validated, including second-parent history.
        verify_signoffs(message, merge=len(parents) >= 2)
    print(
        f"Metadata PASS: {len(commits)} commits. Human contribution-specific consent still required."
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    for sha in (args.base, args.head):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            parser.error("Use full, immutable commit SHAs.")
    try:
        return verify_range(args.base, args.head)
    except (ValueError, OSError, UnicodeError, subprocess.SubprocessError):
        # Never turn a parser, encoding, process or object failure into PASS.
        print(
            "REFUSED: identity, object, history or DCO trailer validation failed.", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
