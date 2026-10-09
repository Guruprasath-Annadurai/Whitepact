# Founder manual actions

Do these yourself. This branch does not submit, post, publish, or pay.

## Wave 1 — paste now

Future Tools and Ignlab are the two external directories. GitHub Discussions
is a post in this repository, not a third directory.

1. Future Tools. Open https://futuretools.io/submit-a-tool. Use the product
   name WhitePact, the URL https://whitepact.com, and the 100-word
   description. Say the pricing model is open source with a hosted release
   still in qualification. Expect a human decision. Inclusion is not
   promised.
2. Ignlab Launch. Open https://launch.ignlab.net/submit.html. No account is
   required. Website URL must be the bare origin `https://whitepact.com`.
   Tagline: `Open-source runtime authorization for AI agents.` Paste the
   200-word description. Logo URL can be the raw repository logo once you
   choose a public image URL you control. Screenshot is optional.
3. GitHub Discussions. Open
   https://github.com/Guruprasath-Annadurai/Whitepact/discussions/new?category=show-and-tell
   and post:

```text
WhitePact is open-source runtime authorization and governance for autonomous AI agents. The Python package is rai-governance-platform. The newest PyPI release on 2026-10-09 is 1.2.6. Source 1.3.1 is not published yet.

Install:
pip install "rai-governance-platform[dashboard]==1.2.6"

MCP stdio:
uvx --from rai-governance-platform==1.2.6 whitepact-mcp

The hosted MCP endpoint requires a bearer credential. The hosted enterprise release is undergoing operational qualification. License: MIT.
https://github.com/Guruprasath-Annadurai/Whitepact
```

## Wave 1 — after a real screenshot exists

4. DevHunt. Sign in with GitHub at https://devhunt.org/account/tools/new.
   The FAQ requires a logo and screenshots. Use a capture of the real
   dashboard or docs UI. Do not upload the robot illustration as a product
   screenshot. Choose the free queue unless you decide later to pay. This
   budget does not include that payment.

## Wave 2 — correct live listings, do not duplicate them

5. Publish `server.json` to the official MCP registry with your existing
   publisher login. The file in this branch pins PyPI `1.2.6`. Review the
   diff first. Publishing was not done here.
6. Refresh Glama and Smithery from that registry update. On Smithery, fill
   the empty description. The Smithery URL that works is
   https://smithery.ai/servers/guruprasathannadurai-official/whitepact
7. Claim https://mcpmarket.com/server/whitepact if the claim flow is free.
   Stop if it asks for payment.
8. Open the MCPBeat and AlternativeTo URLs in a browser. This environment
   received HTTP 403. Update them only if you can see that they are the
   same project.
9. Leave the OpenSSF silver badge in place. Do not file it as a certification.
10. Do not upload a new PyPI release from this branch.

## Wave 3 — only if you accept the remaining gap

11. Hugging Face. Create a Space on the free static SDK and upload
    `docs/ecosystem/huggingface-space/`. Do not attach paid compute.
12. Do not open the CNCF Landscape pull request. The draft in
    `docs/ecosystem/cncf/` is blocked on the 300-star guideline and a real
    SVG logo.
13. Do not push a Docker image.

## Wave 4 — verify the form, then paste the same master

14. For every GREY row in `PLATFORM_ELIGIBILITY_MATRIX.md`, open the
    official URL, confirm the fee is zero, and only then paste
    `copy/DESCRIPTIONS.md`. If the form requires a live SaaS checkout or a
    payment, skip it.

## Wave 5 — leave blocked

15. Do not start AWS Marketplace, GitHub Marketplace, CSA STAR, Linux
    Foundation hosting, or OpenSSF membership.

## Optional GitHub topics

Current topics already cover the project. If you want two more, `python`
and `mit-license` match the repository. Do not add certification topics.
