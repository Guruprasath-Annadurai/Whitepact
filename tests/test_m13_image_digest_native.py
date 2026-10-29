# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual Docker + disposable loopback OCI registry; never production approval."""

import hashlib
import json
import os
import subprocess
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from responsibleai.isolation.image_admission import (
    ImageAdmissionError,
    admit_image,
    verify_container_image,
)

REGISTRY_IMAGE = (
    "registry:2.8.3@sha256:a3d8aaa63ed8681a604f1dea0aa03f100d5895b6a58ace528858a7b332415373"
)


def docker(*args):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=True, timeout=90
    ).stdout.strip()


def ready(port):
    for _ in range(80):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/v2/", timeout=1) as response:
                if response.status == 200:
                    return
        except (OSError, ValueError):
            pass
        time.sleep(0.1)
    pytest.fail("Disposable loopback registry did not become ready")


@pytest.fixture
def registry(real_container_host, monkeypatch):
    image = os.environ["WHITEPACT_TEST_RUNTIME_IMAGE"]
    assert image.startswith("sha256:") and len(image) == 71
    cid = docker("run", "-d", "-p", "127.0.0.1::5000", REGISTRY_IMAGE)
    try:
        port = json.loads(docker("inspect", cid))[0]["NetworkSettings"]["Ports"]["5000/tcp"][0][
            "HostPort"
        ]
        ready(port)
        tag = f"localhost:{port}/runtime:qualified"
        docker("tag", image, tag)
        docker("push", tag)
        refs = json.loads(docker("image", "inspect", tag))[0]["RepoDigests"]
        ref = next(r for r in refs if r.startswith(f"localhost:{port}/runtime@sha256:"))
        monkeypatch.setenv(
            "WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({ref: image, image: image})
        )
        yield {"image": image, "ref": ref, "cid": cid, "port": port, "tag": tag}
    finally:
        subprocess.run(["docker", "rm", "-f", cid], capture_output=True, timeout=20, check=False)


def test_real_registry_admission_and_stopped_container_binding(registry):
    admitted = admit_image("docker", registry["ref"])
    assert admitted.image_id == registry["image"]
    cid = docker(
        "create",
        "--pull=never",
        "--network=none",
        "--read-only",
        "--user=65534:65534",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges:true",
        admitted.image_id,
        "python3",
        "-c",
        'print("APPROVED_CONTENT_ONLY")',
    )
    try:
        verify_container_image("docker", cid, admitted)
        assert docker("start", "--attach", cid) == "APPROVED_CONTENT_ONLY"
        assert json.loads(docker("inspect", cid))[0]["Image"] == admitted.image_id
    finally:
        docker("rm", "-f", cid)


def test_real_registry_outage_does_not_fall_back_to_approved_cached_id(registry):
    assert admit_image("docker", registry["ref"]).image_id == registry["image"]
    docker("stop", registry["cid"])
    with pytest.raises(ImageAdmissionError):
        admit_image("docker", registry["ref"])
    docker("start", registry["cid"])
    ready(registry["port"])
    assert admit_image("docker", registry["ref"]).image_id == registry["image"]


def test_real_mutated_tag_cannot_change_pinned_admission(registry, monkeypatch):
    cid = docker("create", registry["image"], "python3", "-c", 'print("not started")')
    try:
        changed = docker(
            "commit", "--change", "LABEL whitepact.adversarial=substitution", cid, registry["tag"]
        )
        docker("push", registry["tag"])
        assert changed != registry["image"]
        # The tag moved; the approved manifest/content pair still selects old bytes.
        assert admit_image("docker", registry["ref"]).image_id == registry["image"]
        with pytest.raises(ImageAdmissionError):
            admit_image("docker", registry["tag"])
        refs = json.loads(docker("image", "inspect", registry["tag"]))[0]["RepoDigests"]
        substituted = next(
            r
            for r in refs
            if r.startswith(f"localhost:{registry['port']}/runtime@") and r != registry["ref"]
        )
        assert substituted != registry["ref"]
        monkeypatch.setenv(
            "WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({substituted: registry["image"]})
        )
        with pytest.raises(ImageAdmissionError):
            admit_image("docker", substituted)
    finally:
        docker("rm", "-f", cid)


def test_actual_registry_manifest_body_substitution_is_refused(registry, monkeypatch):
    original_digest = registry["ref"].split("@")[1]
    req = urllib.request.Request(
        f"http://127.0.0.1:{registry['port']}/v2/runtime/manifests/{original_digest}",
        headers={
            "Accept": ",".join(
                (
                    "application/vnd.docker.distribution.manifest.v2+json",
                    "application/vnd.docker.distribution.manifest.list.v2+json",
                    "application/vnd.oci.image.manifest.v1+json",
                    "application/vnd.oci.image.index.v1+json",
                )
            )
        },
    )
    with urllib.request.urlopen(req, timeout=5) as response:
        original = response.read()
        manifest_media_type = response.headers["Content-Type"]
    # A valid differently serialized manifest gives an uncached approved digest.
    # The adversarial server then substitutes different bytes for that digest.
    intended = json.dumps(json.loads(original), indent=2).encode()
    digest = "sha256:" + hashlib.sha256(intended).hexdigest()
    assert digest != original_digest
    payload = json.loads(original)
    payload["annotations"] = {"adversarial": "different manifest bytes"}
    altered = json.dumps(payload, separators=(",", ":")).encode()
    assert "sha256:" + hashlib.sha256(altered).hexdigest() != digest
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            self.respond(False)

        def do_HEAD(self):
            self.respond(True)

        def respond(self, head):
            if self.path.rstrip("/") == "/v2":
                body = b"{}"
                kind = "application/json"
            elif "/manifests/" in self.path:
                requests.append(self.command)
                body = altered
                kind = manifest_media_type
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Docker-Distribution-Api-Version", "registry/2.0")
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Docker-Content-Digest", digest)
            self.end_headers()
            if not head:
                self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        ref = f"localhost:{server.server_port}/runtime@{digest}"
        monkeypatch.setenv(
            "WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({ref: registry["image"]})
        )
        with pytest.raises(ImageAdmissionError):
            admit_image("docker", ref)
        assert "GET" in requests, "The actual Docker client must fetch the substituted manifest"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["approval_removed", "audit_write_outage"])
async def test_backend_cannot_start_after_real_creation_if_approval_is_removed(
    registry, tmp_path, monkeypatch, fault
):
    import uuid
    from datetime import UTC, datetime, timedelta

    from responsibleai.enterprise.runtime import configure_enterprise
    from responsibleai.isolation.container_backend import DockerContainerBackend
    from responsibleai.isolation.models import IsolatedExecutionRequest, IsolationProfile
    from tests.protected_component_tenant import (
        component_controller,
        provision_component_organization,
    )

    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    async with component_controller(tmp_path, monkeypatch, "digest") as controller:
        configure_enterprise(controller.engine)
        org = await provision_component_organization(
            controller.engine, name="Digest test", slug="digest-" + uuid.uuid4().hex[:8]
        )
        backend = DockerContainerBackend(image_name=registry["ref"])
        create = backend._create_stopped_container
        created = []

        def revoke_after_create(command, receipt):
            cid = create(command, receipt)
            created.append(cid)
            if fault == "approval_removed":
                monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", "{}")
            else:
                from responsibleai.enterprise.audit import EnterpriseAuditLog

                original = EnterpriseAuditLog.record

                async def refuse_image_record(self, **kwargs):
                    if kwargs.get("action") == "isolation.image.bound":
                        raise OSError("injected image-evidence database outage")
                    return await original(self, **kwargs)

                monkeypatch.setattr(EnterpriseAuditLog, "record", refuse_image_record)
            return cid

        monkeypatch.setattr(backend, "_create_stopped_container", revoke_after_create)
        request = IsolatedExecutionRequest(
            action_id="digest-denial",
            organization_id=org.id,
            action_type="rai_scan",
            arguments={"text": "TEST_ONLY"},
            profile=IsolationProfile(),
            authorization_id=uuid.uuid4().hex,
            action_digest="ab" * 32,
            authorization_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            admission_epoch=1,
        )
        with pytest.raises(ImageAdmissionError if fault == "approval_removed" else OSError):
            await backend.execute(request)
        assert len(created) == 1
        # A real stopped container was created, but the START boundary refused it.
        assert not docker("ps", "-q", "--filter", f"id={created[0]}")
