# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable operator ceremonies for explicitly opted-in customer qualification.

No private key leaves this process; nothing is enrolled for production. The
fixture signers authorize only this exact isolated deployment and inventory.
"""

import base64
import json
import os
import secrets
import subprocess
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from scripts.engineering.m13_bootstrap_authorization import (
    BootstrapManifest,
    register_signed_new_installation,
)
from scripts.engineering.m13_bootstrap_preflight import collect_bootstrap_store_evidence
from scripts.engineering.m13_bootstrap_publication import (
    PIN,
    publication_digest,
    publish_isolated_bootstrap,
)

from responsibleai.data_governance.tenant_controller import postgres_identity, store_b_identity
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.durable_intent import daemon_identity


def _write(path, value):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(value, stream, sort_keys=True)


@asynccontextmanager
async def authorized_disposable_installation(
    engine, provider, *, deployment_id, environment="development"
):
    with tempfile.TemporaryDirectory(prefix="wp-bootstrap-operators-") as directory:
        root = Path(directory).resolve()
        async with engine.raw.connect() as connection:
            identity = await postgres_identity(connection)
        roles = ("SECURITY_OWNER", "DEPLOYMENT_OPERATOR")
        keys = {role: Ed25519PrivateKey.generate() for role in roles}
        authorization = {
            "purpose": "NONPRODUCTION_BOOTSTRAP_QUALIFICATION",
            "installation_id": secrets.token_hex(32),
            "deployment_id": deployment_id,
            "environment": environment,
            "postgres_identity": identity,
            "store_b_identity": store_b_identity(provider),
            "registry": str(root / "independent-installation.sqlite3"),
            "operators": {
                role: {
                    "identity": "disposable-" + role.lower(),
                    "revoked": False,
                    "public_key": keys[role].public_key().public_bytes_raw().hex(),
                }
                for role in roles
            },
        }
        authorization_path = root / "authorization.json"
        _write(authorization_path, authorization)
        docker = DockerContainerBackend().docker_cmd
        inventory = subprocess.run(
            [docker, "ps", "--all", "--no-trunc", "--format", "{{json .}}"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        # Explicit disposable operator enrollment, not a runtime wildcard or a
        # production container-identity policy. Managed execution always refuses.
        publication = {
            "purpose": "ISOLATED_BOOTSTRAP_PUBLICATION_V1",
            "authorization_profile": str(authorization_path),
            "store_b_path": str(provider.path),
            "docker_identity": daemon_identity(docker),
            "infrastructure_ids": [
                json.loads(line)["ID"] for line in inventory.stdout.splitlines()
            ],
        }
        publication_path = root / "publication.json"
        _write(publication_path, publication)
        evidence = await collect_bootstrap_store_evidence(
            engine, provider, profile_path=authorization_path
        )
        now = int(time.time())
        manifest = BootstrapManifest(
            installation_id=authorization["installation_id"],
            deployment_id=deployment_id,
            environment=environment,
            postgres_identity=identity,
            store_b_identity=authorization["store_b_identity"],
            evidence_digest=publication_digest(evidence, publication),
            nonce=secrets.token_hex(32),
            created_at=now,
            expires_at=now + 240,
        )
        signatures = {
            authorization["operators"][role]["identity"]: base64.b64encode(
                keys[role].sign(manifest.canonical_bytes())
            ).decode("ascii")
            for role in roles
        }
        register_signed_new_installation(authorization_path, manifest, signatures)
        receipt = await publish_isolated_bootstrap(
            engine,
            provider,
            profile_path=publication_path,
            manifest=manifest,
            signatures=signatures,
        )
        with pytest.MonkeyPatch.context() as environment:
            environment.setenv(PIN, str(publication_path))
            yield receipt
