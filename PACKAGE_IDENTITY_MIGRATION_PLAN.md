# Package identity migration plan

Status: design only. No PyPI upload, no GHCR push, no name selection.

This plan does not choose the next public distribution name. `docs/PACKAGE_IDENTITY.md` remains the source of truth until the owner records a name.

## Current identity

| Surface | Current value | Notes |
| --- | --- | --- |
| Product | WhitePact | README, CLI help, dashboard |
| PyPI project | `rai-governance-platform` | `pyproject.toml` `project.name`, version `1.3.1` |
| Wheel / sdist | `rai_governance_platform-1.3.1-*` | Hatchling; packages `biasbuster`, `privacylabel`, `responsibleai`, `whitepact` |
| Canonical import | `responsibleai` | Unchanged by a distribution rename |
| Alias import | `whitepact` | Re-exports `responsibleai` from the same wheel |
| Other imports | `biasbuster`, `privacylabel` | Same wheel |
| Preferred CLI | `whitepact`, `whitepact-mcp`, `whitepact-mcp-http` | |
| Legacy CLI | `biasbuster`, `responsibleai` (bias CLI), `responsibleai-mcp`, `responsibleai-mcp-http` | `MIGRATION_WHITEPACT_V2.md` Section 4; no removal date |
| Python SDK | PyPI name `rai-client`, import `rai_client` | `sdk/python` |
| TypeScript SDK | npm `@responsibleai/client` | `sdk/typescript` |
| Go SDK | module path in `sdk/go/go.mod` | |
| Helm | chart `rai-governance`, image `ghcr.io/guruprasath-annadurai/responsibleai` | `RELEASING.md` says there is no CI push to that GHCR name |
| Trusted Publishing | `.github/workflows/publish.yml` environment `pypi`, project string `rai-governance-platform` | `pypa/gh-action-pypi-publish` |
| SBOM | CycloneDX 1.6 via `cyclonedx-py environment` in `reusable-build.yml` | |
| Attestation | `actions/attest` on the wheel, sdist, and SBOM subject | `docs/VERIFY_RELEASE.md` |
| Extras | Self-references such as `rai-governance-platform[dashboard]` | A rename must update these in the same release |

Live PyPI JSON read on 2026-10-07 (no upload):

| Name | Result |
| --- | --- |
| `rai-governance-platform` | Published. Latest version on PyPI is `1.2.6`. This repository's `pyproject.toml` is `1.3.1`, which is not what PyPI is serving. |
| `whitepact` | Not published |
| `whitepact-governance` | Not published |
| `whitepact-platform` | Not published |

Do not treat an available name as reserved. Availability can change, and some names may be too generic to claim.

A local wheel built under the throwaway name `whitepact-distribution-rehearsal-local` installed beside `rai-governance-platform` instead of replacing it. Both distributions owned overlapping import packages. A future shim must contain no packages of its own.

## Desired identity options

The owner must pick one. This document does not.

1. Keep `rai-governance-platform` as the only public distribution. Product name stays WhitePact. Lowest risk. Matches README and Trusted Publishing today.
2. Add a new PyPI project later, and keep `rai-governance-platform` as a one-cycle dependency shim that installs the new project. Requires a chosen name and a new Trusted Publisher.
3. Rename in place. PyPI does not allow a project rename that preserves the old URL. This option is rejected.

Candidate names to decide among, not to publish from this branch: `whitepact`, `whitepact-governance`, `whitepact-platform`. None is approved here.

## Compatibility strategy

- Imports stay `responsibleai`, `whitepact`, `biasbuster`, and `privacylabel` inside one wheel. Callers do not rewrite imports when only the distribution name changes.
- Console scripts stay as they are through the first renamed release. `whitepact` is the preferred CLI. `responsibleai` remains the bias CLI alias.
- Extras must use the new project name in that release's `pyproject.toml`. Old extras strings stop resolving after the shim is removed.
- Version stays `1.3.1` until a real release. An identity change, when approved, should be a new version (recommend `1.4.0`) so installers can pin.
- SDK packages stay separate. `rai-client` and `@responsibleai/client` do not have to move in the same release as the platform wheel.

## Deprecation path

1. Owner records the new PyPI name in `docs/PACKAGE_IDENTITY.md`.
2. Publish the new project at the next version. Do not delete `rai-governance-platform`.
3. Publish one `rai-governance-platform` release whose only dependency is the new project at the same version, and keep the old console scripts in that shim if both wheels would otherwise overwrite the same files. Two wheels must not both install `responsibleai/` into site-packages. The safe shim is a meta-package with no packages of its own.
4. README install commands gain the new name and keep the old command for one cycle, marked legacy.
5. After that cycle, stop publishing new versions of the shim. Leave the last shim version installable. Do not yank the last known-good `rai-governance-platform` release unless it is broken.

## CLI transition

| Command | Role after a rename |
| --- | --- |
| `whitepact` | Preferred. Keep. |
| `whitepact-mcp` / `whitepact-mcp-http` | Preferred MCP. Keep. |
| `biasbuster` | Legacy bias probes. Keep until a dated removal is written. |
| `responsibleai` | Legacy alias of `biasbuster`. Keep until that same dated removal. |
| `responsibleai-mcp` / `responsibleai-mcp-http` | Legacy MCP aliases. Keep for the same window. |

No new console script is added by this plan.

## Python import compatibility

`import responsibleai` and `import whitepact` must keep working from the new distribution. A local rehearsal that builds a throwaway project name must prove both imports resolve from that single wheel and that installing the throwaway wheel upgrades off `rai-governance-platform` instead of leaving two copies. See the rehearsal script.

## Wheel metadata changes (when a name is chosen)

- `project.name`
- `project.optional-dependencies` entries that say `rai-governance-platform[...]`
- README install blocks and the PyPI badge
- `publish.yml` project string and the PyPI trusted-publisher project
- Helm chart description only if the image name changes; chart id `rai-governance` can lag one release

Do not change `tool.hatch.build.targets.wheel.packages` for a distribution rename.

## SDK publication strategy

- Platform wheel and `rai-client` remain different projects.
- TypeScript stays `@responsibleai/client` until an npm name is chosen separately. This plan does not publish to npm.
- Go module path stays until a module-path move is planned. A module move breaks `go get` and is not part of the PyPI decision.

## GHCR naming strategy

Current documented image: `ghcr.io/guruprasath-annadurai/responsibleai`. There is no automated push in CI.

When container publish is approved later:

- Canonical image: `ghcr.io/guruprasath-annadurai/whitepact`
- Keep the `responsibleai` image name as a mirror tag for one cycle, or document a pull-through note in Helm values
- Do not push from this branch

## Trusted Publishing changes

`.github/workflows/publish.yml` is bound to `rai-governance-platform` and the GitHub environment `pypi`. A second project needs:

- a new PyPI project created by the owner
- a new trusted publisher for this repository and the existing tag workflow
- a workflow change that uploads only the owner-approved name
- the existing SHA-256 confirmation step pointed at that name

Until that exists, the workflow must keep publishing `rai-governance-platform` only.

## Rollback

- Do not delete or yank the previous `rai-governance-platform` files as part of a rename.
- If the new project is bad, installers pin the last good `rai-governance-platform` version.
- GitHub Release assets stay attached to the tag that built them. A bad release is followed by a new patch tag, not by rewriting the old tag.
- Attestations stay on the bytes that were published. Do not rebuild different bytes under the same version.

## Release validation

Before any future publish:

1. `scripts/package/rehearse_distribution.py` on the release commit (fresh venv, upgrade, imports, extras, CLI, rebuild hash, SBOM, SHA256SUMS).
2. `reusable-build.yml` reproducibility check (two builds, identical wheel and sdist).
3. CycloneDX SBOM generated from the releasable wheel's environment.
4. `actions/attest` on wheel, sdist, and SBOM.
5. Trusted Publishing upload of those exact bytes.
6. PyPI digest check already in `publish.yml`.
7. `docs/VERIFY_RELEASE.md` commands against the release assets.

This branch runs step 1 locally only.
