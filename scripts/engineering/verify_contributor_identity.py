# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Read-only pre-publication metadata check; not proof of human DCO consent."""

import argparse
import re
import subprocess
import sys

IDENTITY = "Guruprasath Annadurai <annaduraiguruprasath7@gmail.com>"


def git(*args):
    return subprocess.check_output(["git", *args], text=True, encoding="utf-8").strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", required=True)
    parser.add_argument("--head", required=True)
    args = parser.parse_args()
    for sha in (args.base, args.head):
        if not re.fullmatch(r"[0-9a-f]{40}", sha):
            parser.error("Use full, immutable commit SHAs.")
        if git("rev-parse", sha + "^{commit}") != sha:
            parser.error("Expected an exact commit object.")
    for field in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
        if not git("var", field).startswith(IDENTITY + " "):
            raise ValueError("Effective local identity is not approved: " + field)
    commits = git("rev-list", args.base + ".." + args.head).splitlines()
    if not commits:
        raise ValueError("Empty contribution range; nothing qualified.")
    failed = False
    for sha in commits:
        author = git("show", "-s", "--format=%an <%ae>", sha)
        committer = git("show", "-s", "--format=%cn <%ce>", sha)
        parents = git("show", "-s", "--format=%P", sha).split()
        message = git("show", "-s", "--format=%B", sha)
        if author != IDENTITY or committer != IDENTITY:
            print("REFUSED unauthorized author/committer: " + sha)
            failed = True
        if len(parents) < 2 and "Signed-off-by: " + IDENTITY not in message.splitlines():
            print("REFUSED missing approved signoff: " + sha)
            failed = True
    if failed:
        return 1
    print(f"Metadata PASS: {len(commits)} commits. Human contribution-specific consent still required.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, subprocess.CalledProcessError) as exc:
        print("REFUSED: " + str(exc), file=sys.stderr)
        sys.exit(1)
