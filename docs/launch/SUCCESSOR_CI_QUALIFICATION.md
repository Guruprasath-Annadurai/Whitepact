# Successor CI qualification

PR #169 stays a draft targeted at `cursor/whitepact-rc-remediation-b6a9`. It is not retargeted to `main`.

## Why that base is the qualification base

Local `git merge-tree --write-tree` on this worktree:

| Base | Result |
|------|--------|
| `cursor/whitepact-rc-remediation-b6a9` (`0cdef3947503adf7c3f08a5116a4808deda1d3f7`) | Equal to the branch head tree. First observed for `47adb948` as `c0401db2533bba9b8dfaab2a5902bf88aa17e434`. The base stays an ancestor, so later commits on this branch keep that equality. Recompute with `git merge-tree --write-tree origin/cursor/whitepact-rc-remediation-b6a9 HEAD`. |
| `main` (`38f927229b4ea53d19a9107c78653307f5263629`) | Same tree. `main` is an ancestor. A pull request to `main` was not opened. |
| `release/whitepact-v1-rc` (`683d1c382ee2fe4a37c2335f201029d47e8471ae`) | `fatal: refusing to merge unrelated histories` |

A qualification pull request onto `release/whitepact-v1-rc` would not test this source tree. It is not used.

## What GitHub checks out

`actions/checkout` on `pull_request` checks out the synthetic merge commit. Its SHA is not the candidate head. The CI job `Candidate tree matches checkout` fetches `pull/<number>/head` and fails if that tree differs from the merge checkout. When it prints `TESTED TREE MATCHES CANDIDATE HEAD TREE`, the other jobs on that run tested the candidate tree even though their checkout SHA is the merge SHA.

DCO checks out `github.event.pull_request.head.sha` directly.

## Workflows enabled for this base

Pull-request triggers for this base were added, without changing push-to-main behavior, on CI, DCO, CodeQL, Gitleaks, Dependency Review, OpenSSF Policy Guard, Reproducible Build, and the self-conducted security scan. Thresholds are unchanged.

Publish and Terraform apply workflows were not given this trigger.

## Container build

No workflow in `.github/workflows` runs `docker build`. `scripts/ci-docker-isolation.sh` needs a local Docker daemon. That is not a GitHub-hosted required job on this candidate.
