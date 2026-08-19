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
5. Tag the merge commit with an **annotated, signed** tag and push it:
   ```bash
   git tag -s vX.Y.Z -m "WhitePact vX.Y.Z"
   git tag -v vX.Y.Z          # confirm it verifies locally before pushing
   git push origin vX.Y.Z
   ```
   **Never use `git tag vX.Y.Z` (no `-s`) for a release** — that
   creates an unsigned lightweight tag, which
   `.github/workflows/publish.yml`'s `verify-signed-tag` job now
   rejects before anything builds or publishes. See "Signing releases"
   below for the one-time setup this requires, and
   `compliance/SIGNED_VERSION_TAGS.md` for why this is a distinct
   control from the build-provenance attestation in step 6.
6. Pushing a `v*` tag triggers `.github/workflows/publish.yml`, which:
   - **First verifies the tag itself is annotated, signed, and signed
     by an approved release signer** (`verify-signed-tag` job) —
     nothing below this point runs for a lightweight, unsigned, or
     unapproved-signer tag.
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

## Signing releases

Every important release tag (major, minor, and public security-fix
releases) must be an **annotated, cryptographically signed** Git tag —
enforced by `.github/workflows/publish.yml`'s `verify-signed-tag` job,
which runs before anything is built or published and fails closed on a
lightweight tag, a missing signature, an invalid signature, or a
signature from a key not on the approved-signers list. See
`compliance/SIGNED_VERSION_TAGS.md` for the audit of existing tags (all
unsigned, from before this policy existed — not rewritten, see that
document for why) and current status.

### One-time setup: SSH tag signing

Git supports signing tags with an SSH key (`gpg.format=ssh`), not just
GPG — this is the preferred method here because it reuses a key type
most maintainers already have for Git/GitHub access, with no separate
GPG keyring to manage. If you already have an established, secure GPG
signing setup instead, that's also acceptable — the verification job
supports either; adjust the `git config gpg.format` step accordingly if
you use GPG.

```bash
# If you don't already have an SSH key you want to dedicate to signing,
# generate one (ed25519, not RSA -- shorter, and the modern default):
ssh-keygen -t ed25519 -C "release-signing" -f ~/.ssh/whitepact_release_signing

# Tell Git to sign with SSH, using this key, and to sign tags by default:
git config --global gpg.format ssh
git config --global user.signingkey ~/.ssh/whitepact_release_signing.pub
git config --global tag.gpgSign true
```

Then add the **public** key (`~/.ssh/whitepact_release_signing.pub`'s
contents — never the private key) as a line in
[`security/release-signers.allowed`](security/release-signers.allowed),
in the format that file's own header documents, and open a PR. The
`verify-signed-tag` job reads this file to decide who counts as an
approved release signer — a tag signed by a key not listed there fails
the gate exactly like an unsigned one.

### Cutting a signed tag

```bash
git tag -s vX.Y.Z -m "WhitePact vX.Y.Z"
git tag -v vX.Y.Z      # verify locally before pushing
git push origin vX.Y.Z
```

**Never `git tag vX.Y.Z` without `-s` for a release** — see "Cutting a
release" step 5 above.

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
