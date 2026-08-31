# Verify a WhitePact release

These commands verify a release independently of the WhitePact publish job. Release
`v1.2.6` is the first release built and attested by
`.github/workflows/reusable-build.yml`; the commands below passed for its public wheel
and sdist on 2026-08-31. Earlier releases, including `v1.2.3`, were attested by
`.github/workflows/publish.yml` and therefore have a different signer-workflow identity.

Set the release version, download the public assets, and obtain the tagged source:

```bash
export WHITEPACT_VERSION=X.Y.Z
export WHITEPACT_REPO=Guruprasath-Annadurai/Whitepact
mkdir "whitepact-${WHITEPACT_VERSION}-verification"
cd "whitepact-${WHITEPACT_VERSION}-verification"
gh release download "v${WHITEPACT_VERSION}" --repo "$WHITEPACT_REPO"
git clone --filter=blob:none "https://github.com/${WHITEPACT_REPO}.git" source
git -C source fetch origin "refs/tags/v${WHITEPACT_VERSION}:refs/tags/v${WHITEPACT_VERSION}"
export WHITEPACT_COMMIT="$(git -C source rev-list -n 1 "v${WHITEPACT_VERSION}")"
```

## Verify SHA-256 digests

The trusted builder writes `SHA256SUMS` before uploading anything. The publish job
checks it before PyPI upload, and consumers can repeat the check:

```bash
sha256sum --check SHA256SUMS
sha256sum rai_governance_platform-*.whl rai_governance_platform-*.tar.gz
```

On macOS, install GNU coreutils and use `gsha256sum` in place of `sha256sum`.
The release page and PyPI should report the same wheel and sdist SHA-256 values.

## Verify wheel and sdist provenance

Verify each artifact against the expected repository, reusable builder, source
commit, signed tag ref, and GitHub-hosted runner:

```bash
for artifact in rai_governance_platform-*.whl rai_governance_platform-*.tar.gz; do
  gh attestation verify "$artifact" \
    --repo "$WHITEPACT_REPO" \
    --signer-workflow "$WHITEPACT_REPO/.github/workflows/reusable-build.yml" \
    --source-digest "$WHITEPACT_COMMIT" \
    --source-ref "refs/tags/v${WHITEPACT_VERSION}" \
    --deny-self-hosted-runners
done
```

Passing verification confirms that the artifact digest is in a signed GitHub/
Sigstore attestation issued for this repository, builder workflow, source commit,
tag ref, and hosted build environment. It does not replace tag-signature
verification.

Inspect the authenticated SLSA statement and confirm that both the wheel and
sdist appear as subjects:

```bash
gh attestation verify rai_governance_platform-*.whl \
  --repo "$WHITEPACT_REPO" \
  --signer-workflow "$WHITEPACT_REPO/.github/workflows/reusable-build.yml" \
  --source-digest "$WHITEPACT_COMMIT" \
  --source-ref "refs/tags/v${WHITEPACT_VERSION}" \
  --deny-self-hosted-runners \
  --format json \
  --jq '.[].verificationResult.statement | {subject, predicateType, predicate}'
```

The build-provenance predicate type must be `https://slsa.dev/provenance/v1`.

## Verify the portable provenance bundle

Starting with the first release produced after the portable-bundle control was
merged, the release also contains exactly one
`rai-governance-platform-*-provenance.sigstore` file. It is the unmodified bundle
output from GitHub's `actions/attest` step, is included in `SHA256SUMS`, and is
verified before PyPI publication. Releases without this asset, including v1.2.6,
must use the online verification above and must not be described as having the
portable bundle.

Verify the wheel and sdist offline against that release asset while retaining the
same repository, workflow, commit, tag, and runner identity constraints:

```bash
for artifact in rai_governance_platform-*.whl rai_governance_platform-*.tar.gz; do
  gh attestation verify "$artifact" \
    --bundle rai-governance-platform-*-provenance.sigstore \
    --repo "$WHITEPACT_REPO" \
    --signer-workflow "$WHITEPACT_REPO/.github/workflows/reusable-build.yml" \
    --source-digest "$WHITEPACT_COMMIT" \
    --source-ref "refs/tags/v${WHITEPACT_VERSION}" \
    --deny-self-hosted-runners
done
```

The `.sigstore` filename is a representation of the genuine GitHub/Sigstore
bundle, not a detached developer signature. It does not replace the independently
verified signed Git tag.

## Verify release intent: the signed Git tag

The repository allow-list, not a general SSH trust store, defines approved
release signers:

```bash
git -C source config gpg.format ssh
git -C source config gpg.ssh.allowedSignersFile \
  "$(pwd)/source/security/release-signers.allowed"
test "$(git -C source cat-file -t "v${WHITEPACT_VERSION}")" = tag
git -C source tag -v "v${WHITEPACT_VERSION}"
test "$(git -C source rev-list -n 1 "v${WHITEPACT_VERSION}")" = \
  "$WHITEPACT_COMMIT"
```

This proves an approved release signer authorized that exact source commit. The
provenance verification proves GitHub's reusable builder produced the downloaded
artifact from it. Both controls are required.

## Inspect and verify the CycloneDX SBOM

First verify that the attached document is the exact file hashed by the builder:

```bash
sha256sum --check SHA256SUMS
python -m json.tool sbom.cyclonedx.json >/dev/null
python - <<'PY'
import json
with open("sbom.cyclonedx.json", encoding="utf-8") as stream:
    sbom = json.load(stream)
assert sbom["bomFormat"] == "CycloneDX"
assert sbom["specVersion"] == "1.6"
assert sbom["serialNumber"].startswith("urn:uuid:")
assert isinstance(sbom.get("components"), list)
print(f"CycloneDX {sbom['specVersion']}: {len(sbom['components'])} components")
PY
```

If `cyclonedx-cli` is installed, also validate the document against the CycloneDX
schema:

```bash
cyclonedx-cli validate --input-file sbom.cyclonedx.json
```

The official GitHub attestation action binds the CycloneDX document to the wheel.
Verify and inspect that non-default predicate:

```bash
gh attestation verify rai_governance_platform-*.whl \
  --repo "$WHITEPACT_REPO" \
  --signer-workflow "$WHITEPACT_REPO/.github/workflows/reusable-build.yml" \
  --source-digest "$WHITEPACT_COMMIT" \
  --source-ref "refs/tags/v${WHITEPACT_VERSION}" \
  --predicate-type https://cyclonedx.org/bom \
  --deny-self-hosted-runners \
  --format json \
  --jq '.[0].verificationResult.statement.predicate' > attested-sbom.json
python - <<'PY'
import json
from pathlib import Path
attached = json.loads(Path("sbom.cyclonedx.json").read_text())
attested = json.loads(Path("attested-sbom.json").read_text())
assert attached == attested, "attached SBOM differs from authenticated predicate"
print("Attached CycloneDX SBOM exactly matches the authenticated predicate.")
PY
```

The SBOM describes the installed wheel dependency closure. It is not represented
as an attestation for the sdist, and the documentation intentionally makes no such
claim.

## Release acceptance rule

Do not describe a release as SLSA Build L3 unless all commands above pass against
the public, immutable release bytes and the attestation identifies
`.github/workflows/reusable-build.yml` as the signer workflow. Workflow code alone
is implementation evidence, not release verification.
