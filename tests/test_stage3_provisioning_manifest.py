# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent negative oracles for controller attestations, not activation proof."""

import base64
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from responsibleai.data_governance.provisioning_manifest import (
    ProvisionerTrust,
    ProvisioningAuthorizationError,
    ProvisioningManifest,
    verify_provisioning_manifest,
)


@pytest.fixture
def signed():
    key = Ed25519PrivateKey.generate()
    manifest = ProvisioningManifest(
        deployment_id="isolated",
        environment="test",
        postgres_identity="postgres/test",
        store_b_identity="store-b/test",
        request_id="request-1",
        principal_id="user-1",
        tenant_id="tenant-1",
        generation_id="a" * 64,
        operation_digest="b" * 64,
        pending_receipt_digest="c" * 64,
        readiness_epoch=7,
        security_epoch=1,
        revocation_floor=1,
        created_at=100,
        expires_at=130,
        nonce="d" * 64,
        controller_id="disposable-controller",
    )
    trust = ProvisionerTrust(
        "disposable-controller",
        key.public_key().public_bytes_raw(),
        "isolated",
        "test",
        "postgres/test",
        "store-b/test",
    )
    signature = base64.b64encode(key.sign(manifest.canonical_bytes())).decode("ascii")
    return manifest, signature, trust


def verify(signed, **changes):
    manifest, signature, trust = signed
    return verify_provisioning_manifest(
        manifest, signature, trust, **({"now": 110, "current_readiness_epoch": 7} | changes)
    )


def test_valid_signature_proves_only_exact_attestation(signed):
    assert verify(signed) == signed[0].digest()


@pytest.mark.parametrize(
    "field,value",
    [
        ("deployment_id", "another"),
        ("environment", "production"),
        ("postgres_identity", "postgres/other"),
        ("store_b_identity", "store-b/other"),
        ("controller_id", "forged"),
        ("tenant_id", "another"),
        ("principal_id", "another"),
        ("request_id", "another"),
        ("generation_id", "e" * 64),
        ("operation_digest", "e" * 64),
        ("pending_receipt_digest", "e" * 64),
        ("nonce", "e" * 64),
        ("security_epoch", 2),
        ("revocation_floor", 2),
    ],
)
def test_modified_binding_cannot_reuse_signature(signed, field, value):
    manifest, signature, trust = signed
    with pytest.raises(ProvisioningAuthorizationError):
        verify((replace(manifest, **{field: value}), signature, trust))


@pytest.mark.parametrize("now", [99, 130, 131, True, 110.0])
def test_expired_future_or_ambiguous_clock_rejected(signed, now):
    with pytest.raises(ProvisioningAuthorizationError):
        verify(signed, now=now)


def test_readiness_change_invalidates_authorization(signed):
    with pytest.raises(ProvisioningAuthorizationError):
        verify(signed, current_readiness_epoch=8)


@pytest.mark.parametrize("signature", ["", "not-base64", "AA==", None, "A" * 88])
def test_missing_malformed_and_forged_signature_rejected(signed, signature):
    manifest, _, trust = signed
    with pytest.raises(ProvisioningAuthorizationError):
        verify((manifest, signature, trust))


def test_unrecognized_or_revoked_key_rejected(signed):
    manifest, signature, trust = signed
    for changed in (
        replace(trust, revoked=True),
        replace(trust, public_key=Ed25519PrivateKey.generate().public_key().public_bytes_raw()),
    ):
        with pytest.raises(ProvisioningAuthorizationError):
            verify((manifest, signature, changed))


@pytest.mark.parametrize(
    "field,value",
    [
        ("generation_id", "old-label"),
        ("readiness_epoch", True),
        ("security_epoch", 0),
        ("revocation_floor", 0),
        ("expires_at", 161),
        ("expires_at", 100),
        ("action", "RESTORE_READY"),
        ("nonce", "x" * 64),
    ],
)
def test_malformed_manifest_has_no_canonical_authority(signed, field, value):
    manifest, _, _ = signed
    with pytest.raises(ProvisioningAuthorizationError):
        replace(manifest, **{field: value}).canonical_bytes()


def test_signature_reverification_is_not_replay_prevention(signed):
    # Deliberately prevents this pure verifier from being advertised as a ledger.
    assert verify(signed) == verify(signed)
