# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Nonproduction Ed25519 fixtures; not production operator enrollment."""

import base64
from dataclasses import replace

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from responsibleai.data_governance.operator_recovery import (
    OperatorKey,
    RecoveryAuthorizationError,
    RecoveryManifest,
    verify_operator_approvals,
)


def fixture_request():
    manifest = RecoveryManifest(
        request_id="test-request",
        deployment_id="isolated-test",
        environment="test",
        incident_id="test-incident",
        postgres_identity="test-pg",
        schema_revision="0066",
        store_b_identity="test-store-b",
        readiness_epoch=7,
        journal_digest="a" * 64,
        revocation_digest="b" * 64,
        docker_identity="test-docker",
        inventory_digest="c" * 64,
        evidence_digest="d" * 64,
        action="RECONCILE_EXECUTION_ADMISSION",
        scope="SINGLE_HOST",
        security_owner="security",
        recovery_operator="recovery",
        created_at=1000,
        expires_at=1120,
        nonce="e" * 64,
    )
    private = {name: Ed25519PrivateKey.generate() for name in ("security", "recovery")}
    trust = tuple(
        OperatorKey(
            name, role, private[name].public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        )
        for name, role in (("security", "SECURITY_OWNER"), ("recovery", "RECOVERY_OPERATOR"))
    )
    signatures = {
        name: base64.b64encode(key.sign(manifest.canonical_bytes())).decode("ascii")
        for name, key in private.items()
    }
    return manifest, trust, signatures


def test_distinct_disposable_operator_signatures_verify():
    manifest, trust, signatures = fixture_request()
    assert (
        verify_operator_approvals(
            manifest, trust, signatures, now=1010, deployment_id="isolated-test", environment="test"
        )
        == manifest.digest()
    )


@pytest.mark.parametrize(
    "change",
    [
        {"expires_at": 1001},
        {"created_at": 1020},
        {"expires_at": 2000},
        {"deployment_id": "other"},
        {"environment": "production"},
        {"journal_digest": "f" * 64},
        {"nonce": "short"},
        {"security_owner": "recovery"},
        {"schema_revision": ""},
    ],
)
def test_invalid_or_changed_manifest_rejected(change):
    manifest, trust, signatures = fixture_request()
    with pytest.raises(RecoveryAuthorizationError):
        verify_operator_approvals(
            replace(manifest, **change),
            trust,
            signatures,
            now=1010,
            deployment_id="isolated-test",
            environment="test",
        )


@pytest.mark.parametrize(
    "case", ["missing", "revoked", "wrong_role", "same_key", "forged", "extra"]
)
def test_invalid_operator_approvals_rejected(case):
    manifest, trust, signatures = fixture_request()
    if case == "missing":
        signatures.pop("security")
    elif case == "revoked":
        trust = (replace(trust[0], revoked=True), trust[1])
    elif case == "wrong_role":
        trust = (replace(trust[0], role="RECOVERY_OPERATOR"), trust[1])
    elif case == "same_key":
        trust = (trust[0], replace(trust[1], public_key=trust[0].public_key))
    elif case == "forged":
        signatures["security"] = base64.b64encode(b"x" * 64).decode("ascii")
    else:
        signatures["customer"] = signatures["security"]
    with pytest.raises(RecoveryAuthorizationError):
        verify_operator_approvals(
            manifest, trust, signatures, now=1010, deployment_id="isolated-test", environment="test"
        )
