# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Immutable image admission; simulated Docker receipts are unit evidence only."""

import json
import subprocess

import pytest

from responsibleai.isolation.image_admission import (
    ImageAdmissionError,
    admit_image,
    verify_container_image,
)

IMAGE = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64
REF = "registry.example/whitepact@sha256:" + "c" * 64


def docker(monkeypatch, *, reference=REF, receipt=None, failure=None):
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({reference: IMAGE}))
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        if failure:
            raise failure
        if args[1] == "pull":
            return subprocess.CompletedProcess(args, 0, "")
        if args[1:3] == ["image", "inspect"]:
            return subprocess.CompletedProcess(
                args, 0, json.dumps([receipt or {"Id": IMAGE, "RepoDigests": [REF], "Os": "linux"}])
            )
        return subprocess.CompletedProcess(args, 0, IMAGE + "\n")

    monkeypatch.setattr(subprocess, "run", run)
    return calls


@pytest.mark.parametrize(
    "name",
    [
        "python:latest",
        "registry.example/whitepact:v1",
        "sha256:ab",
        REF + "\n",
        "--privileged",
        "",
        "registry.example/whitepact:v1@sha256:" + "c" * 64,
    ],
)
def test_mutable_or_malformed_reference_never_contacts_docker(monkeypatch, name):
    calls = docker(monkeypatch)
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", name)
    assert calls == []


def test_pin_requires_independent_approval(monkeypatch):
    calls = docker(monkeypatch)
    monkeypatch.delenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS")
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", REF)
    assert calls == []


@pytest.mark.parametrize(
    "receipt",
    [
        {"Id": OTHER, "RepoDigests": [REF], "Os": "linux"},
        {"Id": IMAGE, "RepoDigests": ["other@sha256:" + "c" * 64], "Os": "linux"},
        {"Id": IMAGE, "RepoDigests": [REF], "Os": "windows"},
    ],
)
def test_manifest_config_repository_or_platform_substitution_refused(monkeypatch, receipt):
    docker(monkeypatch, receipt=receipt)
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", REF)


@pytest.mark.parametrize(
    "failure",
    [
        OSError("credential=/private/token"),
        subprocess.TimeoutExpired("docker", 30),
        subprocess.CalledProcessError(1, "docker", stderr="secret"),
    ],
)
def test_registry_failure_cannot_use_cached_image_or_leak_diagnostics(monkeypatch, failure):
    calls = docker(monkeypatch, failure=failure)
    with pytest.raises(ImageAdmissionError) as caught:
        admit_image("docker", REF)
    assert len(calls) == 1 and calls[0][1] == "pull"
    assert "private" not in str(caught.value) and "secret" not in str(caught.value)


def test_approved_registry_pin_returns_content_identity(monkeypatch):
    calls = docker(monkeypatch)
    admitted = admit_image("docker", REF)
    assert admitted.image_id == IMAGE and admitted.reference == REF
    assert calls[0][1:] == ["pull", "--quiet", REF]
    verify_container_image("docker", "d" * 64, admitted)


def test_explicit_approved_local_content_id_is_not_a_tag_exception(monkeypatch):
    calls = docker(monkeypatch, reference=IMAGE)
    admitted = admit_image("docker", IMAGE)
    assert admitted.image_id == IMAGE and not any(c[1] == "pull" for c in calls)


def test_changed_container_image_cannot_start(monkeypatch):
    docker(monkeypatch)
    admitted = admit_image("docker", REF)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(a, 0, OTHER))
    with pytest.raises(ImageAdmissionError):
        verify_container_image("docker", "d" * 64, admitted)


def test_revoked_approval_between_admission_and_start_refused(monkeypatch):
    docker(monkeypatch)
    admitted = admit_image("docker", REF)
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", "{}")
    with pytest.raises(ImageAdmissionError):
        verify_container_image("docker", "d" * 64, admitted)


def test_recovery_requires_new_successful_admission_not_cached_receipt(monkeypatch):
    docker(monkeypatch, failure=OSError("offline"))
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", REF)
    calls = docker(monkeypatch)
    assert admit_image("docker", REF).image_id == IMAGE
    assert calls[0][1] == "pull"


def test_actual_backend_preflight_refuses_tag_before_host_work(monkeypatch):
    from responsibleai.isolation.container_backend import DockerContainerBackend

    backend = DockerContainerBackend(image_name="python:latest")
    monkeypatch.setattr(backend, "is_available", lambda: True)

    def forbidden(*args):
        pytest.fail("Refused image must not install runner or stage a workspace")

    monkeypatch.setattr(backend, "_install_trusted_runner", forbidden)
    with pytest.raises(ImageAdmissionError):
        backend.preflight()


@pytest.mark.asyncio
async def test_execute_cannot_skip_approval_after_a_successful_probe(monkeypatch):
    from responsibleai.isolation import durable_intent
    from responsibleai.isolation.container_backend import DockerContainerBackend
    from responsibleai.isolation.models import IsolatedExecutionRequest, IsolationProfile

    backend = DockerContainerBackend(image_name=IMAGE)
    monkeypatch.setattr(backend, "is_available", lambda: True)
    monkeypatch.setattr(durable_intent, "required_journal", lambda: None)
    monkeypatch.delenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", raising=False)

    def forbidden(*args):
        pytest.fail("No unapproved image may create a trusted runner")

    monkeypatch.setattr(backend, "_install_trusted_runner", forbidden)
    request = IsolatedExecutionRequest(
        action_id="unit",
        organization_id="unit",
        action_type="test",
        arguments={},
        profile=IsolationProfile(),
        environment_overrides={"WHITEPACT_ISOLATION_IMAGE_APPROVALS": json.dumps({IMAGE: IMAGE})},
    )
    with pytest.raises(ImageAdmissionError):
        await backend.execute(request)


@pytest.mark.parametrize(
    "raw",
    [
        "{}",
        "[]",
        "null",
        '{"sha256:a":"sha256:b"}',
        '{"' + IMAGE + '":"' + IMAGE + '","' + IMAGE + '":"' + OTHER + '"}',
    ],
)
def test_invalid_or_duplicate_approval_configuration_refused(monkeypatch, raw):
    calls = docker(monkeypatch)
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", raw)
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", REF)
    assert calls == []


@pytest.mark.parametrize(
    "variable,value",
    [("WHITEPACT_ENV", "production"), ("ENVIRONMENT", "prod"), ("RAI_ENV", "prodution")],
)
def test_local_content_qualification_never_substitutes_for_production_registry_pin(
    monkeypatch, variable, value
):
    calls = docker(monkeypatch, reference=IMAGE)
    monkeypatch.setenv(variable, value)
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", IMAGE)
    assert calls == []


def test_production_requires_and_accepts_full_approved_registry_binding(monkeypatch):
    docker(monkeypatch)
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    assert admit_image("docker", REF).image_id == IMAGE


@pytest.mark.parametrize(
    "body",
    [
        "not-json",
        "{}",
        "[]",
        "[{},{}]",
        '[{"Id":"' + OTHER + '","Id":"' + IMAGE + '","Os":"linux","RepoDigests":["' + REF + '"]}]',
        "x" * 1_000_001,
    ],
    ids=[
        "malformed-json",
        "wrong-shape",
        "empty-array",
        "ambiguous-array",
        "duplicate-field",
        "oversized",
    ],
)
def test_malformed_ambiguous_or_oversized_docker_receipts_fail_closed(monkeypatch, body):
    docker(monkeypatch)

    def run(args, **kwargs):
        return subprocess.CompletedProcess(args, 0, "" if args[1] == "pull" else body)

    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", REF)


def test_policy_removed_during_container_inspection_is_not_a_lease(monkeypatch):
    docker(monkeypatch)
    admitted = admit_image("docker", REF)

    def inspect(*args, **kwargs):
        monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", "{}")
        return subprocess.CompletedProcess(args, 0, IMAGE)

    monkeypatch.setattr(subprocess, "run", inspect)
    with pytest.raises(ImageAdmissionError):
        verify_container_image("docker", "d" * 64, admitted)
