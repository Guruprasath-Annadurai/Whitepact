# Release boundary

This workstream is isolated from the production release candidate.

| Item | Value |
|---|---|
| Branch | `cursor/whitepact-global-ecosystem-readiness-ed96` |
| Base commit | `35488a68e587df2adfdb1ceaad44001faca524a4` |
| Base subject | `merge(website): integrate qualified release-sync 9c43229` |
| Qualified platform parent | `c1d7803fce0787f9183e18bb38134f73a6c0f57d` |
| Qualified website parent | `9c43229fa3ce91bdc975240deaa8b0e568871325` |
| Worktree | `/opt/cursor/worktrees/whitepact-ecosystem` |
| Default branch at audit | `main` = `38f927229b4ea53d19a9107c78653307f5263629` |
| Active remediation PR | https://github.com/Guruprasath-Annadurai/Whitepact/pull/167 |
| PR 167 head | `cursor/whitepact-rc-remediation-b6a9` at `0ef9bc43bf17c5f0ee84018354a2e849dd93f054` |
| Integrated candidate PR | https://github.com/Guruprasath-Annadurai/Whitepact/pull/166 |

The base commit was confirmed as the tip of
`origin/cursor/whitepact-final-all-lanes-rc` at the time of branching. This
branch was created from that exact commit in a separate worktree. It does
not rebase, merge, amend, or cherry-pick the remediation branch.

## Not done

- No merge to `main`
- No change to PR 167
- No cloud, Terraform, or DNS change
- No package, image, or Space publish
- No directory submission
- No social post
- No edit to authorization, tenant isolation, MCP enforcement, approval, or grant logic

## What changed on purpose

Documentation under `docs/ecosystem/`, a local runtime demonstration under
`examples/ecosystem/`, claim guards under `tests/`, a README install note,
a CONTRIBUTING tool-count correction, and `server.json` so the registry
manifest points at the published PyPI release `1.2.6` instead of `1.2.2`.

A separate commit changes only the source Trove development-status
classifier. That commit does not publish the package. The live PyPI `1.2.6`
artifact is unchanged.

## Requalification

`server.json` and the Trove classifier are public metadata. They are not
wired into the authorization decision. They still should be reviewed on
their own before anyone merges this branch into a release candidate. Merging
is an integration decision for a later lane.
