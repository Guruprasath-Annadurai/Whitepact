# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable signatures qualify authorization only, never readiness or production."""

import base64
import json
import multiprocessing
import os
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13_bootstrap_authorization import (
    BootstrapManifest,
    BootstrapRefusedError,
    consume_bootstrap_approval,
    register_signed_new_installation,
    require_ready_verified,
)


@pytest.fixture
def bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    keys = {
        name: Ed25519PrivateKey.generate() for name in ("fixture-security", "fixture-deployment")
    }
    now = int(time.time())
    manifest = BootstrapManifest(
        "1" * 64,
        "fixture-deployment",
        "staging",
        "postgres-fixture-16",
        "store-b-fixture",
        "2" * 64,
        "3" * 64,
        now,
        now + 120,
    )
    registry = tmp_path / "external-installation-registry.sqlite3"
    config = {
        "purpose": "NONPRODUCTION_BOOTSTRAP_QUALIFICATION",
        **{
            name: getattr(manifest, name)
            for name in (
                "installation_id",
                "deployment_id",
                "environment",
                "postgres_identity",
                "store_b_identity",
            )
        },
        "registry": str(registry),
        "operators": {
            role: {
                "identity": identity,
                "public_key": keys[identity].public_key().public_bytes_raw().hex(),
                "revoked": False,
            }
            for role, identity in (
                ("SECURITY_OWNER", "fixture-security"),
                ("DEPLOYMENT_OPERATOR", "fixture-deployment"),
            )
        },
    }
    profile = tmp_path / "operator-trust.json"
    profile.write_text(json.dumps(config))
    profile.chmod(0o600)

    def sign(value):
        return {
            identity: base64.b64encode(key.sign(value.canonical_bytes())).decode("ascii")
            for identity, key in keys.items()
        }

    return profile, registry, manifest, sign, config


def test_valid_authorization_consumed_once_but_never_ready(bootstrap):
    profile, registry, manifest, sign, _ = bootstrap
    approvals = sign(manifest)
    digest = register_signed_new_installation(profile, manifest, approvals)
    result = consume_bootstrap_approval(profile, manifest, approvals)
    assert result == {"manifest_digest": digest, "state": "BOOTSTRAP_AUTHORIZED", "ready": False}
    with pytest.raises(BootstrapRefusedError, match="consumed"):
        consume_bootstrap_approval(profile, manifest, approvals)
    with pytest.raises(BootstrapRefusedError, match="exists"):
        register_signed_new_installation(profile, manifest, approvals)
    with pytest.raises(BootstrapRefusedError, match="not implemented"):
        require_ready_verified(profile)
    with sqlite3.connect(registry) as connection:
        assert connection.execute("SELECT state,consumed_nonce FROM installation").fetchone() == (
            "BOOTSTRAP_AUTHORIZED",
            manifest.nonce,
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name='durable_restore_readiness'"
            ).fetchone()
            is None
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("installation_id", "4" * 64),
        ("deployment_id", "another-deployment"),
        ("environment", "development"),
        ("postgres_identity", "different-postgres"),
        ("store_b_identity", "replaced-store-b"),
    ],
)
def test_cross_target_approval_never_registers(bootstrap, field, value):
    profile, registry, manifest, sign, _ = bootstrap
    wrong = replace(manifest, **{field: value})
    with pytest.raises(BootstrapRefusedError, match="Cross-deployment"):
        register_signed_new_installation(profile, wrong, sign(wrong))
    assert not registry.exists()


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "forged",
        "modified",
        "expired",
        "future",
        "revoked",
        "duplicate-key",
        "duplicate-identity",
        "production",
    ],
)
def test_untrusted_or_noncurrent_approvals_never_create_registry(bootstrap, kind, monkeypatch):
    profile, registry, manifest, sign, config = bootstrap
    approvals = sign(manifest)
    if kind == "missing":
        approvals.pop("fixture-security")
    elif kind == "forged":
        approvals["fixture-security"] = base64.b64encode(b"\0" * 64).decode()
    elif kind == "modified":
        manifest = replace(manifest, evidence_digest="4" * 64)
    elif kind == "expired":
        manifest = replace(
            manifest, created_at=int(time.time()) - 200, expires_at=int(time.time()) - 100
        )
        approvals = sign(manifest)
    elif kind == "future":
        manifest = replace(
            manifest, created_at=int(time.time()) + 300, expires_at=int(time.time()) + 400
        )
        approvals = sign(manifest)
    elif kind in {"revoked", "duplicate-key", "duplicate-identity"}:
        a, b = config["operators"].values()
        if kind == "revoked":
            a["revoked"] = True
        elif kind == "duplicate-key":
            b["public_key"] = a["public_key"]
        else:
            b["identity"] = a["identity"]
        profile.write_text(json.dumps(config))
    elif kind == "production":
        monkeypatch.setenv("WHITEPACT_ENV", "production")
    with pytest.raises(BootstrapRefusedError):
        register_signed_new_installation(profile, manifest, approvals)
    assert not registry.exists()


def test_missing_external_history_never_reconstructed(bootstrap):
    profile, registry, manifest, sign, _ = bootstrap
    with pytest.raises(BootstrapRefusedError, match="history unavailable"):
        consume_bootstrap_approval(profile, manifest, sign(manifest))
    assert not registry.exists()


def test_concurrent_consumption_has_exactly_one_winner(bootstrap):
    profile, _, manifest, sign, _ = bootstrap
    approvals = sign(manifest)
    register_signed_new_installation(profile, manifest, approvals)

    def attempt():
        try:
            return consume_bootstrap_approval(profile, manifest, approvals)["ready"] is False
        except BootstrapRefusedError:
            return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sum(workers.map(lambda _: attempt(), range(2))) == 1


def test_partial_registry_creation_stays_closed(bootstrap):
    profile, registry, manifest, sign, _ = bootstrap
    registry.touch(mode=0o600)
    with pytest.raises(BootstrapRefusedError):
        consume_bootstrap_approval(profile, manifest, sign(manifest))
    with pytest.raises(BootstrapRefusedError):
        register_signed_new_installation(profile, manifest, sign(manifest))
    with pytest.raises(BootstrapRefusedError):
        require_ready_verified(profile)


def test_recovery_or_arbitrary_python_object_is_not_bootstrap_authority(bootstrap):
    profile, registry, _, _, _ = bootstrap
    with pytest.raises(BootstrapRefusedError, match="manifest required"):
        register_signed_new_installation(profile, object(), {})
    assert not registry.exists()


def _consume_and_exit(profile, manifest, signatures):
    consume_bootstrap_approval(profile, manifest, signatures)
    os._exit(23)


def test_real_process_exit_after_consumption_preserves_replay_refusal(bootstrap):
    profile, _, manifest, sign, _ = bootstrap
    signatures = sign(manifest)
    register_signed_new_installation(profile, manifest, signatures)
    child = multiprocessing.get_context("spawn").Process(
        target=_consume_and_exit, args=(profile, manifest, signatures)
    )
    child.start()
    try:
        child.join(15)
        assert child.exitcode == 23
        with pytest.raises(BootstrapRefusedError, match="consumed"):
            consume_bootstrap_approval(profile, manifest, signatures)
        with pytest.raises(BootstrapRefusedError, match="not implemented"):
            require_ready_verified(profile)
    finally:
        if child.is_alive():
            child.terminate()
        child.join(5)


def test_revocation_after_registration_blocks_consumption(bootstrap):
    profile, registry, manifest, sign, config = bootstrap
    approvals = sign(manifest)
    register_signed_new_installation(profile, manifest, approvals)
    config["operators"]["SECURITY_OWNER"]["revoked"] = True
    profile.write_text(json.dumps(config))
    with pytest.raises(BootstrapRefusedError, match="revoked"):
        consume_bootstrap_approval(profile, manifest, approvals)
    with sqlite3.connect(registry) as connection:
        assert connection.execute("SELECT state,consumed_nonce FROM installation").fetchone() == (
            "UNINITIALIZED",
            None,
        )


def test_unsupported_schema_is_not_an_authorized_bootstrap(bootstrap):
    profile, registry, manifest, _, _ = bootstrap
    with pytest.raises(BootstrapRefusedError, match="schema"):
        register_signed_new_installation(profile, replace(manifest, schema_revision="0068"), {})
    assert not registry.exists()


def test_concurrent_registration_has_exactly_one_winner(bootstrap):
    profile, _, manifest, sign, _ = bootstrap
    approvals = sign(manifest)

    def attempt():
        try:
            register_signed_new_installation(profile, manifest, approvals)
            return True
        except BootstrapRefusedError:
            return False

    with ThreadPoolExecutor(max_workers=2) as workers:
        assert sum(workers.map(lambda _: attempt(), range(2))) == 1
    assert consume_bootstrap_approval(profile, manifest, approvals)["ready"] is False
