# Supply-chain security evidence

Verified 2026-10-11 by running the commands below; none of it is independent verification and none of it is a SLSA
level claim.

## 1. Released artifacts (v1.2.6, the latest published release)

| Check | Command (from `docs/VERIFY_RELEASE.md`) | Result |
| --- | --- | --- |
| Download | `gh release download v1.2.6 --repo Guruprasath-Annadurai/Whitepact` | wheel, sdist, `SHA256SUMS`, `sbom.cyclonedx.json` |
| Digests | `shasum -a 256 -c SHA256SUMS` | wheel OK, sdist OK, SBOM OK |
| Provenance | `gh attestation verify <artifact> --repo … --signer-workflow …/reusable-build.yml --source-digest f784c44819c9c26f4e3486a9a6331508e20fd1eb --source-ref refs/tags/v1.2.6 --deny-self-hosted-runners` | exit 0 for wheel and sdist; predicate type `https://slsa.dev/provenance/v1` |
| Negative control | same with source digest `000…0` | **refused** ("expected SourceRepositoryDigest …") |
| SBOM attestation | `gh attestation verify <wheel> --predicate-type https://cyclonedx.org/bom` | CycloneDX **1.6**, **43** components, identical to the attached file |
| Tag | annotated tag object → commit `f784c448…` (signature check per `VERIFY_RELEASE.md` requires the allowed-signers file; not repeated here) | resolved |

What this shows: the published bytes were produced by the named builder workflow from that commit on a GitHub-hosted
runner, and an SBOM was attested. What it does not show: that the source is free of defects, that the builder
workflow itself is trustworthy (it is in the same repository), that a second party reviewed the release, or any SLSA
level. PyPI publishing uses `pypa/gh-action-pypi-publish` without a stored token (trusted publishing).

## 2. Dependency vulnerabilities (OSV query of `uv.lock`, 209 locked registry packages)

| Ref | Packages with advisories | Advisories |
| --- | --- | --- |
| `main` (`38f92722`) | 4: PyJWT 2.13.0, mako 1.4.1, multidict 6.7.1, nltk 3.10.3 | 31 |
| this branch before this pass | 3: mako, multidict, nltk | 3 |
| this branch now | **1: nltk 3.10.3** | 1 (GHSA-8mgp-746c-j5xp, **no patched release**; optional `[sentiment]` extra only; `WHITEPACT_VEX.openvex.json`) |

CI additionally runs pip-audit against the installed environment, `npm audit`, dependency-review, gitleaks, CodeQL,
Bandit and the OpenSSF policy guard; these were green on earlier heads (see the PR for the exact head).

## 3. Controls present in the repository

Hash-attested builds and SBOM (above); signed-tag allow-list (`security/release-signers.allowed`); reusable trusted
builder; actions pinned by SHA; workflow `permissions:` declared; CI service images pinned by digest (3, this pass);
`Dockerfile.isolation` base pinned by digest; reproducible-build job ("Rebuild artifacts identically"); DCO check;
license-header check.

## 4. Gaps

Hash-pinned installs for build tooling (`pip install build`, `npm` tooling) remain unpinned (Scorecard
Pinned-Dependencies 5); no fuzzing; no Scorecard-recognised signed-release assets (the attestations are a different
mechanism); container image vulnerability scanning of `Dockerfile.isolation` and the application image is not part of
CI (NOT DONE); no VEX beyond NLTK; no independent reproduction of the build by a second party.
