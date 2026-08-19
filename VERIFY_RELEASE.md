# Verifying a WhitePact Release

A published release carries two separate, independently verifiable
properties. Neither substitutes for the other — see
`compliance/SIGNED_VERSION_TAGS.md` for why they're distinct controls.

## A. The Git version tag was signed by an approved release signer

Proves: a trusted human (the founder, or another approved release
maintainer) actually authorized cutting this release at this commit.

```bash
git fetch --tags
git config gpg.format ssh
git config gpg.ssh.allowedSignersFile /path/to/release-signers.allowed
git tag -v vX.Y.Z
```

Use the repository's own
[`security/release-signers.allowed`](security/release-signers.allowed)
as the allowed-signers file (fetch it from the tagged commit, not an
arbitrary branch, so you're checking against the signer list that was
current *at that release*).

A successful verification prints the signer's identity and confirms
the signature is valid. If this fails — or if the tag turns out to be
lightweight (`git cat-file -t vX.Y.Z` prints `commit`, not `tag`) — do
not trust the release as human-authorized, regardless of what PyPI or
the GitHub Releases page shows.

## B. The build artifact has provenance from this repository's CI

Proves: the specific wheel/sdist you downloaded was built by this
repository's own GitHub Actions workflow, from a specific commit,
unmodified since — via Sigstore-backed GitHub Artifact Attestations.

```bash
gh attestation verify path/to/downloaded/whitepact-X.Y.Z-py3-none-any.whl \
  --owner Guruprasath-Annadurai
```

This does **not** prove a human decided to cut this release — only
that whatever triggered the build pipeline produced this exact,
untampered artifact. Check (A) for the human-authorization property.

## Why both, not just one

A compromised or careless CI configuration could in principle build and
attest a release nobody meant to cut, if triggering the pipeline were
the only gate — check (A) is what stops that. Conversely, a signed tag
alone doesn't tell you the artifact you downloaded from PyPI actually
matches what was built from that tag rather than being substituted in
transit or via a compromised PyPI account — check (B) is what stops
that. Verifying only one leaves the other threat uncovered.
