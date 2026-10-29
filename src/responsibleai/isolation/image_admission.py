# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Fail-closed image admission at the trusted Docker control-plane boundary.

Approval is deployment configuration, never request input. Registry references
bind BOTH the manifest digest and the expected Docker configuration/content ID.
An explicitly approved full local content ID supports offline/prebuilt images;
it is never a fallback for a failed registry operation. Docker's content store
and daemon are trusted (a compromised privileged daemon is outside containment).
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass

from responsibleai.environment import is_production
from responsibleai.isolation.errors import IsolationBackendUnavailableError

APPROVALS_ENV = "WHITEPACT_ISOLATION_IMAGE_APPROVALS"
_ID = re.compile(r"sha256:[0-9a-f]{64}\Z")
_CID = re.compile(r"[0-9a-f]{64}\Z")
_REPOSITORY = re.compile(r"[a-z0-9][a-z0-9._:/-]*\Z")


class ImageAdmissionError(IsolationBackendUnavailableError):
    """No execution is permitted without fresh, validated image admission."""


def _ref_valid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    if _ID.fullmatch(value):
        return True
    if value.count("@") != 1:
        return False
    repository, digest = value.split("@")
    return bool(
        _ID.fullmatch(digest)
        and _REPOSITORY.fullmatch(repository)
        and ":" not in repository.rsplit("/", 1)[-1]
        and all(p not in {"", ".", ".."} for p in repository.split("/"))
    )


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise ValueError("duplicate approval")
        result[key] = value
    return result


def _approved(reference: str) -> str:
    try:
        raw = os.environ.get(APPROVALS_ENV, "")
        if not _ref_valid(reference) or not raw or len(raw) > 16_384:
            raise ValueError
        if _ID.fullmatch(reference) and is_production():
            # Qualification/local builds have no registry manifest provenance.
            # Production must approve a repository digest AND its content ID.
            raise ValueError
        records = json.loads(raw, object_pairs_hook=_pairs)
        if not isinstance(records, dict) or not 0 < len(records) <= 64:
            raise ValueError
        for ref, identity in records.items():
            if not _ref_valid(ref) or not isinstance(identity, str) or not _ID.fullmatch(identity):
                raise ValueError
            if _ID.fullmatch(ref) and ref != identity:
                raise ValueError
        return records[reference]
    except (ValueError, KeyError, TypeError, RecursionError):
        raise ImageAdmissionError("Isolation image approval is missing or invalid.") from None


def _run(docker_cmd: str, arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            [docker_cmd, *arguments],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
            shell=False,
        )
        if len(result.stdout) > 1_000_000:
            raise ValueError
        return result.stdout
    except (OSError, subprocess.SubprocessError, ValueError):
        raise ImageAdmissionError("Isolation image verification is unavailable.") from None


@dataclass(frozen=True)
class AdmittedImage:
    reference: str
    image_id: str


def assert_approval_current(admitted: AdmittedImage) -> None:
    if _approved(admitted.reference) != admitted.image_id:
        raise ImageAdmissionError("Isolation image approval changed before execution.")


def admit_image(docker_cmd: str, reference: str) -> AdmittedImage:
    expected = _approved(reference)
    registry = "@" in reference
    if registry:
        # Always contact the configured registry for this mode. An outage never
        # authorizes use of a stale tag/cache or switching to a local-ID policy.
        _run(docker_cmd, ["pull", "--quiet", reference])
    try:
        images = json.loads(
            _run(docker_cmd, ["image", "inspect", reference]), object_pairs_hook=_pairs
        )
        if not isinstance(images, list) or len(images) != 1 or not isinstance(images[0], dict):
            raise ValueError
        image = images[0]
        if image.get("Id") != expected or image.get("Os") != "linux":
            raise ValueError
        if registry and (
            not isinstance(image.get("RepoDigests"), list) or reference not in image["RepoDigests"]
        ):
            raise ValueError
        # Re-read approval after a potentially slow pull/inspection.
        if _approved(reference) != expected:
            raise ValueError
        return AdmittedImage(reference, expected)
    except (ValueError, TypeError, RecursionError):
        raise ImageAdmissionError("Isolation image identity does not match its approval.") from None


def verify_container_image(docker_cmd: str, container_id: str, admitted: AdmittedImage) -> None:
    if not _CID.fullmatch(container_id):
        raise ImageAdmissionError("Isolation image approval changed before execution.")
    assert_approval_current(admitted)
    actual = _run(
        docker_cmd, ["container", "inspect", "--format", "{{.Image}}", container_id]
    ).strip()
    if actual != admitted.image_id:
        raise ImageAdmissionError("Stopped container image differs from its admitted identity.")
    assert_approval_current(admitted)
