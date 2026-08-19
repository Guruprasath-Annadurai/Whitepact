# Signed Version Tags — Audit and Status

Last reviewed: 2026-08-19 · For the OpenSSF Best Practices `version_tags_signed` criterion.

## What this document is about — and what it isn't

This covers signing the **Git version tag object itself** — the thing
`git tag -v vX.Y.Z` verifies. It is a separate control from **artifact
attestation** (Sigstore/GitHub `actions/attest-build-provenance`,
already in place — see `.github/workflows/publish.yml` and
`SECURITY_ASSURANCE_CASE.md` §2.21), and the two prove different
things:

| | Proves | Verified with |
|---|---|---|
| Artifact attestation (already implemented) | This wheel/sdist was built by this repo's own GitHub Actions workflow, from this exact commit, unmodified since | `gh attestation verify <file> --owner Guruprasath-Annadurai` |
| Signed Git tag (**not yet implemented** — this document) | A trusted human (the founder, or an approved release maintainer) actually authorized cutting this release at this commit | `git tag -v vX.Y.Z` |

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

## 2. Audit results — all 9 existing tags

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

- **Signing mechanism**: not yet configured on this machine/for this
  founder. `git config --get gpg.format` and `git config --get
  user.signingkey` are both unset; no SSH public keys exist under
  `~/.ssh/*.pub`; no GPG secret keys are present (`gpg --list-secret-keys`
  returns nothing). This was checked directly, not assumed.
- **`security/release-signers.allowed`**: created as a placeholder with
  the correct file format documented, containing **no key material** —
  see that file's own header. Populating it with a real public key is
  a founder action (Section 6 below).
- **Release workflow gate**: added to `.github/workflows/publish.yml`
  (a `verify-signed-tag` job that every other job now depends on) —
  see `RELEASING.md` "Signing releases" for what it checks and why it
  fails closed (rejects every tag, signed or not) until a real signer
  is configured in `security/release-signers.allowed`. This is
  intentional: an unconfigured allowed-signers file must not silently
  accept an unsigned/unverifiable tag just because no policy violation
  was detected — "no signer configured" is itself a failure state.

## 5. What is required before the next release

**FOUNDER ACTION REQUIRED**: generate an SSH signing key (or use an
existing one, if the founder already has one for another purpose — a
dedicated release-signing key is preferable but not required) and:

1. Follow `RELEASING.md`'s "One-time setup: SSH tag signing" section.
2. Add the resulting **public** key to `security/release-signers.allowed`.
3. Commit that file (public key only — never the private key) and push.
4. Cut the next release using `git tag -s` per the updated procedure.

Until that happens, `version_tags_signed` remains **NOT MET** — this
document does not claim otherwise. See `SECURITY_ASSURANCE_CASE.md`
§2.21 for how this gap is reflected there.

## 6. Revisiting this document

Update the audit table above whenever a new tag is cut — this is a
point-in-time snapshot (2026-08-19), not a live query. Re-run Section 1's
commands to refresh it.
