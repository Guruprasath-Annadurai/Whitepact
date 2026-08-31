# Signed Version Tags — Audit and Status

Last reviewed: 2026-08-31 · For the OpenSSF Best Practices `version_tags_signed` criterion.

## What this document is about — and what it isn't

This covers signing the **Git version tag object itself** — the thing
`git tag -v vX.Y.Z` verifies. It is a separate control from **artifact
attestation** (Sigstore/GitHub `actions/attest-build-provenance`,
already in place — see `.github/workflows/publish.yml` and
`SECURITY_ASSURANCE_CASE.md` §2.21), and the two prove different
things:

| | Proves | Verified with |
|---|---|---|
| Artifact attestation (already implemented) | This wheel/sdist was built by this repo's own GitHub Actions workflow, from this exact commit, unmodified since | `gh attestation verify <file> --repo Guruprasath-Annadurai/Whitepact` (new reusable-builder releases add `--signer-workflow`; see `docs/VERIFY_RELEASE.md`) |
| Signed Git tag (**verified for `v1.2.3` and `v1.2.6`; required for every future release**) | A trusted human (the founder, or an approved release maintainer) actually authorized cutting this release at this commit | `git tag -v vX.Y.Z` |

A signed build pipeline that runs automatically on *any* pushed tag
does not, by itself, prove a human intended to cut that release — it
proves the pipeline is trustworthy once triggered. Signed tags are the
control that gates *triggering* it to only trusted humans.

## 1. Audit method

```bash
git tag                              # enumerate all tags
git cat-file -t <tag>                # "commit" = lightweight tag; "tag" = annotated tag object
git show <tag> --no-patch            # for annotated tags: tagger identity, message, embedded signature if present
git tag -v <tag>                     # attempts signature verification; fails/no-op if unsigned
```

`git cat-file -t` is the authoritative check for annotated-vs-lightweight
— GitHub's release UI can show tagger/date information even for a
lightweight tag (reconstructed from the pointed-to commit), so the
release page alone is not evidence of an annotated, let alone signed,
tag. This audit used the raw Git object model, not the GitHub UI.

## 2. Historical audit results — the 9 pre-policy tags

| Tag | Object type | Annotated | Signed | `git tag -v` result |
|---|---|---|---|---|
| `v0.6.0` | `commit` | No (lightweight) | No | N/A — lightweight tags carry no signature |
| `v0.7.0` | `commit` | No (lightweight) | No | N/A |
| `v0.8.0` | `commit` | No (lightweight) | No | N/A |
| `v0.9.0` | `commit` | No (lightweight) | No | N/A |
| `v1.0.0` | `commit` | No (lightweight) | No | N/A |
| `v1.1.0` | `tag` | **Yes** | **No** | No signature block in `git show v1.1.0` output; `git tag -v` reports no embedded signature to check |
| `v1.2.0` | `tag` | **Yes** | **No** | Same as above |
| `v1.2.1` | `commit` | No (lightweight) | No | N/A |
| `v1.2.2` | `commit` | No (lightweight) | No | N/A |

**Summary**: 7 of 9 tags are lightweight (no tag object at all, hence
nothing to sign). The 2 annotated tags (`v1.1.0`, `v1.2.0`) carry a
tagger identity and message but no cryptographic signature. **Zero of
9 existing release tags are signed.**

**Root cause**: `RELEASING.md`'s documented release procedure, prior to
this review, instructed `git tag vX.Y.Z` — which creates a lightweight
tag unless `-a`/`-s` is explicitly passed. This was a real,
undocumented gap in the release process itself, not an inconsistently
followed policy — there was no policy requiring annotated or signed
tags until this review. `RELEASING.md` has been updated (see below) to
require `-s` (annotated + signed) for every release going forward.

## 3. Existing tags — not rewritten

Per this task's own instruction and standard practice: **historical,
already-published tags are not force-moved or rewritten.** Doing so
would break reproducibility for anyone who has already fetched, built
from, or referenced these tags (PyPI packages built from them are
already published and immutable regardless of what the Git tag becomes).
The 9 tags above remain exactly as they are, documented here honestly
as unsigned, rather than silently rewritten to appear compliant.

The policy in `RELEASING.md` applies to every **new** release going
forward.

## 4. Current status

- **Signing mechanism**: **configured, 2026-08-19.** A dedicated
  ed25519 SSH signing key was generated on the founder's own machine
  (`ssh-keygen -t ed25519 -f ~/.ssh/whitepact_release_signing`, never
  transmitted anywhere) and Git configured globally to use it
  (`gpg.format=ssh`, `user.signingkey`, `tag.gpgSign=true` — see
  `RELEASING.md` "Signing releases"). The private key never leaves
  `~/.ssh/` on the founder's machine; it is not in this repository, not
  in any CI secret, and not logged anywhere.
- **`security/release-signers.allowed`**: populated with the
  corresponding **public** key
  (`milchcreamfoods@gmail.com ssh-ed25519 AAAA...`). End-to-end
  verification was run locally before this line was committed: a real
  tag signed with the private key, verified with `git tag -v` against
  this exact file, in a throwaway test repository — confirmed
  `Good "git" signature for milchcreamfoods@gmail.com`.
- **Release workflow gate**: `verify-signed-tag` job in
  `.github/workflows/publish.yml`, tested against all 5 required
  scenarios (signed-approved/unsigned/lightweight/tampered/unapproved-
  signer) with throwaway keys before this feature was committed — see
  the PR that introduced it for the transcript.

## 5. `v1.2.3` — the first genuinely signed release tag

Cut and pushed 2026-08-19 with the newly-configured key. The first
attempt caught a real bug in the verification job itself
(`actions/checkout` resolved the tag-push trigger to its dereferenced
commit SHA, making a genuinely signed, annotated tag look lightweight
to `git cat-file -t` in CI — see the fix commit for detail); no
artifact was published under that first attempt, the tag was deleted
and re-cut cleanly after the fix landed. The second attempt's
`verify-signed-tag` job passed for real:

- Tag object type: `tag` (annotated)
- Signature: valid SSH signature from
  `milchcreamfoods@gmail.com`'s key, verified against
  `security/release-signers.allowed`
- Result: `Good "git" signature for milchcreamfoods@gmail.com`
- Release: <https://github.com/Guruprasath-Annadurai/Whitepact/releases/tag/v1.2.3>,
  build provenance and SBOM attached, published to PyPI via Trusted
  Publishing

`version_tags_signed` is genuinely **MET** as of this release. Every
release from this point forward uses the same `git tag -s` procedure
(`RELEASING.md` "Cutting a signed tag"), gated by the same CI check.

## 6. `v1.2.6` — current hardened release evidence

The annotated `v1.2.6` tag points to
`f784c44819c9c26f4e3486a9a6331508e20fd1eb`. On 2026-08-31, `git tag -v v1.2.6`
reported a good SSH signature for `milchcreamfoods@gmail.com` against
`security/release-signers.allowed`. Publish run `33337718757` independently passed the
same signed-tag and approved-signer gate before invoking the reusable trusted builder.

## 7. Revisiting this document

Update the audit table above whenever a new tag is cut — this is a
point-in-time snapshot (2026-08-19), not a live query. Re-run Section 1's
commands to refresh it.
