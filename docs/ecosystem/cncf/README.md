# CNCF Landscape draft — do not submit

Status: RED.

The landscape README at https://github.com/cncf/landscape says cloud-native
projects with at least 300 GitHub stars that fit an existing category are
generally included, and that the logo must be an SVG containing the name,
without a reversed dark background. On 2026-10-09 this repository had 2
stars and no SVG master.

WhitePact is an open-source runtime authorization project with a Dockerfile
and Helm chart. That is not enough to claim a CNCF category or membership.
The closest honest category, if a later submission is ever appropriate, is
Security & Compliance rather than a claim of CNCF project status. This draft
does not assert membership, endorsement, or acceptance.

## Files

- `landscape-entry.yml` is a pull-request-shaped fragment. Do not open the
  upstream pull request.
- `whitepact-wordmark-draft.svg` is a transparent text wordmark so the
  package is not missing a file. Replace it with the real vector logo
  before any submission.

## Evidence to attach later, not now

- MIT license: `LICENSE`
- Repository: https://github.com/Guruprasath-Annadurai/Whitepact
- Technical relevance: runtime policy before agent actions, packaged with
  containers and Helm in this repository
