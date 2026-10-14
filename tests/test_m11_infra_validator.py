# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline tooling safety; no provider or cloud operations in unit tests."""

import hashlib
import io
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest
from scripts.infra.validate_terraform import (
    MODULES,
    checked_revision,
    clean_environment,
    extract_archive,
    provider_commands,
    validate,
    validation_result,
    verify_binary,
)


def test_commands_cannot_apply_plan_destroy_or_mutate_lock():
    commands = provider_commands(Path("/trusted/terraform"))
    assert commands == [
        [
            "/trusted/terraform",
            "init",
            "-backend=false",
            "-lockfile=readonly",
            "-input=false",
            "-no-color",
        ],
        ["/trusted/terraform", "validate", "-json"],
    ]
    assert not {"apply", "plan", "destroy", "login", "import", "unlock"}.intersection(
        value for command in commands for value in command
    )
    assert "whitepact-hetzner-foundation" not in MODULES


def test_environment_drops_secrets_proxy_tfvars_and_cloud_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "sentinel-private")
    monkeypatch.setenv("TF_VAR_token", "sentinel-token")
    monkeypatch.setenv("TF_CLI_ARGS", "-backend=true")
    monkeypatch.setenv("HTTPS_PROXY", "http://credential-bearing.invalid")
    env = clean_environment(tmp_path)
    assert env["HOME"] == str(tmp_path)
    assert env["CHECKPOINT_DISABLE"] == "1"
    assert not set(env).intersection(
        {"AWS_SECRET_ACCESS_KEY", "TF_VAR_token", "TF_CLI_ARGS", "HTTPS_PROXY"}
    )
    assert "sentinel" not in str(env)


@pytest.mark.parametrize("revision", ["--all", "main;apply", "../../", "abc", "HEAD~1"])
def test_revision_is_not_a_shell_or_git_option(revision):
    with pytest.raises(ValueError):
        checked_revision(revision)


def test_exact_revision_and_head_supported():
    assert checked_revision("HEAD") == "HEAD"
    assert checked_revision("62be9caa70e6c2eb1c4782a64554323646d987e0")


def test_tfenv_wrapper_or_wrong_binary_is_rejected_before_execution(tmp_path):
    wrapper = tmp_path / "terraform"
    wrapper.write_text("#!/bin/sh\nexit 0\n")
    wrapper.chmod(0o700)
    with pytest.raises(ValueError, match="checksum"):
        verify_binary(wrapper, "0" * 64)


def test_binary_checksum_verified_without_home_config(tmp_path):
    binary = tmp_path / "terraform"
    binary.write_bytes(b"test-only binary bytes")
    binary.chmod(0o700)
    assert verify_binary(binary, hashlib.sha256(binary.read_bytes()).hexdigest()) == binary


@pytest.mark.parametrize("name", ["../escape", "/absolute"])
def test_archive_traversal_rejected(tmp_path, name):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        item = tarfile.TarInfo(name)
        item.size = 1
        archive.addfile(item, io.BytesIO(b"x"))
    with pytest.raises(ValueError, match="archive"):
        extract_archive(data.getvalue(), tmp_path)


def test_archive_symlink_rejected(tmp_path):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        item = tarfile.TarInfo("outside-link")
        item.type = tarfile.SYMTYPE
        item.linkname = "/Users/ag"
        archive.addfile(item)
    with pytest.raises(ValueError, match="archive"):
        extract_archive(data.getvalue(), tmp_path)


def test_safe_archive_materializes_only_inside_disposable_root(tmp_path):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode="w") as archive:
        item = tarfile.TarInfo("infra/terraform/example.tf")
        item.size = 3
        archive.addfile(item, io.BytesIO(b"#ok"))
    extract_archive(data.getvalue(), tmp_path)
    assert (tmp_path / "infra/terraform/example.tf").read_text() == "#ok"


@pytest.mark.parametrize("timeout", [0, 9, 301, 10000])
def test_command_deadline_bounds_before_any_binary_or_provider_operation(tmp_path, timeout):
    with pytest.raises(ValueError, match="timeout"):
        validate(tmp_path, tmp_path / "missing", timeout=timeout)


@pytest.mark.parametrize("option", ["--apply", "--plan", "--destroy", "--module"])
def test_cli_does_not_expose_mutation_or_arbitrary_target_option(option):
    script = Path(__file__).resolve().parents[1] / "scripts/infra/validate_terraform.py"
    result = subprocess.run(
        [sys.executable, str(script), "--terraform-binary", "/not/executed", option],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert not result.stdout


def test_provider_download_requires_explicit_opt_in():
    script = Path(__file__).resolve().parents[1] / "scripts/infra/validate_terraform.py"
    result = subprocess.run(
        [sys.executable, str(script), "--terraform-binary", "/not/executed"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert "no provider or cloud operation performed" in result.stderr
    assert not result.stdout


@pytest.mark.parametrize("output", [None, [], {}, {"valid": "true"}])
def test_malformed_validation_output_cannot_pass(output):
    assert validation_result(output, 0)["status"] == "BLOCKED"


def test_validation_diagnostics_never_echo_secret_or_source_values():
    output = {
        "format_version": "1.0",
        "valid": True,
        "error_count": 0,
        "warning_count": 1,
        "diagnostics": [
            {"severity": "warning", "summary": "sentinel-secret", "detail": "secret-value"}
        ],
    }
    result = validation_result(output, 0)
    assert result["status"] == "PASS"
    assert result["warning_count"] == 1
    assert "secret" not in str(result)
    output["error_count"] = 1
    assert validation_result(output, 0)["status"] == "BLOCKED"
    output["diagnostics"].append({"severity": "error", "summary": "not printed"})
    assert validation_result(output, 0)["status"] == "FAIL"
    output["error_count"] = 0
    output["diagnostics"].pop()
    assert validation_result(output, 1)["status"] == "FAIL"
