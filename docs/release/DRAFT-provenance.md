# Provenance plan (DRAFT)

Do **not** claim SLSA level without meeting requirements.

Record at final release:

- Source repository URL + exact commit SHA
- Branch/tag name
- Build environment (CI job id / image digest)
- Artifact names + SHA-256 digests
- Toolchain versions (Python, hatchling)
- Links to test evidence artifacts
- SBOM + OpenVEX paths

Existing workflows to align: `.github/workflows/publish.yml`, `reproducible-build.yml`.
