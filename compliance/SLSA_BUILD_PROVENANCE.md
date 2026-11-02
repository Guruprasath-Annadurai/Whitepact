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
- **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** — present and locally validated in
  workflow code, but no public release has yet traversed that implementation.
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
| `v1.2.3` wheel and sdist have signed SLSA provenance | **VERIFIED** | `gh attestation verify` passed on 2026-08-30 for both GitHub Release assets. Predicate: `https://slsa.dev/provenance/v1`; source commit: `c53562281df07f657d8bdcdb387b40d66d4e4c48`; signer workflow: `.github/workflows/publish.yml@refs/tags/v1.2.3`; GitHub-hosted runner. |
| `v1.2.3` artifact digest integrity | **VERIFIED** | Wheel SHA-256 `1286d5c36b7fdc39e365b327eb714224983145fa2761d516443b8c217d213d00`; sdist SHA-256 `06cca485080d29d38d3da5feaf4fb63e64ee5cc9bd14bac6d53ee1398b07c6e6`. Both are authenticated attestation subjects. |
| `v1.2.3` release-intent signature | **VERIFIED** | Annotated tag `v1.2.3` verifies as a good SSH signature for `milchcreamfoods@gmail.com` against `security/release-signers.allowed`. |
| Current released evidence supports SLSA Build L2 | **VERIFIED** | `v1.2.3` provenance is authenticated, service-generated on a hosted build platform, identifies artifact digests and source, and is independently consumable. This is a release-specific L2 conclusion, not an L3 conclusion. |
| Reusable workflow exclusively creates release wheel and sdist | **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** | `.github/workflows/reusable-build.yml` owns both builds, byte-for-byte reproducibility comparison, provenance, SBOM attestation, checksums, and the single artifact upload. `.github/workflows/publish.yml` calls it and contains no build command. |
| Trusted-builder least-privilege permissions | **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** | Caller and reusable workflow grant only `contents: read`, `id-token: write`, and `attestations: write`; no publishing environment or secrets cross the boundary. External actions in the modified release workflows are pinned to immutable commits. |
| Exact attested bytes reach PyPI and GitHub Release | **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** | Publish downloads `release-bundle`, checks builder `SHA256SUMS`, verifies both provenance statements with repository/builder/source/ref/runner constraints, uploads the bundle's distributions without rebuilding, checks PyPI JSON SHA-256 values, then attaches the same files to the GitHub Release. |
| CycloneDX SBOM attestation | **IMPLEMENTED BUT NOT YET RELEASE-VERIFIED** | Official `actions/attest` SBOM mode binds `sbom.cyclonedx.json` to the wheel using predicate type `https://cyclonedx.org/bom`. No sdist SBOM-attestation claim is made. |
| New hardened release has executed successfully | **NOT SATISFIED** | No new signed version tag has run the reusable workflow yet. Workflow implementation and local tests cannot satisfy this release-evidence gate. |
| New wheel and sdist independently verify against the reusable signer workflow | **NOT SATISFIED** | Required acceptance command is `gh attestation verify ... --signer-workflow Guruprasath-Annadurai/Whitepact/.github/workflows/reusable-build.yml`, with expected source digest/ref and hosted-runner enforcement, against downloaded public release assets. |
| Public SLSA Build L3 claim | **NOT SATISFIED** | Blocked until the two preceding rows pass for a real release and the exact PyPI/GitHub Release hashes match the builder manifest. |
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

After this hardening, the signed-tag gate authorizes release intent; a reusable,
least-privilege workflow builds, reproduces, hashes, and attests; and a separate
publish job can only download, verify, and distribute the resulting bundle. OIDC
identities remain short-lived. No PyPI API token or signing private key exists in
the workflow.

## Claim rule

WhitePact may state that the existing `v1.2.3` release has independently verified
SLSA Build L2-compatible provenance. It must not state that WhitePact currently
has a Build L3 release. After a new signed version tag completes the hardened
workflow, a reviewer must download the public wheel and sdist and run every
release-acceptance check in `docs/VERIFY_RELEASE.md`. Only that successful,
recorded verification closes the Build L3 evidence gate.
