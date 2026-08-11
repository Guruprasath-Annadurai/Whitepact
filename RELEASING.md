# Releasing

How a version of this project actually gets published — written down
once so it doesn't have to be reconstructed from memory or from
reading `publish.yml` cold each time. MIGRATION_WHITEPACT_V2.md Phase
16 (release engineering).

## Versioning

[Semantic Versioning](https://semver.org/spec/v2.0.0.html), tracked in
one place: `pyproject.toml`'s `version` field. `src/responsibleai/__init__.py`'s
`__version__` must match it exactly —
`tests/test_whitepact_alias.py::TestPublicApiIdentity::test_version_matches_package_metadata`
enforces this in CI, so the two can't silently drift the way
`__version__` once did (see `CHANGELOG.md`'s `[Unreleased]` "Fixed"
entry).

- **PATCH** (`1.2.x`): bug fixes, no API/behavior change a caller
  could observe.
- **MINOR** (`1.x.0`): new, additive functionality — a new endpoint, a
  new MCP tool, a new optional parameter with a backward-compatible
  default. Everything in this migration so far has been a MINOR-shaped
  change: additive, nothing removed, nothing renamed in place.
- **MAJOR** (`x.0.0`): a breaking change — removing a deprecated name,
  changing a default that alters behavior, dropping a Python version.
  `MIGRATION_WHITEPACT_V2.md` Section 11's backward-compatibility
  timeline is explicit that no MAJOR bump (the eventual removal of
  `responsibleai`/`RAI_*`/`rai://` names) is scheduled or committed to
  a date.

## Cutting a release

1. Update `pyproject.toml`'s `version`.
2. Update `src/responsibleai/__init__.py`'s `__version__` to match.
3. Move `CHANGELOG.md`'s `[Unreleased]` section to a new
   `## [X.Y.Z] — YYYY-MM-DD` heading (real date, not a placeholder).
   Leave a fresh empty `[Unreleased]` section above it for the next
   round of changes.
4. Open a PR with just those changes. Once merged to `main`:
5. Tag the merge commit and push the tag:
   ```bash
   git tag vX.Y.Z
   git push origin vX.Y.Z
   ```
6. Pushing a `v*` tag triggers `.github/workflows/publish.yml`, which:
   - Builds the wheel and sdist, verifies them with `twine check`.
   - Generates a CycloneDX SBOM from the actual built artifact's
     installed dependency closure (Phase 15).
   - Attests build provenance via Sigstore
     (`actions/attest-build-provenance`) — verifiable with
     `gh attestation verify <file> --owner Guruprasath-Annadurai`.
   - Publishes to PyPI via [trusted publishing](https://docs.pypi.org/trusted-publishers/)
     (OIDC — no long-lived API token stored as a secret).
   - Creates a GitHub Release for the tag, attaching the built
     artifacts and the SBOM, with auto-generated notes pointing back
     at the `CHANGELOG.md` entry.

## What this does *not* automate

Per the standing rule against fabricating implementation status:

- **No automatic version bumping.** Steps 1-3 above are manual, on
  purpose — deciding whether a change is PATCH/MINOR/MAJOR is a
  judgment call this repo doesn't try to infer from commit messages.
- **No automatic changelog generation from commits.** The `[Unreleased]`
  section is written by hand as changes land, not generated from `git
  log` at release time — a curated summary is more useful to a reader
  than every commit message, and this project's own commit messages are
  written for reviewers, not end users.
- **No Docker image publishing workflow.** `Dockerfile` exists and
  `docker-compose.prod.yml`/`helm/rai-governance/` reference an image
  (`ghcr.io/guruprasath-annadurai/responsibleai`), but there is no CI
  step that builds and pushes that image on a tag — a deployer builds
  it themselves from the tagged source today. Real gap, not an
  oversight; tracked separately.
- **No release-candidate/pre-release channel.** Every tag is treated as
  a stable release. If a pre-release channel is ever needed, it isn't
  designed here — this document doesn't accumulate unreviewed
  speculative process, same discipline `SPEC.md` holds itself to.
