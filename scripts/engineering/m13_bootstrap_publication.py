# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit isolated NONPRODUCTION bootstrap publisher; no public entry point.

The external private operator profile is the trust boundary, not an application
session. Local files model independently administered custody for qualification;
they do not establish production or whole-host rollback resistance.
"""

import asyncio
import fcntl
import hashlib
import json
import os
import re
import sqlite3
import stat
import subprocess
from pathlib import Path

from scripts.engineering.m13_bootstrap_authorization import (
    BootstrapManifest,
    BootstrapRefusedError,
    _private_file,
    _profile,
    _registry,
    _unique_object,
    _verify,
    consume_bootstrap_approval,
)
from scripts.engineering.m13_bootstrap_preflight import collect_bootstrap_store_evidence
from sqlalchemy import text

from responsibleai.data_governance.tenant_controller import store_b_identity
from responsibleai.environment import is_production
from responsibleai.isolation.durable_intent import daemon_identity
from responsibleai.isolation.in_flight import InFlightExecutionRegistry

PIN = "WHITEPACT_NONPRODUCTION_BOOTSTRAP_PROFILE"


def publication_digest(store_evidence, profile):
    """Versioned signature binding includes the exact trusted inventory policy."""
    value = {
        "format": "BOOTSTRAP-PUBLICATION-EVIDENCE-V1",
        "stores": store_evidence,
        "publication_policy": profile,
    }
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")
    ).hexdigest()


def publication_profile(path):
    if is_production():
        raise BootstrapRefusedError("Production bootstrap publication is unavailable")
    with os.fdopen(_private_file(path)) as stream:
        profile = json.load(stream, object_pairs_hook=_unique_object)
    if (
        set(profile)
        != {
            "purpose",
            "authorization_profile",
            "store_b_path",
            "docker_identity",
            "infrastructure_ids",
        }
        or profile["purpose"] != "ISOLATED_BOOTSTRAP_PUBLICATION_V1"
    ):
        raise BootstrapRefusedError("Invalid publication trust profile")
    if (
        type(profile["infrastructure_ids"]) is not list
        or len(set(profile["infrastructure_ids"])) != len(profile["infrastructure_ids"])
        or any(
            type(cid) is not str or re.fullmatch(r"[0-9a-f]{64}", cid) is None
            for cid in profile["infrastructure_ids"]
        )
    ):
        raise BootstrapRefusedError("Exact enrolled infrastructure identities required")
    for name in ("authorization_profile", "store_b_path"):
        if not Path(profile[name]).is_absolute():
            raise BootstrapRefusedError("Absolute pinned target paths required")
    return profile


def _inventory(profile):
    from responsibleai.isolation.container_backend import DockerContainerBackend

    docker = DockerContainerBackend().docker_cmd
    if daemon_identity(docker) != profile["docker_identity"]:
        raise BootstrapRefusedError("Bootstrap Docker target changed")
    result = subprocess.run(
        [docker, "ps", "--all", "--no-trunc", "--format", "{{json .}}"],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    rows = [json.loads(line) for line in result.stdout.splitlines()]
    if any(
        row.get("ID") not in profile["infrastructure_ids"]
        or "io.whitepact.execution=" in str(row.get("Labels", ""))
        or str(row.get("Names", "")).startswith("wp_iso_")
        for row in rows
    ):
        raise BootstrapRefusedError("Unknown or execution workload blocks bootstrap")
    registry = InFlightExecutionRegistry.get_instance()
    if registry.count_active() or registry.get_unresolved_containments():
        raise BootstrapRefusedError("Unresolved containment blocks bootstrap")


async def publish_isolated_bootstrap(engine, provider, *, profile_path, manifest, signatures):
    """Publish once, with exclusive locks and external completion before admission.

    Signers authorize only a new empty installation. Tenant generation, consent,
    root authority and execution grants are NOT created by this operation.
    """
    profile = publication_profile(profile_path)
    authorization = _profile(profile["authorization_profile"])
    if Path(provider.path) != Path(profile["store_b_path"]):
        raise BootstrapRefusedError("Store B path substitution")
    digest = _verify(authorization, manifest, signatures)
    descriptor = os.open(
        authorization["registry"] + ".bootstrap-lock",
        os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW,
        0o600,
    )
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise BootstrapRefusedError("Unprotected bootstrap operation lock")
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        evidence = await collect_bootstrap_store_evidence(
            engine, provider, profile_path=profile["authorization_profile"]
        )
        if publication_digest(evidence, profile) != manifest.evidence_digest:
            raise BootstrapRefusedError("Signed bootstrap publication evidence changed")
        await asyncio.to_thread(_inventory, profile)
        async with engine.raw.begin() as connection:
            names = (
                (
                    await connection.execute(
                        text(
                            "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"
                        )
                    )
                )
                .scalars()
                .all()
            )
            for name in names:
                if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                    raise BootstrapRefusedError("Invalid database table identity")
                await connection.execute(
                    text(f'LOCK TABLE public."{name}" IN ACCESS EXCLUSIVE MODE')
                )
                if name != "alembic_version" and await connection.scalar(
                    text(f'SELECT count(*) FROM public."{name}"')
                ):
                    raise BootstrapRefusedError("Bootstrap source history changed")
            store = provider._get_connection()
            try:
                store.execute("BEGIN IMMEDIATE")
                tables = [
                    row[0]
                    for row in store.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    )
                ]
                for name in tables:
                    if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name) is None:
                        raise BootstrapRefusedError("Invalid durable table identity")
                    if store.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]:
                        raise BootstrapRefusedError("Bootstrap durable history changed")
                consume_bootstrap_approval(profile["authorization_profile"], manifest, signatures)
                with _registry(authorization) as external:
                    external.execute(
                        "CREATE TABLE bootstrap_publication(id INTEGER PRIMARY KEY CHECK(id=1),"
                        "digest TEXT NOT NULL,signatures TEXT NOT NULL,phase TEXT NOT NULL,evidence TEXT NOT NULL)"
                    )
                    external.execute(
                        "INSERT INTO bootstrap_publication VALUES(1,?,?, 'CONSUMED',?)",
                        (
                            digest,
                            json.dumps(signatures, sort_keys=True),
                            json.dumps(evidence, sort_keys=True),
                        ),
                    )
                    external.execute(
                        "CREATE TABLE bootstrap_recovery_fence(id INTEGER PRIMARY KEY CHECK(id=1),"
                        "required INTEGER NOT NULL CHECK(required IN (0,1)))"
                    )
                    external.execute("INSERT INTO bootstrap_recovery_fence VALUES(1,0)")
                # No generic READY setter. Initial publication is absent-only,
                # and admission remains fenced by the external CONSUMED state.
                store.execute(
                    "CREATE TABLE bootstrap_installation_binding(id INTEGER PRIMARY KEY CHECK(id=1),"
                    "profile_path TEXT NOT NULL,digest TEXT NOT NULL)"
                )
                store.execute(
                    "INSERT INTO bootstrap_installation_binding VALUES(1,?,?)",
                    (str(Path(profile_path).resolve()), digest),
                )
                store.execute(
                    "INSERT INTO durable_restore_readiness(key,state,epoch,updated_at,updated_by) "
                    "VALUES('global','READY',1,?,?)",
                    (str(manifest.created_at), "signed-isolated-bootstrap:" + digest),
                )
                store.commit()
            finally:
                store.close()
        await asyncio.to_thread(_inventory, profile)
        with _registry(authorization) as external:
            if (
                external.execute(
                    "UPDATE bootstrap_publication SET phase='COMPLETE' WHERE id=1 AND phase='CONSUMED' AND digest=?",
                    (digest,),
                ).rowcount
                != 1
            ):
                raise BootstrapRefusedError("Bootstrap completion changed")
        verify_isolated_bootstrap_binding(provider, profile_path=profile_path)
        return {"state": "READY_VERIFIED", "manifest_digest": digest, "production": False}
    finally:
        os.close(descriptor)


def verify_isolated_bootstrap_binding(provider, *, profile_path=None):
    """Check retained signatures, consumed nonce and both completion records.

    Called on every readiness read when a binding or pinned profile is present.
    An interrupted publication is never interpreted as usable readiness.
    """
    with sqlite3.connect(f"file:{provider.path}?mode=ro", uri=True) as store:
        exists = store.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bootstrap_installation_binding'"
        ).fetchone()
        binding = (
            store.execute(
                "SELECT profile_path,digest FROM bootstrap_installation_binding WHERE id=1"
            ).fetchone()
            if exists
            else None
        )
        pinned = profile_path or os.environ.get(PIN)
        if not binding and not pinned:
            return False
        if not binding or (pinned and Path(pinned).resolve() != Path(binding[0])):
            raise BootstrapRefusedError("Bootstrap binding missing or substituted")
        profile = publication_profile(binding[0])
        if Path(provider.path) != Path(profile["store_b_path"]):
            raise BootstrapRefusedError("Bootstrap Store B substituted")
        authorization = _profile(profile["authorization_profile"])
        if (
            store_b_identity(provider) != authorization["store_b_identity"]
            or not provider.verify_integrity()
        ):
            raise BootstrapRefusedError("Bootstrap Store B identity or integrity changed")
        with _registry(authorization) as external:
            row = external.execute(
                "SELECT i.digest,i.manifest,i.state,i.consumed_nonce,p.signatures,p.phase,p.evidence "
                "FROM installation i JOIN bootstrap_publication p ON p.id=1 AND p.digest=i.digest "
                "WHERE i.id=?",
                (authorization["installation_id"],),
            ).fetchone()
            fence = external.execute(
                "SELECT required FROM bootstrap_recovery_fence WHERE id=1"
            ).fetchone()
        if (
            not row
            or row[0] != binding[1]
            or row[2] != "BOOTSTRAP_AUTHORIZED"
            or row[5] != "COMPLETE"
        ):
            raise BootstrapRefusedError("Bootstrap publication incomplete or rolled back")
        payload = bytes(row[1])
        from scripts.engineering.m13_bootstrap_authorization import DOMAIN

        manifest = BootstrapManifest(**json.loads(payload[len(DOMAIN) :]))
        if (
            not payload.startswith(DOMAIN)
            or payload != manifest.canonical_bytes()
            or hashlib.sha256(payload).hexdigest() != binding[1]
            or manifest.nonce != row[3]
        ):
            raise BootstrapRefusedError("Bootstrap receipt changed")
        _verify(authorization, manifest, json.loads(row[4]), now=manifest.created_at)
        if publication_digest(json.loads(row[6]), profile) != manifest.evidence_digest:
            raise BootstrapRefusedError("Bootstrap publication policy or evidence changed")
        readiness = store.execute(
            "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
        ).fetchone()
        if not readiness or readiness[1] < 1:
            raise BootstrapRefusedError("Bootstrap readiness missing or rolled back")
        if fence not in ((0,), (1,)):
            raise BootstrapRefusedError("External bootstrap recovery fence missing")
        if fence == (1,) and readiness[0] == "READY":
            from responsibleai.data_governance.operator_recovery_control import (
                assert_completed_binding,
            )

            if not assert_completed_binding(provider):
                raise BootstrapRefusedError("Signed R1 recovery required after bootstrap incident")
    return True


def fence_isolated_bootstrap_recovery(provider):
    """External monotonic fence precedes every restrictive Store B write.

    Rolling Store B back to the original bootstrap READY receipt cannot erase a
    later incident. This never authorizes R1 or changes its trust requirements.
    """
    with sqlite3.connect(f"file:{provider.path}?mode=ro", uri=True) as store:
        exists = store.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='bootstrap_installation_binding'"
        ).fetchone()
        if not exists:
            return
        binding = store.execute(
            "SELECT profile_path FROM bootstrap_installation_binding WHERE id=1"
        ).fetchone()
    if not binding:
        raise BootstrapRefusedError("Bootstrap incident binding missing")
    profile = publication_profile(binding[0])
    authorization = _profile(profile["authorization_profile"])
    with _registry(authorization) as external:
        if (
            external.execute("UPDATE bootstrap_recovery_fence SET required=1 WHERE id=1").rowcount
            != 1
        ):
            raise BootstrapRefusedError("External incident fence unavailable")
