# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Nonproduction offline recovery controller and hosted enforcement boundary.

No public route or application credential can create a session here. The local
operator profile is trusted host configuration, outside Store A's restore domain.
Production enrollment/activation is intentionally unsupported in this candidate.
"""

from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import math
import os
import secrets
import sqlite3
import stat
import subprocess
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from datetime import time as wall_time
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select, text
from sqlalchemy.sql.elements import quoted_name

from responsibleai.data_governance.operator_recovery import (
    OperatorKey,
    RecoveryAuthorizationError,
    RecoveryManifest,
    RecoveryReceiptLedger,
    verify_operator_approvals,
)
from responsibleai.environment import resolve
from responsibleai.isolation.mode import unisolated_execution_allowed

_TABLES = tuple(
    sorted(
        {
            "organizations",
            "tenant_provisioning_records",
            "tenant_provisioning_outbox",
            "tenant_tombstones",
            "governance_revocation_epochs",
            "governance_execution_authorizations",
            "governance_execution_nonces",
            "runtime_containment_records",
            "restore_reconciliation_records",
            "governance_root_authority_records",
            "governance_consent_proofs",
            "governance_delegations",
            "governance_approvals",
            "governance_approval_votes",
            "web_memberships",
            "org_api_keys",
            "org_api_key_metadata",
            "iam_api_key_lineage",
            "iam_sessions",
            "web_sessions",
            "runtime_execution_requests",
            "runtime_execution_attempts",
            "runtime_execution_dispatch_outbox",
            "runtime_execution_fences",
            "runtime_worker_leases",
            "governance_policies",
            "governance_policy_activations",
            "governance_policy_history",
            "governance_policy_revisions",
            "governance_policy_versions",
        }
    )
)


class RecoveryInProgressError(RecoveryAuthorizationError):
    """A durable unfinished operation fences admission without a competing write."""


EVIDENCE_FORMAT = "WHITEPACT-PG-RECOVERY-EVIDENCE-V2"
_EVIDENCE_REQUEST_PREFIX = "pg-evidence-v2:"


def _require_manifest_format(manifest: RecoveryManifest) -> None:
    # Version is signature-bound without changing the fixed manifest schema.
    # Historical controllers emitted only unprefixed hexadecimal request IDs.
    suffix = manifest.request_id.removeprefix(_EVIDENCE_REQUEST_PREFIX)
    if (
        not manifest.request_id.startswith(_EVIDENCE_REQUEST_PREFIX)
        or len(suffix) != 32
        or any(character not in "0123456789abcdef" for character in suffix)
    ):
        raise RecoveryAuthorizationError("Historical signed evidence format requires review")


def _require_completed_evidence(row: Mapping[str, Any], manifest: RecoveryManifest) -> None:
    """Receipt metadata cannot relabel older signed evidence as V2."""
    try:
        approved = json.loads(row["approved_evidence"])
        valid = (
            type(approved) is dict
            and approved.get("evidence_format") == EVIDENCE_FORMAT
            and _digest(approved) == manifest.evidence_digest
        )
    except (KeyError, TypeError, ValueError):
        valid = False
    if not valid:
        raise RecoveryAuthorizationError("Signed recovery evidence format or digest changed")


def enforcement_required() -> bool:
    return not unisolated_execution_allowed()


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()


def _timezone_value(value: datetime | wall_time) -> Any:
    zone = value.tzinfo
    if zone is None:
        return ["naive"]
    if type(zone) not in (timezone, ZoneInfo):
        raise RecoveryAuthorizationError("Unsupported recovery-evidence timezone")
    offset = value.utcoffset()
    if offset is None:
        raise RecoveryAuthorizationError("Ambiguous recovery-evidence timezone")
    micros = ((offset.days * 86400 + offset.seconds) * 1000000) + offset.microseconds
    if type(zone) is timezone:
        return ["fixed", micros, value.tzname()]
    if type(zone) is ZoneInfo:
        return ["iana", zone.key, micros]
    raise RecoveryAuthorizationError("Unsupported recovery-evidence timezone")


def _evidence_value(value: Any) -> Any:
    """V2 injective type tree; never stringify unknown authoritative values.

    Naive timestamps remain explicitly naive, never interpreted as local/UTC.
    Aware timestamps preserve their offset, zone identity and fold. Numeric
    scale/sign and binary octets are retained. Every container is tagged so a
    JSON value cannot impersonate a typed value or a version envelope.
    """
    kind = type(value)
    if value is None:
        return ["null"]
    if kind is bool:
        return ["bool", value]
    if kind is int:
        return ["int", value]
    if kind is float:
        if not math.isfinite(value):
            raise RecoveryAuthorizationError("Nonfinite recovery-evidence float")
        return ["float", value]
    if kind is str:
        return ["str", value]
    if kind is bytes:
        return ["bytes", value.hex()]
    if isinstance(value, UUID):
        if kind is not UUID:
            # asyncpg returns its exact known UUID adapter for native PG UUIDs.
            # Unknown subclasses are not allowed to supply custom encodings.
            try:
                from asyncpg.pgproto.pgproto import UUID as POSTGRES_UUID
            except ImportError:
                raise RecoveryAuthorizationError(
                    "Unsupported recovery-evidence UUID adapter"
                ) from None
            if kind is not POSTGRES_UUID:
                raise RecoveryAuthorizationError("Unsupported recovery-evidence UUID adapter")
        return ["uuid", value.hex]
    if kind is Decimal:
        if not value.is_finite():
            raise RecoveryAuthorizationError("Nonfinite recovery-evidence decimal")
        parts = value.as_tuple()
        return ["decimal", parts.sign, list(parts.digits), parts.exponent]
    if kind is datetime:
        zone = _timezone_value(value)
        return [
            "datetime",
            value.isoformat(timespec="microseconds"),
            value.fold,
            zone,
        ]
    if kind is date:
        return ["date", value.isoformat()]
    if kind is wall_time:
        zone = _timezone_value(value)
        return [
            "time",
            value.isoformat(timespec="microseconds"),
            value.fold,
            zone,
        ]
    if kind is timedelta:
        return ["timedelta", value.days, value.seconds, value.microseconds]
    if kind is list:
        return ["list", [_evidence_value(item) for item in value]]
    if kind is tuple:
        return ["tuple", [_evidence_value(item) for item in value]]
    if kind is dict:
        if any(type(key) not in (str, quoted_name) for key in value):
            raise RecoveryAuthorizationError("Nonstring recovery-evidence field")
        # SQLAlchemy's known metadata adapter carries quoting policy, not a
        # different database field name. Preserve its exact string contents.
        return ["map", [[str.__str__(key), _evidence_value(value[key])] for key in sorted(value)]]
    raise RecoveryAuthorizationError("Unsupported recovery-evidence value type")


def _evidence_bytes(value: Any) -> bytes:
    return json.dumps(
        _evidence_value(value),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")


def _snapshot_digest(records: list[dict[str, Any]]) -> str:
    # Sorting and digesting use exactly the same canonical row bytes.
    rows = sorted(_evidence_bytes(record) for record in records)
    envelope = b'{"format":' + json.dumps(EVIDENCE_FORMAT).encode("ascii") + b',"rows":['
    return hashlib.sha256(envelope + b",".join(rows) + b"]}").hexdigest()


def _private_json(path: Path) -> dict[str, Any]:
    if not path.is_absolute() or path.resolve() != path:
        raise RecoveryAuthorizationError("Operator configuration requires a canonical path")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_nlink != 1
        ):
            raise RecoveryAuthorizationError("Operator configuration is not private")
        data = os.read(descriptor, 65537)
        if len(data) > 65536:
            raise RecoveryAuthorizationError("Operator configuration exceeds bound")
    finally:
        os.close(descriptor)

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise RecoveryAuthorizationError("Duplicate configuration field")
            result[key] = value
        return result

    result = json.loads(data, object_pairs_hook=unique)
    if not isinstance(result, dict):
        raise RecoveryAuthorizationError("Invalid operator configuration")
    return result


@dataclass(frozen=True)
class OperatorProfile:
    path: Path
    digest: str
    deployment_id: str
    environment: str
    incident_id: str
    postgres_identity: str
    store_b_path: Path
    ledger_path: Path
    docker_identity: str
    infrastructure_ids: tuple[str, ...]
    keys: tuple[OperatorKey, ...]

    @classmethod
    def load(cls, path: Path) -> OperatorProfile:
        pinned = os.environ.get("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG")
        if pinned is None or Path(pinned) != path:
            raise RecoveryAuthorizationError("Operator trust path is not pinned by the host")
        data = _private_json(path)
        expected = {
            "purpose",
            "deployment_id",
            "environment",
            "incident_id",
            "postgres_identity",
            "store_b_path",
            "ledger_path",
            "docker_identity",
            "infrastructure_ids",
            "keys",
        }
        if set(data) != expected or data["purpose"] != "NONPRODUCTION_RECOVERY_QUALIFICATION":
            raise RecoveryAuthorizationError("Unapproved operator profile")
        actual = resolve()
        if actual.is_production or actual.name != data["environment"]:
            raise RecoveryAuthorizationError("Production recovery activation is not authorized")
        if any(
            not isinstance(data[name], str) or not data[name]
            for name in expected - {"keys", "infrastructure_ids"}
        ):
            raise RecoveryAuthorizationError("Invalid operator profile field")
        for name in ("store_b_path", "ledger_path"):
            value = Path(data[name])
            if not value.is_absolute() or value.resolve() != value:
                raise RecoveryAuthorizationError("Recovery stores require canonical paths")
        if data["store_b_path"] == data["ledger_path"]:
            raise RecoveryAuthorizationError("Receipt ledger must be separate from Store B")
        keys = tuple(
            OperatorKey(
                identity=key["identity"],
                role=key["role"],
                public_key=bytes.fromhex(key["public_key"]),
                revoked=key["revoked"],
            )
            for key in data["keys"]
        )
        active = [key for key in keys if key.revoked is False]
        if (
            len(active) != 2
            or {key.role for key in active} != {"SECURITY_OWNER", "RECOVERY_OPERATOR"}
            or len({key.identity for key in keys}) != len(keys)
            or len({key.public_key for key in active}) != 2
            or any(len(key.public_key) != 32 or type(key.revoked) is not bool for key in keys)
        ):
            raise RecoveryAuthorizationError("Exact independently enrolled operator roles required")
        ids = data["infrastructure_ids"]
        if not isinstance(ids, list) or any(
            not isinstance(item, str) or len(item) != 64 for item in ids
        ):
            raise RecoveryAuthorizationError("Explicit immutable infrastructure IDs required")
        return cls(
            path,
            _digest(data),
            data["deployment_id"],
            data["environment"],
            data["incident_id"],
            data["postgres_identity"],
            Path(data["store_b_path"]),
            Path(data["ledger_path"]),
            data["docker_identity"],
            tuple(ids),
            keys,
        )


@contextmanager
def _control_connection(profile: OperatorProfile) -> Iterator[sqlite3.Connection]:
    with RecoveryReceiptLedger(profile.ledger_path)._connect() as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(recovery_operations)")}
        if (
            not {"evidence_format", "approved_evidence"}.issubset(columns)
            or connection.execute(
                "SELECT 1 FROM recovery_operations WHERE evidence_format != ? "
                "OR evidence_format IS NULL LIMIT 1",
                (EVIDENCE_FORMAT,),
            ).fetchone()
        ):
            raise RecoveryAuthorizationError("Historical recovery evidence format requires review")
        yield connection


def initialize_control_ledger(path: Path) -> None:
    """Explicit disposable/nonproduction provisioning only; no existing-file reset."""
    RecoveryReceiptLedger.initialize(path)
    with RecoveryReceiptLedger(path)._connect() as connection:
        connection.execute(
            "CREATE TABLE recovery_operations (epoch INTEGER PRIMARY KEY AUTOINCREMENT, "
            "request_id TEXT NOT NULL UNIQUE, manifest TEXT NOT NULL, signatures TEXT NOT NULL, "
            "profile_digest TEXT NOT NULL, phase TEXT NOT NULL, store_b_epoch INTEGER, "
            "final_digest TEXT, evidence_format TEXT NOT NULL, approved_evidence TEXT NOT NULL)"
        )


def _latest(profile: OperatorProfile):
    with _control_connection(profile) as connection:
        connection.row_factory = sqlite3.Row
        return connection.execute(
            "SELECT * FROM recovery_operations ORDER BY epoch DESC LIMIT 1"
        ).fetchone()


def record_restrictive_failure() -> None:
    """Persist only quarantine, never operator approval or recovery authority."""
    pinned = os.environ.get("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG")
    if not pinned:
        return
    profile = OperatorProfile.load(Path(pinned))
    with _control_connection(profile) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute(
            "SELECT phase FROM recovery_operations ORDER BY epoch DESC LIMIT 1"
        ).fetchone()
        # An unfinished recovery is already a durable admission fence. Runtime
        # observations during its READY-before-COMPLETE window must not replace
        # the authorized operation or invent another approval.
        if row is not None and row[0] != "COMPLETE":
            return
        connection.execute(
            "INSERT INTO recovery_operations(request_id,manifest,signatures,profile_digest,phase) "
            "VALUES(?,?,?,?,'FAILED')",
            ("failure-" + secrets.token_hex(16), "{}", "{}", profile.digest),
        )


@dataclass(frozen=True)
class _Session:
    profile: OperatorProfile
    manifest: RecoveryManifest
    signatures: Mapping[str, str]
    engine: Any
    provider: Any
    approved_evidence: Mapping[str, Any]
    state: dict[str, Any] = field(default_factory=dict)


_SESSION: ContextVar[_Session | None] = ContextVar(
    "whitepact_offline_operator_recovery", default=None
)


def _checked_session(*, phase: str, engine=None, provider=None) -> _Session:
    session = _SESSION.get()
    if (
        session is None
        or (engine is not None and engine is not session.engine)
        or (provider is not None and provider is not session.provider)
    ):
        raise RecoveryAuthorizationError("Verified offline operator recovery session required")
    profile = OperatorProfile.load(session.profile.path)
    if profile.digest != session.profile.digest:
        raise RecoveryAuthorizationError("Operator trust configuration changed")
    if _digest(session.approved_evidence) != session.manifest.evidence_digest:
        raise RecoveryAuthorizationError("Recovery session evidence is not the approved evidence")
    verify_operator_approvals(
        session.manifest,
        profile.keys,
        session.signatures,
        now=int(time.time()),
        deployment_id=profile.deployment_id,
        environment=profile.environment,
    )
    row = _latest(profile)
    if (
        row is None
        or row["request_id"] != session.manifest.request_id
        or row["phase"] != phase
        or row["profile_digest"] != profile.digest
    ):
        raise RecoveryAuthorizationError("Recovery session is stale, consumed or interrupted")
    return session


def assert_engine_authorized(engine, provider) -> None:
    if enforcement_required() or (
        hasattr(provider, "requires_operator_recovery") and provider.requires_operator_recovery()
    ):
        _checked_session(phase="CONSUMED", engine=engine, provider=provider)


def assert_ready_write_authorized(provider=None) -> None:
    if enforcement_required() or (
        hasattr(provider, "requires_operator_recovery") and provider.requires_operator_recovery()
    ):
        if provider is None:
            raise RecoveryAuthorizationError("Durable recovery provider required")
        _checked_session(phase="PG_VERIFIED", provider=provider)


def authorized_ready_epoch(provider) -> int:
    session = _checked_session(phase="PG_VERIFIED", provider=provider)
    return session.manifest.readiness_epoch + 1


def validate_ready_lifecycle(provider) -> None:
    session = _checked_session(phase="PG_VERIFIED", provider=provider)
    snapshot = _store_b_snapshot(provider)
    if (
        _digest(snapshot["lifecycle"]) != session.approved_evidence["lifecycle_digest"]
        or _digest(snapshot["provisioning"]) != session.approved_evidence["provisioning_digest"]
    ):
        raise RecoveryAuthorizationError("Store B lifecycle changed after operator approval")


async def _pg_snapshots(connection):
    from responsibleai.db.engine import metadata

    versions = (
        (await connection.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
    )
    if versions != ["0067"]:
        raise RecoveryAuthorizationError("Runtime schema changed during recovery")
    snapshots = {}
    org_ids = []
    for name in _TABLES:
        rows = (
            (await connection.execute(select(metadata.tables[name]).limit(10001))).mappings().all()
        )
        if len(rows) > 10000:
            raise RecoveryAuthorizationError("Recovery evidence exceeds bounded plan")
        records = [dict(row) for row in rows]
        if name == "runtime_containment_records" and any(
            row["state"] != "CONTAINED" for row in records
        ):
            raise RecoveryAuthorizationError("Durable execution intent remains unresolved")
        if name == "organizations":
            org_ids = [row["id"] for row in records]
        snapshots[name] = _snapshot_digest(records)
    return snapshots, org_ids


async def _lock_authority_tables(connection) -> None:
    await connection.execute(text("SET LOCAL lock_timeout='5s'"))
    await connection.execute(
        text("LOCK TABLE alembic_version," + ",".join(_TABLES) + " IN SHARE ROW EXCLUSIVE MODE")
    )


async def begin_locked_reconciliation_inputs(connection, provider) -> None:
    if not enforcement_required() and not (
        hasattr(provider, "requires_operator_recovery") and provider.requires_operator_recovery()
    ):
        return
    session = _checked_session(phase="CONSUMED", provider=provider)
    await _lock_authority_tables(connection)
    store_lock = sqlite3.connect(str(provider.path), timeout=1)
    try:
        store_lock.execute("BEGIN IMMEDIATE")
        session.state["store_lock"] = store_lock
        snapshots, _ = await _pg_snapshots(connection)
        store_b = _store_b_snapshot(provider)
        if (
            _digest(snapshots) != session.approved_evidence["pg_digest"]
            or _digest(store_b["lifecycle"]) != session.approved_evidence["lifecycle_digest"]
            or store_b["identity"] != session.manifest.store_b_identity
            or store_b["state"] != "RECONCILING"
            or store_b["epoch"] != session.manifest.readiness_epoch + 1
        ):
            raise RecoveryAuthorizationError("Signed recovery inputs changed before mutation")
    except BaseException:
        release_reconciliation_store_lock()
        raise


async def capture_reconciled_authority(connection, provider) -> None:
    session = _SESSION.get()
    if session is None:
        return
    _checked_session(phase="CONSUMED", provider=provider)
    snapshots, _ = await _pg_snapshots(connection)
    session.state["reconciled_digest"] = _digest(
        {key: value for key, value in snapshots.items() if key != "restore_reconciliation_records"}
    )


def release_reconciliation_store_lock() -> None:
    session = _SESSION.get()
    if session is not None:
        connection = session.state.pop("store_lock", None)
        if connection is not None:
            try:
                connection.rollback()
            finally:
                connection.close()


def _phase(session: _Session, previous: str, following: str, **values) -> None:
    with _control_connection(session.profile) as connection:
        result = connection.execute(
            "UPDATE recovery_operations SET phase=?,store_b_epoch=?,final_digest=? "
            "WHERE request_id=? AND phase=?",
            (
                following,
                values.get("store_b_epoch"),
                values.get("final_digest"),
                session.manifest.request_id,
                previous,
            ),
        )
        if result.rowcount != 1:
            raise RecoveryAuthorizationError("Conflicting recovery transition")


def _store_b_snapshot(provider) -> dict[str, Any]:
    if not provider.verify_integrity():
        raise RecoveryAuthorizationError("Store B integrity is not verified")
    path = Path(provider.path)
    info = path.stat()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as connection:
        row = connection.execute(
            "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
        ).fetchone()
        provisioning: dict[str, str | None] = {}
        for table in (
            "tenant_provisioning_reservations",
            "provisioning_controller_trust",
            "provisioning_publication_consumptions",
            "tenant_provisioning_completions",
        ):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if not exists:
                provisioning[table] = None
                continue
            rows = connection.execute(f"SELECT * FROM {table} LIMIT 10001").fetchall()
            if len(rows) > 10000:
                raise RecoveryAuthorizationError(
                    "Provisioning recovery evidence exceeds qualified bound"
                )
            provisioning[table] = _digest(
                sorted(
                    [
                        [value.hex() if isinstance(value, bytes) else value for value in record]
                        for record in rows
                    ],
                    key=lambda record: str(record[0]),
                )
            )
    if row is None:
        raise RecoveryAuthorizationError("Recovery requires existing durable quarantine evidence")
    return {
        "identity": _digest([str(path), info.st_dev, info.st_ino]),
        "state": row[0],
        "epoch": row[1],
        "provisioning": provisioning,
        "lifecycle": sorted(
            (asdict(record) for record in provider.list_all()),
            key=lambda record: record["tenant_id"],
        ),
    }


async def collect_recovery_evidence(engine, provider, profile: OperatorProfile) -> dict[str, Any]:
    """Read real PG, durable Store B, registry and dedicated-host Docker evidence.

    Unknown containers are blockers; approved infrastructure must be explicitly
    pinned by full immutable CID in the protected nonproduction profile.
    """
    from responsibleai.isolation.in_flight import InFlightExecutionRegistry

    if engine.raw.dialect.name != "postgresql" or Path(provider.path) != profile.store_b_path:
        raise RecoveryAuthorizationError("Exact PostgreSQL and Store B targets required")
    if engine.raw.url.host not in (None, "localhost", "127.0.0.1", "::1"):
        raise RecoveryAuthorizationError(
            "This nonproduction candidate supports local PostgreSQL only"
        )
    async with engine.raw.connect() as connection:
        async with connection.begin():
            await connection.execute(
                text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            )
            version = (
                (await connection.execute(text("SELECT version_num FROM alembic_version")))
                .scalars()
                .all()
            )
            if version != ["0067"]:
                raise RecoveryAuthorizationError("Exact compatible schema 0067 required")
            identity = (
                await connection.execute(
                    text(
                        "SELECT current_database(), oid::text, (SELECT system_identifier::text FROM pg_control_system()) "
                        "FROM pg_database WHERE datname=current_database()"
                    )
                )
            ).one()
            if _digest(list(identity)) != profile.postgres_identity:
                raise RecoveryAuthorizationError("PostgreSQL deployment identity mismatch")
            # Read-only qualification is allowed while FAILED; it cannot admit
            # traffic or replace operator authorization. Incomplete/stale active
            # tenant evidence must not become READY through reconciliation.
            from responsibleai.data_governance.tenant_admission import (
                verify_tenant_completion_evidence,
            )

            tenants = (
                (await connection.execute(text("SELECT id FROM organizations"))).scalars().all()
            )
            for tenant_id in tenants:
                lifecycle = provider.get_state(tenant_id)
                if lifecycle is None:
                    raise RecoveryAuthorizationError(
                        "Store A tenant is lacking authoritative Store B lifecycle"
                    )
                if lifecycle.state.value == "ACTIVE":
                    epoch = await connection.scalar(
                        text(
                            "SELECT epoch FROM governance_revocation_epochs WHERE organization_id=:tenant AND scope='governance'"
                        ),
                        {"tenant": tenant_id},
                    )
                    try:
                        await verify_tenant_completion_evidence(
                            connection, tenant_id, int(epoch or 0), provider
                        )
                    except Exception as exc:
                        raise RecoveryAuthorizationError(
                            "Active tenant completion evidence is unverified"
                        ) from exc
            snapshots, org_ids = await _pg_snapshots(connection)
    registry = InFlightExecutionRegistry.get_instance()
    if registry.get_unresolved_containments() or any(
        registry.count_active(org) or registry.count_unresolved(org)
        for org in [*org_ids, "unknown"]
    ):
        raise RecoveryAuthorizationError("In-flight execution tracking is unresolved")
    from responsibleai.isolation.container_backend import DockerContainerBackend
    from responsibleai.isolation.durable_intent import daemon_identity

    docker = DockerContainerBackend().docker_cmd
    daemon = await asyncio.to_thread(daemon_identity, docker)
    if daemon != profile.docker_identity:
        raise RecoveryAuthorizationError("Docker backend identity mismatch")
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
        raise RecoveryAuthorizationError("Unknown or surviving execution workload")
    # Docker's human-duration strings change merely as time passes. They are
    # not identity/state evidence and must not invalidate an otherwise exact plan.
    inventory = [
        {
            key: row.get(key)
            for key in ("ID", "Names", "Labels", "State", "Image", "Mounts", "Networks", "Ports")
        }
        for row in inventory
    ]
    store_b = _store_b_snapshot(provider)
    with _control_connection(profile) as connection:
        floor = connection.execute(
            "SELECT max(store_b_epoch) FROM recovery_operations WHERE phase='COMPLETE'"
        ).fetchone()[0]
    if floor is not None and store_b["epoch"] < floor:
        raise RecoveryAuthorizationError("Store B readiness epoch rolled back")
    return {
        "evidence_format": EVIDENCE_FORMAT,
        "postgres_identity": profile.postgres_identity,
        "schema_revision": "0067",
        "store_b_identity": store_b["identity"],
        "readiness_epoch": store_b["epoch"],
        "journal_digest": snapshots["runtime_containment_records"],
        "revocation_digest": _digest(
            [
                snapshots["governance_revocation_epochs"],
                snapshots["governance_execution_authorizations"],
            ]
        ),
        "docker_identity": daemon,
        "inventory_digest": _digest(sorted(inventory, key=lambda row: row["ID"])),
        "stores_digest": _digest([snapshots, store_b]),
        "pg_digest": _digest(snapshots),
        "lifecycle_digest": _digest(store_b["lifecycle"]),
        "provisioning_digest": _digest(store_b["provisioning"]),
        "source_digest": _digest(
            {
                key: value
                for key, value in snapshots.items()
                if key != "restore_reconciliation_records"
            }
        ),
    }


async def prepare_offline_recovery(engine, provider, *, profile_path: Path) -> RecoveryManifest:
    """Read-only PREPARE; no signature, authority or readiness is created."""
    profile = OperatorProfile.load(profile_path)
    evidence = await collect_recovery_evidence(engine, provider, profile)
    snapshot = _store_b_snapshot(provider)
    if snapshot["state"] == "READY":
        raise RecoveryAuthorizationError("No quarantined recovery incident exists")
    designated = {}
    for role in ("SECURITY_OWNER", "RECOVERY_OPERATOR"):
        identities = [
            key.identity for key in profile.keys if key.role == role and key.revoked is False
        ]
        if len(identities) != 1:
            raise RecoveryAuthorizationError("Exact designated operator roles required")
        designated[role] = identities[0]
    values = {
        key: value
        for key, value in evidence.items()
        if key in RecoveryManifest.__dataclass_fields__
    }
    now = int(time.time())
    manifest = RecoveryManifest(
        **values,
        request_id=_EVIDENCE_REQUEST_PREFIX + secrets.token_hex(16),
        deployment_id=profile.deployment_id,
        environment=profile.environment,
        incident_id=profile.incident_id,
        evidence_digest=_digest(evidence),
        action="RECONCILE_EXECUTION_ADMISSION",
        scope="SINGLE_HOST",
        security_owner=designated["SECURITY_OWNER"],
        recovery_operator=designated["RECOVERY_OPERATOR"],
        created_at=now,
        expires_at=now + 180,
        nonce=secrets.token_hex(32),
    )
    manifest.canonical_bytes()
    return manifest


async def verify_engine_final_state(engine, provider) -> None:
    if not enforcement_required():
        return
    session = _checked_session(phase="CONSUMED", engine=engine, provider=provider)
    evidence = await collect_recovery_evidence(engine, provider, session.profile)
    if evidence["source_digest"] != session.state.get("reconciled_digest"):
        raise RecoveryAuthorizationError("Reconciled authority changed before finalization")
    if evidence["lifecycle_digest"] != session.approved_evidence["lifecycle_digest"]:
        raise RecoveryAuthorizationError("Approved Store B lifecycle changed")
    if evidence["provisioning_digest"] != session.approved_evidence["provisioning_digest"]:
        raise RecoveryAuthorizationError("Approved provisioning evidence changed")
    snapshot = _store_b_snapshot(provider)
    if (
        snapshot["state"] != "RECONCILING"
        or snapshot["epoch"] != session.manifest.readiness_epoch + 1
    ):
        raise RecoveryAuthorizationError("Recovery readiness changed during reconciliation")
    _phase(session, "CONSUMED", "PG_VERIFIED", final_digest=_digest(evidence))


def assert_completed_binding(provider) -> bool:
    """A READY write from interrupted recovery is not admission, even on restart."""
    with sqlite3.connect(f"file:{provider.path}?mode=ro", uri=True) as connection:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='operator_recovery_binding'"
        ).fetchone()
        if not exists:
            pinned = os.environ.get("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG")
            if pinned:
                profile = OperatorProfile.load(Path(pinned))
                if Path(provider.path) != profile.store_b_path:
                    raise RecoveryAuthorizationError(
                        "Store B does not match the pinned operator target"
                    )
                if _latest(profile) is not None:
                    raise RecoveryAuthorizationError(
                        "Store B recovery binding is absent or rolled back"
                    )
            return False
        binding = connection.execute(
            "SELECT profile_path,request_id FROM operator_recovery_binding WHERE id=1"
        ).fetchone()
    if binding is None:
        raise RecoveryAuthorizationError("Recovery binding is missing")
    profile = OperatorProfile.load(Path(binding[0]))
    row = _latest(profile)
    if (
        row is not None
        and row["request_id"] == binding[1]
        and row["profile_digest"] == profile.digest
        and row["phase"] in ("CONSUMED", "PG_VERIFIED")
    ):
        raise RecoveryInProgressError("Offline operator recovery is incomplete")
    if (
        row is None
        or row["phase"] != "COMPLETE"
        or row["request_id"] != binding[1]
        or row["profile_digest"] != profile.digest
    ):
        raise RecoveryAuthorizationError("Recovery is incomplete or evidence changed")
    manifest = RecoveryManifest(**json.loads(row["manifest"]))
    _require_manifest_format(manifest)
    _require_completed_evidence(row, manifest)
    verify_operator_approvals(
        manifest,
        profile.keys,
        json.loads(row["signatures"]),
        now=manifest.created_at,
        deployment_id=profile.deployment_id,
        environment=profile.environment,
    )
    with _control_connection(profile) as connection:
        receipt = connection.execute(
            "SELECT manifest_digest,state FROM recovery_receipts WHERE request_id=? AND nonce=?",
            (manifest.request_id, manifest.nonce),
        ).fetchone()
    if receipt != (manifest.digest(), "CONSUMED"):
        raise RecoveryAuthorizationError("Recovery consumption evidence is missing")
    snapshot = _store_b_snapshot(provider)
    if snapshot["state"] != "READY" or snapshot["epoch"] != row["store_b_epoch"]:
        raise RecoveryAuthorizationError("Store B recovery epoch changed")
    return True


async def assert_database_recovery_binding(engine) -> None:
    """A rolled-back Store A cannot reuse a completed external recovery receipt."""
    pinned = os.environ.get("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG")
    if not pinned:
        return
    profile = OperatorProfile.load(Path(pinned))
    row = _latest(profile)
    if row is None:
        return
    if row["phase"] in ("CONSUMED", "PG_VERIFIED"):
        raise RecoveryInProgressError("Offline operator recovery is incomplete")
    if row["phase"] != "COMPLETE":
        raise RecoveryAuthorizationError("Offline recovery has not completed")
    from responsibleai.db.engine import restore_reconciliation_records

    async with engine.raw.connect() as connection:
        record = (
            await connection.execute(
                select(
                    restore_reconciliation_records.c.status,
                    restore_reconciliation_records.c.reconciled_by,
                )
                .order_by(restore_reconciliation_records.c.restored_at.desc())
                .limit(1)
            )
        ).first()
    if record is None or tuple(record) != ("RECONCILED", row["request_id"]):
        raise RecoveryAuthorizationError("Store A does not match the completed operator recovery")


@contextmanager
def _exclusive_operation(profile: OperatorProfile) -> Iterator[None]:
    path = profile.ledger_path.with_suffix(".recovery-lock")
    descriptor = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(descriptor)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise RecoveryAuthorizationError("Invalid recovery lock")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise RecoveryAuthorizationError("Recovery operation already in progress") from exc
        yield
    finally:
        os.close(descriptor)


async def execute_offline_recovery(
    engine,
    provider,
    gate,
    *,
    profile_path: Path,
    manifest: RecoveryManifest,
    signatures: Mapping[str, str],
):
    """One signed, single-host nonproduction recovery; no automatic retry."""
    from responsibleai.data_governance.backup_defense import (
        RestoreReadinessState,
        RestoreReconciliationEngine,
    )

    profile = OperatorProfile.load(profile_path)
    _require_manifest_format(manifest)
    if manifest.incident_id != profile.incident_id:
        raise RecoveryAuthorizationError("Recovery incident mismatch")
    if not enforcement_required():
        raise RecoveryAuthorizationError("Qualification requires the hosted enforcement boundary")
    with _exclusive_operation(profile):
        evidence = await collect_recovery_evidence(engine, provider, profile)
        for name, value in evidence.items():
            if name in RecoveryManifest.__dataclass_fields__ and getattr(manifest, name) != value:
                raise RecoveryAuthorizationError("Recovery evidence is stale or target mismatched")
        ledger = RecoveryReceiptLedger(profile.ledger_path)
        ledger.consume_approvals(
            manifest,
            profile.keys,
            signatures,
            now=int(time.time()),
            deployment_id=profile.deployment_id,
            environment=profile.environment,
            current_evidence_digest=_digest(evidence),
        )
        with _control_connection(profile) as connection:
            connection.execute(
                "INSERT INTO recovery_operations(request_id,manifest,signatures,profile_digest,phase,evidence_format,approved_evidence) "
                "VALUES(?,?,?,?,'CONSUMED',?,?)",
                (
                    manifest.request_id,
                    json.dumps(asdict(manifest)),
                    json.dumps(dict(signatures)),
                    profile.digest,
                    EVIDENCE_FORMAT,
                    json.dumps(
                        evidence,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=True,
                        allow_nan=False,
                    ),
                ),
            )
        session = _Session(profile, manifest, signatures, engine, provider, evidence)
        token = _SESSION.set(session)
        try:
            if _store_b_snapshot(provider)["state"] == "READY":
                raise RecoveryAuthorizationError("Recovery requires a quarantined system")
            with sqlite3.connect(provider.path) as connection:
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS operator_recovery_binding "
                    "(id INTEGER PRIMARY KEY CHECK(id=1),profile_path TEXT NOT NULL,request_id TEXT NOT NULL)"
                )
                connection.execute(
                    "INSERT OR REPLACE INTO operator_recovery_binding VALUES(1,?,?)",
                    (str(profile.path), manifest.request_id),
                )
            # Only after real evidence verification and durable consumption.
            # The public gate's sticky DB error is not itself a repair operation.
            if gate.provider is not provider or gate.provider_error is not None:
                gate = type(gate)(provider=provider, db_engine=engine)
            reconciler = RestoreReconciliationEngine(
                engine, lifecycle_provider=provider, gate=gate, require_durable=True
            )
            report = await reconciler.reconcile_post_restore(reconciled_by=manifest.request_id)
            _checked_session(phase="PG_VERIFIED", engine=engine, provider=provider)
            async with engine.raw.begin() as final_connection:
                await _lock_authority_tables(final_connection)
                with sqlite3.connect(str(provider.path), timeout=1) as final_store_lock:
                    final_store_lock.execute("BEGIN IMMEDIATE")
                    final = await collect_recovery_evidence(engine, provider, profile)
                    snapshot = _store_b_snapshot(provider)
                    if (
                        snapshot["state"] != "READY"
                        or snapshot["epoch"] != manifest.readiness_epoch + 2
                        or final["source_digest"] != session.state.get("reconciled_digest")
                        or final["lifecycle_digest"]
                        != session.approved_evidence["lifecycle_digest"]
                        or final["provisioning_digest"]
                        != session.approved_evidence["provisioning_digest"]
                    ):
                        raise RecoveryAuthorizationError(
                            "Recovery evidence changed during finalization"
                        )
                    _phase(
                        session,
                        "PG_VERIFIED",
                        "COMPLETE",
                        store_b_epoch=snapshot["epoch"],
                        final_digest=_digest(final),
                    )
                    if not assert_completed_binding(provider):
                        raise RecoveryAuthorizationError("Recovery completion readback failed")
            return report
        except BaseException:
            # Includes cancellation; process death is fenced by the persisted
            # non-COMPLETE phase and Store B binding instead of this handler.
            gate.set_state(RestoreReadinessState.FAILED, updated_by=manifest.request_id)
            raise
        finally:
            release_reconciliation_store_lock()
            _SESSION.reset(token)
