# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The evidence anchor against a REAL S3-compatible object-lock service (MinIO, over TLS).

What this proves: our SigV4 signing, https-only transport, ``If-None-Match`` and COMPLIANCE retention headers are
accepted by an actual server; a read-back returns the exact bytes with the lock and a future retain-until; an
overwrite is refused; deleting the locked version is refused. What it does NOT prove: Cloudflare R2 or AWS S3
behaviour, an independent administrative domain (the container is ours), or a provisioned production witness --
``live_object_store_status()`` stays NOT_PROVISIONED. Needs Docker; WHITEPACT_REQUIRE_OBJECT_LOCK_TEST=1 turns a
missing daemon into a failure.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime, timedelta
from ipaddress import ip_address

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from responsibleai.governance.evidence_publication import (
    LIVE_OBJECT_STORE_STATUS,
    WitnessRequiredUnavailableError,
    _sigv4_request,
    live_object_store_status,
    object_lock_headers,
    put_object_lock,
    read_back_object_lock,
)

IMAGE = (
    "bitnamilegacy/minio:latest"  # real MinIO; the official Docker Hub image is no longer published
)
USER, PASSWORD, REGION = "wpadmin", "wpadmin-" + uuid.uuid4().hex, "us-east-1"


def _docker_ok() -> bool:
    return (
        bool(shutil.which("docker"))
        and subprocess.run(  # noqa: S603, S607
            ["docker", "info"], capture_output=True
        ).returncode
        == 0
    )


def _self_signed(directory) -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "127.0.0.1")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.IPAddress(ip_address("127.0.0.1")), x509.DNSName("localhost")]
            ),
            False,
        )
        .sign(key, hashes.SHA256())
    )
    (directory / "public.crt").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    (directory / "private.key").write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
    )
    return str(directory / "public.crt")


@pytest.fixture()
def store(tmp_path):
    if not _docker_ok():
        if os.environ.get("WHITEPACT_REQUIRE_OBJECT_LOCK_TEST") == "1":
            pytest.fail("WHITEPACT_REQUIRE_OBJECT_LOCK_TEST=1 but no Docker daemon is available")
        pytest.skip(
            "QUALIFICATION_SKIP purpose=live object-lock anchor. No Docker daemon. Not a pass."
        )
    cafile = _self_signed(tmp_path)
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    name = f"wp-minio-{uuid.uuid4().hex[:8]}"
    subprocess.run(  # noqa: S603, S607
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "--name",
            name,
            "-p",
            f"127.0.0.1:{port}:9000",
            "-e",
            f"MINIO_ROOT_USER={USER}",
            "-e",
            f"MINIO_ROOT_PASSWORD={PASSWORD}",
            "-e",
            "MINIO_SCHEME=https",
            "-v",
            f"{tmp_path}:/certs:ro",
            IMAGE,
        ],
        check=True,
        capture_output=True,
    )
    ctx = ssl.create_default_context(cafile=cafile)  # trust ONLY the test CA; verification stays on

    def send(request):
        try:
            with urllib.request.urlopen(request, context=ctx, timeout=10) as r:  # noqa: S310
                return r.status, r.read(), dict(r.headers.items())
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(), dict(exc.headers.items())

    endpoint = f"https://127.0.0.1:{port}"
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(
                    endpoint + "/minio/health/live", context=ctx, timeout=2
                ):  # noqa: S310
                    break
            except Exception:
                time.sleep(0.3)
        else:
            raise AssertionError("minio did not become healthy")
        bucket = "anchor"
        request = _sigv4_request(
            method="PUT",
            endpoint=endpoint,
            bucket=bucket,
            key="",
            body=b"",
            access_key_id=USER,
            secret_access_key=PASSWORD,
            region=REGION,
            extra_headers={"x-amz-bucket-object-lock-enabled": "true"},
        )
        assert send(request)[0] == 200
        yield endpoint, bucket, send
    finally:
        subprocess.run(["docker", "kill", name], capture_output=True)  # noqa: S603, S607


def _kw():
    return {"access_key_id": USER, "secret_access_key": PASSWORD, "region": REGION}


def test_anchor_is_written_locked_readable_and_cannot_be_overwritten_or_deleted(store) -> None:
    endpoint, bucket, send = store
    record = json.dumps(
        {"witness_ref": "wr1_example", "chain_sequence": 7, "head_hash": "a" * 64}
    ).encode()
    until = datetime.now(UTC) + timedelta(days=1)
    status = put_object_lock(
        endpoint=endpoint,
        bucket=bucket,
        key="wr1_example/7.json",
        body=record,
        retain_until=until,
        transport=lambda r: send(r)[:2],
        **_kw(),
    )
    assert status == 200

    back = read_back_object_lock(
        endpoint=endpoint, bucket=bucket, key="wr1_example/7.json", transport=send, **_kw()
    )
    assert back.body == record  # the auditor reads back exactly what was anchored
    assert back.lock_mode == "COMPLIANCE"
    assert back.retain_until is not None and back.retain_until.startswith(
        until.strftime("%Y-%m-%d")
    )
    assert back.version_id

    # An overwrite with different content is refused by the server (If-None-Match: *).
    with pytest.raises(WitnessRequiredUnavailableError, match="412"):
        put_object_lock(
            endpoint=endpoint,
            bucket=bucket,
            key="wr1_example/7.json",
            body=b"{}",
            retain_until=until,
            transport=lambda r: send(r)[:2],
            **_kw(),
        )

    # Deleting the locked version is refused (COMPLIANCE retention; not even the root user may).
    delete = _sigv4_request(
        method="DELETE",
        endpoint=endpoint,
        bucket=bucket,
        key="wr1_example/7.json",
        body=b"",
        query=f"versionId={back.version_id}",
        **_kw(),
    )
    result = send(delete)
    # MinIO answers 400 InvalidRequest "Object is WORM protected"; S3/R2 answer 403 AccessDenied.
    assert result[0] in {400, 403}, result[:2]
    assert b"WORM" in result[1] or b"AccessDenied" in result[1], result[1][:200]
    again = read_back_object_lock(
        endpoint=endpoint, bucket=bucket, key="wr1_example/7.json", transport=send, **_kw()
    )
    assert again.body == record


def test_a_wrong_secret_is_refused_and_http_endpoints_never_reach_the_network(store) -> None:
    endpoint, bucket, send = store
    with pytest.raises(WitnessRequiredUnavailableError, match="403"):
        put_object_lock(
            endpoint=endpoint,
            bucket=bucket,
            key="x/1.json",
            body=b"{}",
            access_key_id=USER,
            secret_access_key="wrong",
            region=REGION,
            transport=lambda r: send(r)[:2],
        )
    with pytest.raises(WitnessRequiredUnavailableError, match="https"):
        put_object_lock(
            endpoint=endpoint.replace("https://", "http://"),
            bucket=bucket,
            key="x/2.json",
            body=b"{}",
            **_kw(),
        )
    assert live_object_store_status({}) == LIVE_OBJECT_STORE_STATUS == "NOT_PROVISIONED"


def test_retention_headers_are_the_compliance_set() -> None:
    headers = object_lock_headers(retain_until=datetime.now(UTC) + timedelta(days=1))
    assert headers["x-amz-object-lock-mode"] == "COMPLIANCE" and headers["If-None-Match"] == "*"
