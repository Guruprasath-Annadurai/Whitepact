# Blockers and dependencies

Nothing in this list was bypassed. Items marked for the main engineering
lane need product or security work that this branch is not allowed to do.

## P0 — do not misstate

- Do not advertise `rai-governance-platform==1.3.1` as installable. PyPI
  latest on 2026-10-09 was `1.2.6`.
- Do not say `pip install whitepact` works. That project name returned 404.
- Do not describe the hosted MCP endpoint as an anonymous demo. It returns
  401 without a bearer credential.
- Do not treat `whitepact.com` as the qualified marketing site. The live
  response is the ResponsibleAI dashboard at version `1.2.6`.

## P1 — blocks a free submission that is otherwise close

- DevHunt requires screenshots. No authentic product-UI screenshot is in
  the repository. `web/public/assets/og-whitepact-phase3.png` is a logo
  card. `trust-core-head.webp` is an illustration, not the product.
- CNCF Landscape generally asks for 300 GitHub stars and an SVG logo with
  the name on a transparent background. Stars were 2. No SVG master exists.
- Docker Hub has no `whitepact` repository. Publishing an image is not
  authorized here.
- LlamaIndex, CrewAI, and AutoGen have no adapter. Do not claim one.
  Building those adapters is new product work for a later lane, not a
  security-code change this lane should invent.

## P1 — existing listings are stale

- Official MCP registry latest is still package pin `1.2.2` / listing
  `1.2.3`. This branch’s `server.json` is a correction package only.
- Smithery’s public page says “No description”.
- MCP Market’s page says “Claim this listing”.
- Glama still mirrors older tool-count wording.
- Published wheel `1.2.6` still classifies the package as
  Production/Stable and maps `whitepact` to the legacy CLI.

## P2 — owner prerequisites

- Hugging Face static Space files are local. An owner account must upload
  them. Do not select paid hardware.
- GitHub Discussions draft is local. The owner posts it.
- Future Tools and Ignlab are ready to paste, then wait for human review.
- Group D directories whose fee or form could not be fetched stay GREY.
  The owner verifies the live form before typing anything.

## P3 — enterprise programs that stay blocked

- AWS Marketplace seller listing
- GitHub Marketplace app listing
- CSA STAR publication
- Linux Foundation project hosting
- OpenSSF organizational membership

The free OpenSSF Best Practices silver badge is already live and is not
one of these memberships.

## Dependency on the release lane

This branch starts at `35488a68e587df2adfdb1ceaad44001faca524a4`. It does
not contain PR 167’s remediation commits. If the release candidate moves,
re-apply this documentation only by a later integration decision. Do not
merge this branch into the release candidate from this lane.
