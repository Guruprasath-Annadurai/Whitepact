# SLSA Build provenance evidence boundary

Last reviewed: 2026-08-30  
Normative model: [SLSA v1.2 Build Track](https://slsa.dev/spec/v1.2/)  
Repository: `Guruprasath-Annadurai/Whitepact`

The reusable-builder design follows GitHub's official guidance for
[increasing an artifact's build security rating](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/increase-security-rating).

This is an evidence register, not a certification or a blanket security claim.
The allowed status values are:

- **VERIFIED** — checked against a real released artifact or immutable repository
  evidence.
- **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** — present and locally validated for a
  control whose release-specific execution evidence has not yet been recorded.
- **NOT SATISFIED** — required evidence does not exist or has not passed.
- **NOT APPLICABLE** — outside the assessed SLSA v1.2 Build Track boundary.

The machine-readable companion is `compliance/SLSA_BUILD_PROVENANCE.json`.

## Assessed boundary

The assessed products are WhitePact's Python wheel and sdist. The source is the
commit referenced by an approved-signer, annotated Git release tag. The build
platform is a GitHub-hosted Actions runner. The intended trusted builder is
`.github/workflows/reusable-build.yml`. PyPI upload and GitHub Release creation
are distribution steps in `.github/workflows/publish.yml`; they do not build or
attest artifacts.

The CycloneDX SBOM and `SHA256SUMS` are supporting release evidence. The wheel and
sdist are the SLSA build subjects.

## Evidence register

| Control / assertion | Status | Evidence and boundary |
|---|---|---|
| `v1.2.6` wheel and sdist have signed SLSA provenance | **VERIFIED** | `gh attestation verify` passed on 2026-08-31 for both downloaded GitHub Release assets. Predicate: `https://slsa.dev/provenance/v1`; source commit: `f784c44819c9c26f4e3486a9a6331508e20fd1eb`; signer workflow: `.github/workflows/reusable-build.yml@refs/tags/v1.2.6`; GitHub-hosted runner; Rekor timestamp verified. |
| `v1.2.6` artifact digest integrity | **VERIFIED** | Wheel SHA-256 `aef728a0227c115537aee7f434aa2c28d744f15cca78822eb1df339f106d3ad7`; sdist SHA-256 `289c37a2ecd36f989530674f5b483362b81b14ff277fc9d6b6373d5fa4155bd3`. `SHA256SUMS`, GitHub release digests, attestation subjects and PyPI JSON agree. |
| `v1.2.6` release-intent signature | **VERIFIED** | Annotated tag `v1.2.6` verifies as a good SSH signature for `milchcreamfoods@gmail.com` against `security/release-signers.allowed`; the release job's signer gate also passed. |
| `v1.2.6` released evidence satisfies SLSA v1.2 Build L3 | **VERIFIED** | The producer uses a consistent, documented process and distributes provenance. GitHub-hosted Actions provides hosted, ephemeral isolation and platform-controlled keyless signing; the SLSA v1 predicate identifies both subjects, builder, invocation, source and external parameters. GitHub's official reusable-workflow/artifact-attestation model is the selected L3-capable builder pattern. This is a release-specific conformance assessment, not certification. |
| Reusable workflow exclusively creates release wheel and sdist | **VERIFIED** | `.github/workflows/reusable-build.yml` built both v1.2.6 distributions, compared a second build byte-for-byte, generated provenance/SBOM/checksums, and uploaded once. `.github/workflows/publish.yml` did not rebuild. Run `33337718757` passed. |
| Trusted-builder least-privilege permissions | **VERIFIED** | Caller and reusable workflow grant only `contents: read`, `id-token: write`, and `attestations: write`; no publishing environment or long-lived secret crosses the boundary. The successful signer identity records a GitHub-hosted runner. |
| Exact attested bytes reached PyPI and GitHub Release | **VERIFIED** | Publish checked `SHA256SUMS`, verified provenance, copied only the two distributions, published without rebuilding, confirmed PyPI SHA-256 values, and created the GitHub Release from the same bundle. Independent comparison repeated on 2026-08-31. |
| CycloneDX SBOM attestation | **VERIFIED** | v1.2.6 includes `sbom.cyclonedx.json` (SHA-256 `a678fe2650f805baa8e9d2dd554a4e0bef701525d28ffc1335d9936785ae5c3f`) and an SBOM attestation bound to the wheel with predicate type `https://cyclonedx.org/bom`. No sdist SBOM-attestation claim is made. |
| Hardened release executed successfully | **VERIFIED** | Publish run `33337718757` completed signed-tag verification, reusable build/reproduction/attestation, publish verification, exact-byte PyPI publication, hash confirmation and GitHub Release creation. |
| Wheel and sdist independently verify against the reusable signer workflow | **VERIFIED** | Consumer commands in `docs/VERIFY_RELEASE.md` passed on 2026-08-31 with repository, signer workflow, source digest, tag ref and hosted-runner constraints. |
| Scoped public SLSA Build L3 statement for v1.2.6 | **VERIFIED** | Allowed wording is limited to the assessed v1.2.6 wheel/sdist and must remain qualified as conformance evidence, not certification or proof of artifact security. |
| SLSA Source Track assessment | **NOT APPLICABLE** | This assessment is limited to the SLSA v1.2 Build Track. Source Track conformance is a separate assessment. |
| Obsolete pre-v1.0 Build Level 4 terminology | **NOT APPLICABLE** | SLSA v1.2 Build Track ends at Build L3. No Build L4 claim is used. |

## Architecture change

Before this hardening, one `publish` job in `.github/workflows/publish.yml`
checked out source, built the wheel/sdist, generated an SBOM, generated
provenance, published to PyPI, and created a GitHub Release. Its top-level token
also granted write permissions across jobs. The artifacts had valid GitHub
provenance, but the architecture lacked the reusable trusted-builder isolation
required for an L3 claim. The audit also found no executable release build-twice
byte comparison, despite prior documentation treating reproducibility as an
existing control; that check is newly implemented here rather than credited as
historical evidence.

In the current architecture, the signed-tag gate authorizes release intent; a reusable,
least-privilege workflow builds, reproduces, hashes, and attests; and a separate
publish job can only download, verify, and distribute the resulting bundle. OIDC
identities remain short-lived. No PyPI API token or signing private key exists in
the workflow. Release `v1.2.6` exercised this architecture successfully.

## Claim rule

WhitePact may state that the assessed `v1.2.6` wheel and sdist have release-specific
evidence satisfying SLSA v1.2 Build L3 requirements. It must not say “SLSA certified,”
apply the statement to unassessed releases, or imply that provenance proves absence of
vulnerabilities. Each future release needs fresh signed-tag, workflow, artifact, digest,
attestation and consumer-verification evidence before receiving the same statement.
