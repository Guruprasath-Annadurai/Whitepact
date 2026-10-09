# Submission master

This is the founder’s copy sheet for free submissions. It is not a record of
anything submitted. Do not pay for a listing. Do not publish a package, image,
or Space from this branch.

## Identity

| Field | Value |
|---|---|
| Product name | WhitePact |
| Python distribution | `rai-governance-platform` |
| Import name | `responsibleai` |
| Do not install | `pip install whitepact` |
| Newest PyPI release verified 2026-10-09 | `1.2.6` |
| Source version in this commit’s parent tree | `1.3.1` (not a PyPI release) |
| License | MIT |
| Repository | https://github.com/Guruprasath-Annadurai/Whitepact |
| Security contact | annaduraiguruprasath7@gmail.com |
| Private advisories | https://github.com/Guruprasath-Annadurai/Whitepact/security/advisories/new |
| Public issues | https://github.com/Guruprasath-Annadurai/Whitepact/issues |

## Positioning that is allowed

Open-source runtime authorization and governance for autonomous AI agents.

Available for self-hosted technical evaluation using documented releases or qualified source.

Enterprise hosted release undergoing operational qualification.

## Copy

Use `docs/ecosystem/copy/DESCRIPTIONS.md` without rewriting the version,
license, or limitation paragraphs. The 50-word, 100-word, and 200-word
descriptions are the ones to paste into forms.

## Install block

```bash
pip install "rai-governance-platform[dashboard]==1.2.6"
whitepact-mcp
```

On the published 1.2.6 wheel, `whitepact` still starts `biasbuster.cli:main`.
`whitepact-mcp` is the stdio MCP entrypoint. `whitepact-mcp-http` is the HTTP
entrypoint.

## MCP stdio block

```bash
uvx --from rai-governance-platform==1.2.6 whitepact-mcp
```

## What not to paste

Do not paste source version `1.3.1` as a `pip` pin. Do not paste a customer
count, a certification, or a claim that the hosted enterprise service is
available worldwide. Do not paste the robot illustration at
`web/public/assets/trust-core-head.webp` as a product screenshot.

## Ready for the owner to submit

These are GREEN in the matrix. Submission is still the owner’s action.

1. Future Tools: https://futuretools.io/submit-a-tool
2. Ignlab Launch: https://launch.ignlab.net/submit.html
3. GitHub Discussions: https://github.com/Guruprasath-Annadurai/Whitepact/discussions

DevHunt is prepared but not GREEN until an authentic UI screenshot exists.
The official FAQ requires screenshots.

## Already live — update, do not duplicate

Official MCP Registry, Glama, Smithery, MCP Market, OpenSSF Best Practices
project 14112, PyPI project `rai-governance-platform`, and the existing GitHub
topics. Details and correction text are in `ALREADY_LIVE_DIRECTORY_AUDIT.md`.
