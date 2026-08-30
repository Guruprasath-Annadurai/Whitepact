"""Regression guards for the SLSA release trust boundary.

These tests intentionally inspect workflow source as policy. GitHub validates the
YAML separately with actionlint; these checks prevent a syntactically valid edit
from silently collapsing the reusable-builder or exact-byte guarantees.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_PATH = ROOT / ".github" / "workflows" / "publish.yml"
BUILDER_PATH = ROOT / ".github" / "workflows" / "reusable-build.yml"
PUBLISH = PUBLISH_PATH.read_text(encoding="utf-8")
BUILDER = BUILDER_PATH.read_text(encoding="utf-8")


def _step_order(document: str, *needles: str) -> list[int]:
    return [document.index(needle) for needle in needles]


def test_release_workflows_are_valid_yaml_documents() -> None:
    for path in (PUBLISH_PATH, BUILDER_PATH):
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        assert isinstance(workflow, dict)
        assert "on" in workflow
        assert "jobs" in workflow


def test_publish_calls_local_reusable_builder_after_signed_tag_gate() -> None:
    assert "uses: ./.github/workflows/reusable-build.yml" in PUBLISH
    assert "needs: verify-signed-tag" in PUBLISH
    assert _step_order(
        PUBLISH,
        "verify-signed-tag:",
        "build:",
        "publish:",
    ) == sorted(_step_order(PUBLISH, "verify-signed-tag:", "build:", "publish:"))


def test_publish_never_rebuilds_or_creates_provenance() -> None:
    forbidden = (
        "python -m build",
        "hatch build",
        "poetry build",
        "attest-build-provenance",
        "actions/attest@",
        "actions/upload-artifact@",
    )
    for token in forbidden:
        assert token not in PUBLISH


def test_builder_owns_both_distributions_and_reproducibility_check() -> None:
    assert 'PRIMARY_DIR="${RUNNER_TEMP}/whitepact-release-bundle"' in BUILDER
    assert 'REPRO_DIR="${RUNNER_TEMP}/whitepact-reproducibility-check"' in BUILDER

    assert 'python -m build --outdir "${PRIMARY_DIR}"' in BUILDER
    assert 'python -m build --outdir "${REPRO_DIR}"' in BUILDER

    assert 'primary_names="$(find "${PRIMARY_DIR}"' in BUILDER
    assert 'reproduced_names="$(find "${REPRO_DIR}"' in BUILDER

    assert (
        'cmp --silent "${PRIMARY_DIR}/${artifact}" "${REPRO_DIR}/${artifact}"'
        in BUILDER
    )
    assert (
        'sha256sum "${PRIMARY_DIR}/${artifact}" "${REPRO_DIR}/${artifact}"'
        in BUILDER
    )

    # The source checkout must remain unchanged while both builds are produced.
    assert "python -m build --outdir release-bundle" not in BUILDER
    assert "python -m build --outdir reproducibility-check" not in BUILDER
    assert 'cmp --silent "release-bundle/${artifact}"' not in BUILDER

    # Only the already-verified primary artifacts are exposed for the
    # downstream SBOM, digest, attestation, and publication steps.
    copy_index = BUILDER.index('cp "${PRIMARY_DIR}"/* release-bundle/')
    compare_index = BUILDER.index(
        'cmp --silent "${PRIMARY_DIR}/${artifact}" "${REPRO_DIR}/${artifact}"'
    )
    assert copy_index > compare_index

def test_provenance_explicitly_covers_wheel_and_sdist() -> None:
    provenance = re.search(
        r"name: Attest wheel and sdist build provenance(?P<body>.*?)(?=\n\s+- name:)",
        BUILDER,
        flags=re.DOTALL,
    )
    assert provenance is not None
    assert "release-bundle/*.whl" in provenance.group("body")
    assert "release-bundle/*.tar.gz" in provenance.group("body")


def test_cyclonedx_sbom_uses_official_attestation_mode() -> None:
    sbom = re.search(
        r"name: Attest CycloneDX SBOM(?P<body>.*?)(?=\n\s+# Upload once)",
        BUILDER,
        flags=re.DOTALL,
    )
    assert sbom is not None
    assert "subject-path: release-bundle/*.whl" in sbom.group("body")
    assert "sbom-path: release-bundle/sbom.cyclonedx.json" in sbom.group("body")
    assert "predicate-type:" not in sbom.group("body")
    assert "--spec-version 1.6" in BUILDER
    # actions/attest currently recognizes CycloneDX JSON by bomFormat,
    # specVersion, and serialNumber. cyclonedx-py's reproducible mode removes
    # serialNumber, so enabling it would make the official SBOM mode reject.
    assert "--output-reproducible" not in BUILDER


def test_publish_compares_attached_sbom_to_authenticated_predicate() -> None:
    assert "attested-sbom.json" in PUBLISH
    assert "attached != attested" in PUBLISH
    assert "Attached CycloneDX SBOM differs from its attested predicate" in PUBLISH


def test_builder_uploads_exactly_once_after_attestation_and_checksums() -> None:
    assert BUILDER.count("actions/upload-artifact@") == 1
    positions = _step_order(
        BUILDER,
        "Record builder SHA-256 digests",
        "Attest wheel and sdist build provenance",
        "Attest CycloneDX SBOM",
        "Upload attested release bundle",
    )
    assert positions == sorted(positions)


def test_publish_verifies_before_pypi_and_pypi_before_release() -> None:
    positions = _step_order(
        PUBLISH,
        "Download the attested release bundle",
        "Verify builder digests and artifact set",
        "Independently verify wheel and sdist provenance",
        "Verify CycloneDX SBOM attestation",
        "Publish exact attested distributions to PyPI",
        "Confirm PyPI published the builder's exact bytes",
        "Create GitHub Release from the same verified bundle",
    )
    assert positions == sorted(positions)
    assert "packages-dir: release-bundle/" in PUBLISH
    assert "skip-existing: true" in PUBLISH
    assert "sha256sum --check SHA256SUMS" in PUBLISH


def test_reusable_builder_permissions_are_exact_and_no_secrets_are_forwarded() -> None:
    expected = """permissions:
  contents: read
  id-token: write
  attestations: write"""
    assert expected in BUILDER
    assert "secrets:" not in BUILDER

    call_job = re.search(r"\n  build:\n(?P<body>.*?)(?=\n  publish:)", PUBLISH, flags=re.DOTALL)
    assert call_job is not None
    body = call_job.group("body")
    assert "contents: read" in body
    assert "id-token: write" in body
    assert "attestations: write" in body
    assert "contents: write" not in body
    assert "secrets:" not in body


def test_publish_permission_isolation() -> None:
    assert "permissions: {}" in PUBLISH
    verify_job = re.search(
        r"\n  verify-signed-tag:\n(?P<body>.*?)(?=\n  build:)", PUBLISH, flags=re.DOTALL
    )
    publish_job = re.search(r"\n  publish:\n(?P<body>.*)\Z", PUBLISH, flags=re.DOTALL)
    assert verify_job is not None and publish_job is not None
    assert "contents: read" in verify_job.group("body")
    assert "id-token: write" not in verify_job.group("body")
    assert "attestations: write" not in publish_job.group("body")
    assert "contents: write" in publish_job.group("body")
    assert "id-token: write" in publish_job.group("body")
    assert "attestations: read" in publish_job.group("body")


def test_external_actions_are_immutably_pinned() -> None:
    for path, document in ((PUBLISH_PATH, PUBLISH), (BUILDER_PATH, BUILDER)):
        for line in document.splitlines():
            stripped = line.strip()
            if not stripped.startswith("uses:") or "./.github/" in stripped:
                continue
            reference = stripped.split("#", 1)[0].split("@", 1)[-1].strip()
            assert re.fullmatch(r"[0-9a-f]{40}", reference), (
                f"{path}: external action is not pinned to a full commit: {stripped}"
            )


def test_verification_constrains_builder_source_and_runner() -> None:
    assert "--signer-workflow" in PUBLISH
    assert ".github/workflows/reusable-build.yml" in PUBLISH
    assert '--source-digest "$GITHUB_SHA"' in PUBLISH
    assert '--source-ref "$GITHUB_REF"' in PUBLISH
    assert PUBLISH.count("--deny-self-hosted-runners") == 2
