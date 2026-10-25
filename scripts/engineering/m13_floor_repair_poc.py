# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolated NONPRODUCTION advance-only floor experiment. NEVER publishes READY.

Not imported by the runtime, CLI, SDK or recovery controller. Separate-purpose
signatures and an independently retained witness are mandatory. Production
enrollment and rollback-resistant storage custody are not established here.
"""

import asyncio
import base64
import hashlib
import json
import re
import secrets
import sqlite3
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import text

from responsibleai.data_governance.operator_recovery import (
    RecoveryAuthorizationError,
    RecoveryReceiptLedger,
)
from responsibleai.data_governance.operator_recovery_control import (
    OperatorProfile,
    _control_connection,
    _digest,
    _exclusive_operation,
    _lock_authority_tables,
    _pg_snapshots,
    _store_b_snapshot,
    collect_recovery_evidence,
)
from responsibleai.data_governance.tenant_admission import verify_tenant_completion_evidence
from responsibleai.isolation.in_flight import InFlightExecutionRegistry

PLAN_DOMAIN = b"WHITEPACT-M13-NONPRODUCTION-FLOOR-REPAIR-V1\0"
ANCHOR_DOMAIN = b"WHITEPACT-M13-NONPRODUCTION-FLOOR-WITNESS-V1\0"


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def _verify(profile, payload, signatures):
    keys = tuple(key for key in profile.keys if key.revoked is False)
    if len(keys) != 2 or set(signatures) != {key.identity for key in keys}:
        raise RecoveryAuthorizationError("Exact distinct floor approvals required")
    try:
        for key in keys:
            Ed25519PublicKey.from_public_bytes(key.public_key).verify(
                base64.b64decode(signatures[key.identity], validate=True), payload
            )
    except Exception as exc:
        raise RecoveryAuthorizationError("Invalid floor approval") from exc


def _ledger(profile):
    return RecoveryReceiptLedger(profile.ledger_path.with_suffix(".floor-poc.sqlite3"))


def initialize(profile_path):
    """Explicit disposable ledger initialization; existing ledgers never reset."""
    profile = OperatorProfile.load(Path(profile_path))
    path = profile.ledger_path.with_suffix(".floor-poc.sqlite3")
    RecoveryReceiptLedger.initialize(path)
    with RecoveryReceiptLedger(path)._connect() as connection:
        connection.execute(
            "CREATE TABLE floor_witness (tenant TEXT PRIMARY KEY,payload TEXT NOT NULL,"
            "signatures TEXT NOT NULL,digest TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE floor_attempts (sequence INTEGER PRIMARY KEY AUTOINCREMENT,"
            "request_id TEXT UNIQUE NOT NULL,nonce TEXT UNIQUE NOT NULL,"
            "digest TEXT NOT NULL,state TEXT NOT NULL,details TEXT NOT NULL,final_digest TEXT)"
        )


async def witness(engine, provider, *, profile_path, tenant):
    """Read verified pre-rollback evidence; callers independently sign the result."""
    profile = OperatorProfile.load(Path(profile_path))
    evidence = await collect_recovery_evidence(engine, provider, profile)
    store = _store_b_snapshot(provider)
    lifecycle = provider.get_state(tenant)
    if lifecycle is None or lifecycle.state.value != "ACTIVE":
        raise RecoveryAuthorizationError("Established active tenant required")
    return {
        "purpose": "NONPRODUCTION_PRE_ROLLBACK_FLOOR_WITNESS",
        "profile": profile.digest,
        "tenant": tenant,
        "generation": lifecycle.generation_id,
        "store_identity": store["identity"],
        "lifecycle": _digest(store["lifecycle"]),
        "provisioning": _digest(store["provisioning"]),
        "readiness_epoch": store["epoch"],
        "floor": max(lifecycle.security_epoch, lifecycle.revocation_floor),
        "verified_source": _digest(evidence),
    }


def retain_witness(profile_path, payload, signatures):
    profile = OperatorProfile.load(Path(profile_path))
    if payload.get("profile") != profile.digest or payload.get("purpose") != (
        "NONPRODUCTION_PRE_ROLLBACK_FLOOR_WITNESS"
    ):
        raise RecoveryAuthorizationError("Wrong witness purpose or profile")
    encoded = ANCHOR_DOMAIN + _bytes(payload)
    _verify(profile, encoded, signatures)
    with _ledger(profile)._connect() as connection:
        connection.execute(
            "INSERT INTO floor_witness VALUES(?,?,?,?)",
            (
                payload["tenant"],
                _bytes(payload).decode(),
                json.dumps(signatures),
                hashlib.sha256(encoded).hexdigest(),
            ),
        )


@dataclass(frozen=True)
class FloorPlan:
    request_id: str
    nonce: str
    profile_digest: str
    tenant: str
    generation: str
    witness_digest: str
    evidence_digest: str
    expected_epoch: int
    target_epoch: int
    readiness_epoch: int
    created_at: int
    expires_at: int
    purpose: str = "NONPRODUCTION_ADVANCE_ONLY_FLOOR_REPAIR"

    def canonical_bytes(self):
        if self.purpose != "NONPRODUCTION_ADVANCE_ONLY_FLOOR_REPAIR":
            raise RecoveryAuthorizationError("Wrong floor repair purpose")
        for name in (
            "expected_epoch",
            "target_epoch",
            "readiness_epoch",
            "created_at",
            "expires_at",
        ):
            if type(getattr(self, name)) is not int or not 0 <= getattr(self, name) < 2**63:
                raise RecoveryAuthorizationError("Invalid floor plan integer")
        if (
            self.target_epoch <= self.expected_epoch
            or not 0 < self.expires_at - self.created_at <= 300
        ):
            raise RecoveryAuthorizationError("Advance-only short-lived floor plan required")
        for name, value in asdict(self).items():
            if name not in {
                "expected_epoch",
                "target_epoch",
                "readiness_epoch",
                "created_at",
                "expires_at",
            }:
                if type(value) is not str or not value or len(value) > 256:
                    raise RecoveryAuthorizationError("Invalid floor plan field")
        for name in ("request_id", "nonce", "profile_digest", "witness_digest", "evidence_digest"):
            if re.fullmatch(r"[0-9a-f]{64}", getattr(self, name)) is None:
                raise RecoveryAuthorizationError("Cryptographic floor identifier required")
        return PLAN_DOMAIN + _bytes(asdict(self))


async def _evidence(connection, engine, provider, profile, tenant, request_id=None):
    if (
        engine.raw.dialect.name != "postgresql"
        or engine.raw.url.host not in (None, "localhost", "127.0.0.1", "::1")
        or Path(provider.path) != profile.store_b_path
    ):
        raise RecoveryAuthorizationError("Exact local nonproduction targets required")
    identity = (
        await connection.execute(
            text(
                "SELECT current_database(),oid::text,(SELECT system_identifier::text FROM pg_control_system()) "
                "FROM pg_database WHERE datname=current_database()"
            )
        )
    ).one()
    if _digest(list(identity)) != profile.postgres_identity:
        raise RecoveryAuthorizationError("PostgreSQL target mismatch")
    snapshots, tenants = await _pg_snapshots(connection)
    store = _store_b_snapshot(provider)
    if store["state"] not in {"FAILED", "RESTORE_PENDING"}:
        raise RecoveryAuthorizationError("Durable quarantine required")
    with _ledger(profile)._connect() as ledger:
        row = ledger.execute(
            "SELECT payload,signatures,digest FROM floor_witness WHERE tenant=?", (tenant,)
        ).fetchone()
        history = ledger.execute(
            "SELECT request_id,nonce,digest,state,details,final_digest FROM floor_attempts "
            "WHERE request_id != ? ORDER BY sequence",
            (request_id or "",),
        ).fetchall()
    if any(record[3] not in {"FAILED", "COMPLETE"} for record in history):
        raise RecoveryAuthorizationError("Unfinished floor attempt requires independent review")
    with _control_connection(profile) as control:
        if control.execute(
            "SELECT 1 FROM recovery_operations WHERE phase != 'COMPLETE' LIMIT 1"
        ).fetchone():
            raise RecoveryAuthorizationError("Unfinished R1 recovery blocks floor repair")
    if row is None:
        raise RecoveryAuthorizationError("Independent pre-rollback witness missing")
    anchor, signatures, anchor_digest = json.loads(row[0]), json.loads(row[1]), row[2]
    encoded = ANCHOR_DOMAIN + _bytes(anchor)
    _verify(profile, encoded, signatures)
    if hashlib.sha256(encoded).hexdigest() != anchor_digest or any(
        (
            anchor["profile"] != profile.digest,
            anchor["tenant"] != tenant,
            anchor["store_identity"] != store["identity"],
            anchor["lifecycle"] != _digest(store["lifecycle"]),
            anchor["provisioning"] != _digest(store["provisioning"]),
            store["epoch"] < anchor["readiness_epoch"],
        )
    ):
        raise RecoveryAuthorizationError("Store B witness mismatch or rollback")
    record = provider.get_state(tenant)
    if (
        record is None
        or record.state.value != "ACTIVE"
        or record.generation_id != anchor["generation"]
    ):
        raise RecoveryAuthorizationError("Immutable established generation required")
    target = max(record.security_epoch, record.revocation_floor)
    if target != anchor["floor"]:
        raise RecoveryAuthorizationError("Witness floor differs")
    epoch = None
    for current in tenants:
        observed = await connection.scalar(
            text(
                "SELECT epoch FROM governance_revocation_epochs WHERE organization_id=:id AND scope='governance'"
            ),
            {"id": current},
        )
        if observed is None:
            raise RecoveryAuthorizationError("Established governance epoch missing")
        # This is a hypothetical post-repair validation, NEVER an admission call.
        # It proves every existing completion check except the intentionally
        # changed epoch. The actual database remains quarantined at observed.
        await verify_tenant_completion_evidence(
            connection, current, target if current == tenant else observed, provider
        )
        if current == tenant:
            epoch = observed
    if epoch is None or epoch >= target:
        raise RecoveryAuthorizationError("Exact advance-only mismatch required")
    registry = InFlightExecutionRegistry.get_instance()
    if registry.get_unresolved_containments() or any(
        registry.count_active(current) or registry.count_unresolved(current) for current in tenants
    ):
        raise RecoveryAuthorizationError("Unresolved work blocks floor repair")
    if await connection.scalar(
        text(
            "SELECT count(*) FROM runtime_execution_attempts WHERE state IN "
            "('ADMITTED','BACKEND_STARTING','RUNNING','UNCERTAIN') OR effect_state IN "
            "('EFFECT_STARTING','EFFECT_TRANSMITTING','EFFECT_UNCERTAIN')"
        )
    ):
        raise RecoveryAuthorizationError("Uncertain execution effect blocks floor repair")
    from responsibleai.isolation.container_backend import DockerContainerBackend
    from responsibleai.isolation.durable_intent import daemon_identity

    docker = DockerContainerBackend().docker_cmd
    if await asyncio.to_thread(daemon_identity, docker) != profile.docker_identity:
        raise RecoveryAuthorizationError("Docker identity mismatch")
    result = await asyncio.to_thread(
        subprocess.run,
        [docker, "ps", "--all", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True,
        text=True,
        timeout=10,
        check=True,
    )
    inventory = [json.loads(line) for line in result.stdout.splitlines()]
    if any(
        row.get("ID") not in profile.infrastructure_ids
        or "io.whitepact.execution=" in str(row.get("Labels", ""))
        or str(row.get("Names", "")).startswith("wp_iso_")
        for row in inventory
    ):
        raise RecoveryAuthorizationError("Unknown workload blocks floor repair")
    return {
        "epoch": epoch,
        "target": target,
        "generation": record.generation_id,
        "readiness_epoch": store["epoch"],
        "witness": anchor_digest,
        "snapshot": _digest([snapshots, store]),
        "history": _digest(history),
        "inventory": _digest(
            sorted(
                [
                    {
                        key: row.get(key)
                        for key in (
                            "ID",
                            "Names",
                            "Labels",
                            "State",
                            "Image",
                            "Mounts",
                            "Networks",
                            "Ports",
                        )
                    }
                    for row in inventory
                ],
                key=lambda row: row["ID"],
            )
        ),
    }


async def prepare(engine, provider, *, profile_path, tenant):
    profile = OperatorProfile.load(Path(profile_path))
    async with engine.raw.begin() as connection:
        evidence = await _evidence(connection, engine, provider, profile, tenant)
    now = int(time.time())
    return FloorPlan(
        secrets.token_hex(32),
        secrets.token_hex(32),
        profile.digest,
        tenant,
        evidence["generation"],
        evidence["witness"],
        _digest(evidence),
        evidence["epoch"],
        evidence["target"],
        evidence["readiness_epoch"],
        now,
        now + 120,
    )


async def _checkpoint(phase):
    """Observable crash boundary; tests may interrupt, never grant authority."""


async def execute(engine, provider, *, profile_path, plan, signatures):
    profile = OperatorProfile.load(Path(profile_path))
    if type(plan) is not FloorPlan:
        raise RecoveryAuthorizationError("Separate floor plan required")
    payload = plan.canonical_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    with _exclusive_operation(profile):
        try:
            with _ledger(profile)._connect() as ledger:
                ledger.execute(
                    "INSERT INTO floor_attempts(request_id,nonce,digest,state,details) VALUES(?,?,?,'CONSUMED',?)",
                    (
                        plan.request_id,
                        plan.nonce,
                        digest,
                        _bytes({"plan": asdict(plan), "signatures": signatures}).decode(),
                    ),
                )
        except sqlite3.IntegrityError as exc:
            raise RecoveryAuthorizationError("Floor approval already consumed") from exc
        await _checkpoint("CONSUMED")
        try:
            _verify(profile, payload, signatures)
            if (
                plan.profile_digest != profile.digest
                or not plan.created_at <= int(time.time()) < plan.expires_at
            ):
                raise RecoveryAuthorizationError("Stale or wrong-target floor approval")
            async with engine.raw.begin() as connection:
                await _lock_authority_tables(connection)
                store_lock = sqlite3.connect(str(provider.path), timeout=1)
                try:
                    store_lock.execute("BEGIN IMMEDIATE")
                    evidence = await _evidence(
                        connection, engine, provider, profile, plan.tenant, plan.request_id
                    )
                    if _digest(evidence) != plan.evidence_digest:
                        raise RecoveryAuthorizationError("Signed floor evidence changed")
                    if (
                        evidence["epoch"],
                        evidence["target"],
                        evidence["generation"],
                        evidence["witness"],
                        evidence["readiness_epoch"],
                    ) != (
                        plan.expected_epoch,
                        plan.target_epoch,
                        plan.generation,
                        plan.witness_digest,
                        plan.readiness_epoch,
                    ):
                        raise RecoveryAuthorizationError("Exact floor binding mismatch")
                    changed = await connection.execute(
                        text(
                            "UPDATE governance_revocation_epochs SET epoch=:target WHERE organization_id=:id "
                            "AND scope='governance' AND epoch=:expected AND epoch<:target"
                        ),
                        {
                            "target": plan.target_epoch,
                            "id": plan.tenant,
                            "expected": plan.expected_epoch,
                        },
                    )
                    if changed.rowcount != 1:
                        raise RecoveryAuthorizationError("Floor CAS refused")
                    await _checkpoint("PG_UNCOMMITTED")
                finally:
                    store_lock.rollback()
                    store_lock.close()
            await _checkpoint("PG_COMMITTED")
            # Existing strict R1 PREPARE checks must now succeed independently;
            # this read-only proof neither runs recovery nor publishes READY.
            evidence = await collect_recovery_evidence(engine, provider, profile)
            with _ledger(profile)._connect() as ledger:
                ledger.execute(
                    "UPDATE floor_attempts SET state='COMPLETE',final_digest=? WHERE request_id=?",
                    (_digest(evidence), plan.request_id),
                )
            return {"state": "FLOOR_ADVANCED", "epoch": plan.target_epoch, "ready": False}
        except BaseException:
            with _ledger(profile)._connect() as ledger:
                ledger.execute(
                    "UPDATE floor_attempts SET state='FAILED' WHERE request_id=?",
                    (plan.request_id,),
                )
            raise
