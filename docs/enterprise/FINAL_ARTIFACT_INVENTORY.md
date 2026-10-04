# Final artifact inventory (engineering)

| Artifact | Location / SHA | Notes |
|----------|----------------|-------|
| Frozen M4 candidate | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | **Do not mutate** during Antigravity audit |
| M4 tree | `2c0447e733b3d96dea1feaf0144f5ec3aa43b8b4` | |
| M4 CI (18/18) | Run `37149277919` | On gate tip lineage; see `M4_EXACT_HEAD_CI_EVIDENCE.md` |
| Qualified M3 | `620399b7973f5ed058d45218610be228e72d3ed8` | |
| M5 integrated RC | `ecea2b4a99c9e0574f30629ce8acafca237a0d6f` | CI `37194273812` 18/18 |
| Qualified M4 | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | Antigravity PASS |
| Python wheel | CI `Build distribution` job | Not published to PyPI |
| Frontend bundle | CI `Frontend closure` job | |
| Helm chart | CI `Helm chart lint` | |
| Terraform | `infra/terraform/**` | Validate only |
| SBOM / provenance | CI OpenSSF / Reproducible Build workflows | See workflow artifacts |
| Antigravity M4 report | *(pending)* | Record URL + SHA when received |

Update this table when M5 RC is frozen.
