# Supply-chain evidence index (M6)

| Control | CI / repo evidence |
|---------|-------------------|
| Dependency Review | GitHub `Dependency Review` workflow on PRs |
| CodeQL | `CodeQL` workflow |
| Gitleaks | `Gitleaks` workflow |
| OpenSSF Policy Guard | `OpenSSF Policy Guard` workflow |
| Reproducible Build | `Reproducible Build` workflow |
| DCO | `DCO` check on commits |
| Helm | `Helm chart lint` job |
| Terraform locks | `infra/terraform/**` provider constraints |
| Container scanning | Document in CI when image build job present |

Gaps: record SBOM/provenance artifact URLs per release SHA in `FINAL_ARTIFACT_INVENTORY.md` when M5 RC freezes.
