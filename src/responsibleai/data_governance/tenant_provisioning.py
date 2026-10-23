# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Nonproduction durable reservation and signed publication storage.

Publication requires a pinned controller signature and matching pending intent.
These storage operations alone neither validate Store A nor authorize execution;
the protected controller and completion admission verifier enforce those checks.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from dataclasses import asdict, astuple, dataclass

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    compute_lifecycle_digest,
)
from responsibleai.data_governance.provisioning_manifest import (
    ProvisionerTrust,
    ProvisioningAuthorizationError,
    ProvisioningManifest,
    verify_provisioning_manifest,
)
from responsibleai.environment import is_production


class ProvisioningReservationError(RuntimeError):
    """Pending evidence is unavailable or conflicts; no authority is created."""


@dataclass(frozen=True)
class PendingTenantIdentity:
    deployment_id: str
    request_id: str
    principal_id: str
    operation_digest: str
    tenant_id: str
    generation_id: str
    status: str


class PendingTenantReservations:
    """Durable exactly-once pending reservation; caller authentication is NOT implemented here."""

    def __init__(self, provider: SqliteDurableLifecycleStateProvider) -> None:
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        if (
            type(provider) is not SqliteDurableLifecycleStateProvider
            or not provider.verify_integrity()
        ):
            raise ProvisioningReservationError("Verified durable Store B is required")
        self._provider = provider

    def initialize(self) -> None:
        """Explicit test/engineering setup; never called by a read or reservation."""
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE tenant_provisioning_reservations ("
                "deployment_id TEXT NOT NULL,request_id TEXT NOT NULL,"
                "principal_id TEXT NOT NULL,operation_digest TEXT NOT NULL,"
                "tenant_id TEXT NOT NULL UNIQUE,generation_id TEXT NOT NULL UNIQUE "
                "CHECK(length(generation_id)=64 AND generation_id NOT GLOB '*[^a-f0-9]*'),"
                "status TEXT NOT NULL CHECK(status='PENDING'),"
                "PRIMARY KEY(deployment_id,request_id))"
            )
            for action in ("UPDATE", "DELETE"):
                connection.execute(
                    f"CREATE TRIGGER tenant_reservation_no_{action.lower()} BEFORE {action} "
                    "ON tenant_provisioning_reservations BEGIN "
                    "SELECT RAISE(ABORT,'Pending identity reservations are immutable'); END"
                )
            connection.commit()
        finally:
            connection.close()

    def get(self, *, deployment_id: str, request_id: str) -> PendingTenantIdentity | None:
        """Read existing intent only; never bootstrap missing rollback evidence."""
        if is_production() or not self._provider.verify_integrity():
            raise ProvisioningReservationError("Pending identity evidence is unavailable")
        connection = self._provider._get_connection()
        try:
            row = connection.execute(
                "SELECT deployment_id,request_id,principal_id,operation_digest,tenant_id,generation_id,status "
                "FROM tenant_provisioning_reservations WHERE deployment_id=? AND request_id=?",
                (deployment_id, request_id),
            ).fetchone()
            return PendingTenantIdentity(*row) if row else None
        except sqlite3.Error as exc:
            raise ProvisioningReservationError("Pending identity evidence is unavailable") from exc
        finally:
            connection.close()

    def reserve(
        self, *, deployment_id: str, request_id: str, principal_id: str, operation_digest: str
    ) -> PendingTenantIdentity:
        """Reserve only pending data; never infer that a claimed principal is authorized."""
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        for value in (deployment_id, request_id, principal_id):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
                raise ProvisioningReservationError("Invalid reservation binding")
        if not isinstance(operation_digest, str) or not re.fullmatch(
            r"[a-f0-9]{64}", operation_digest
        ):
            raise ProvisioningReservationError("Invalid operation digest")
        if not self._provider.verify_integrity():
            raise ProvisioningReservationError("Store B integrity is unverified")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT deployment_id,request_id,principal_id,operation_digest,"
                "tenant_id,generation_id,status FROM tenant_provisioning_reservations "
                "WHERE deployment_id=? AND request_id=?",
                (deployment_id, request_id),
            ).fetchone()
            if row is not None:
                if row[2:4] != (principal_id, operation_digest) or row[6] != "PENDING":
                    raise ProvisioningReservationError("Reservation binding conflict")
                result = PendingTenantIdentity(*row)
            else:
                result = PendingTenantIdentity(
                    deployment_id,
                    request_id,
                    principal_id,
                    operation_digest,
                    str(uuid.uuid4()),
                    secrets.token_hex(32),
                    "PENDING",
                )
                connection.execute(
                    "INSERT INTO tenant_provisioning_reservations VALUES(?,?,?,?,?,?,?)",
                    astuple(result),
                )
            connection.commit()
            return result
        except sqlite3.Error as error:
            raise ProvisioningReservationError("Pending reservation storage unavailable") from error
        finally:
            connection.close()


class PublicationAuthorizationLedger:
    """Single-host durable authorization consumption, not tenant activation.

    No trust is accepted at consumption time. Explicit engineering enrollment
    pins one disposable controller to this Store B. Operational key enrollment
    and OS isolation remain separate; production use is deliberately refused.
    A consumed receipt is never an admission or COMPLETE receipt.
    """

    def __init__(self, provider: SqliteDurableLifecycleStateProvider) -> None:
        if type(provider) is not SqliteDurableLifecycleStateProvider or is_production():
            raise ProvisioningReservationError("Unqualified publication ledger deployment")
        self._provider = provider

    def initialize(self, trust: ProvisionerTrust) -> None:
        """Explicit disposable enrollment; never overwrite an enrolled controller."""
        if is_production():
            raise ProvisioningReservationError("Production controller enrollment is not authorized")
        if type(trust.public_key) is not bytes or len(trust.public_key) != 32 or trust.revoked:
            raise ProvisioningAuthorizationError("Invalid controller enrollment")
        if len(self._provider._secret_key.encode()) < 32:
            raise ProvisioningAuthorizationError("Independent Store B integrity key required")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE provisioning_controller_trust ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1),"
                "controller_id TEXT NOT NULL,public_key BLOB NOT NULL,"
                "deployment_id TEXT NOT NULL,environment TEXT NOT NULL,"
                "postgres_identity TEXT NOT NULL,store_b_identity TEXT NOT NULL,"
                "revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),digest TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO provisioning_controller_trust VALUES(1,?,?,?,?,?,?,0,?)",
                (
                    trust.controller_id,
                    trust.public_key,
                    trust.deployment_id,
                    trust.environment,
                    trust.postgres_identity,
                    trust.store_b_identity,
                    self._trust_digest(trust),
                ),
            )
            connection.execute(
                "CREATE TABLE provisioning_publication_consumptions ("
                "request_id TEXT PRIMARY KEY,tenant_id TEXT NOT NULL UNIQUE,"
                "generation_id TEXT NOT NULL UNIQUE,nonce TEXT NOT NULL UNIQUE,"
                "manifest_digest TEXT NOT NULL UNIQUE,consumed_at INTEGER NOT NULL,"
                "manifest_json TEXT NOT NULL,signature TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE tenant_provisioning_completions ("
                "tenant_id TEXT PRIMARY KEY,manifest_json TEXT NOT NULL,"
                "signature TEXT NOT NULL,nonce TEXT NOT NULL UNIQUE)"
            )
            for table in (
                "provisioning_controller_trust",
                "provisioning_publication_consumptions",
                "tenant_provisioning_completions",
            ):
                for action in ("UPDATE", "DELETE"):
                    connection.execute(
                        f"CREATE TRIGGER {table}_no_{action.lower()} BEFORE {action} ON {table} "
                        "BEGIN SELECT RAISE(ABORT,'Provisioning evidence is immutable'); END"
                    )
            connection.commit()
        finally:
            connection.close()

    def _load_trust(self, connection: sqlite3.Connection) -> ProvisionerTrust:
        row = connection.execute(
            "SELECT controller_id,public_key,deployment_id,environment,"
            "postgres_identity,store_b_identity,revoked,digest FROM provisioning_controller_trust "
            "WHERE singleton=1"
        ).fetchone()
        if row is None:
            raise ProvisioningAuthorizationError("Controller trust is missing")
        trust = ProvisionerTrust(
            controller_id=row[0],
            public_key=row[1],
            deployment_id=row[2],
            environment=row[3],
            postgres_identity=row[4],
            store_b_identity=row[5],
            revoked=bool(row[6]),
        )
        if len(self._provider._secret_key.encode()) < 32 or not hmac.compare_digest(
            row[7], self._trust_digest(trust)
        ):
            raise ProvisioningAuthorizationError("Controller trust integrity failure")
        return trust

    def publication(self, tenant_id: str) -> ProvisioningManifest | None:
        """Read verified historical evidence; this never authorizes a new write."""
        if is_production() or not self._provider.verify_integrity():
            raise ProvisioningReservationError("Publication ledger is not admitted")
        connection = self._provider._get_connection()
        try:
            row = connection.execute(
                "SELECT manifest_json,signature,manifest_digest FROM "
                "provisioning_publication_consumptions WHERE tenant_id=?",
                (tenant_id,),
            ).fetchone()
            if row is None:
                return None
            manifest = ProvisioningManifest(**json.loads(row[0]))
            digest = verify_provisioning_manifest(
                manifest,
                row[1],
                self._load_trust(connection),
                now=manifest.created_at,
                current_readiness_epoch=manifest.readiness_epoch,
            )
            if (
                digest != row[2]
                or manifest.tenant_id != tenant_id
                or manifest.action != "PUBLISH_TENANT_LIFECYCLE"
            ):
                raise ProvisioningAuthorizationError("Publication evidence mismatch")
            pending = connection.execute(
                "SELECT principal_id,operation_digest,tenant_id,generation_id,status "
                "FROM tenant_provisioning_reservations WHERE deployment_id=? AND request_id=?",
                (manifest.deployment_id, manifest.request_id),
            ).fetchone()
            if pending != (
                manifest.principal_id,
                manifest.operation_digest,
                manifest.tenant_id,
                manifest.generation_id,
                "PENDING",
            ):
                raise ProvisioningAuthorizationError("Publication pending evidence mismatch")
            return manifest
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise ProvisioningAuthorizationError("Publication evidence is unverified") from exc
        finally:
            connection.close()

    def complete(self, manifest: ProvisioningManifest, signature: str) -> None:
        """Consume fresh signed final-CAS evidence; not a substitute for Store A checks."""
        if is_production() or not self._provider.verify_integrity():
            raise ProvisioningReservationError("Completion ledger is not admitted")
        if self._provider.get_readiness_state() != RestoreReadinessState.READY:
            raise ProvisioningAuthorizationError("Completion remains quarantined")
        publication = self.publication(manifest.tenant_id)
        if publication is None or manifest.publication_digest != publication.digest():
            raise ProvisioningAuthorizationError("Exact publication evidence required")
        immutable = (
            "deployment_id",
            "environment",
            "postgres_identity",
            "store_b_identity",
            "request_id",
            "principal_id",
            "tenant_id",
            "generation_id",
            "operation_digest",
            "pending_receipt_digest",
            "controller_id",
            "security_epoch",
            "revocation_floor",
        )
        if manifest.action != "COMPLETE_TENANT_PROVISIONING" or any(
            getattr(manifest, name) != getattr(publication, name) for name in immutable
        ):
            raise ProvisioningAuthorizationError("Completion binding mismatch")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            readiness = connection.execute(
                "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
            ).fetchone()
            if readiness is None or readiness[0] != "READY":
                raise ProvisioningAuthorizationError("Completion requires durable READY evidence")
            verify_provisioning_manifest(
                manifest,
                signature,
                self._load_trust(connection),
                now=int(time.time()),
                current_readiness_epoch=readiness[1],
            )
            lifecycle = connection.execute(
                "SELECT generation_id,state,security_epoch,revocation_floor FROM "
                "durable_tenant_lifecycle_states WHERE tenant_id=?",
                (manifest.tenant_id,),
            ).fetchone()
            if lifecycle != (
                manifest.generation_id,
                "ACTIVE",
                manifest.security_epoch,
                manifest.revocation_floor,
            ):
                raise ProvisioningAuthorizationError("Completion lifecycle changed")
            if connection.execute(
                "SELECT 1 FROM provisioning_publication_consumptions WHERE nonce=?",
                (manifest.nonce,),
            ).fetchone():
                raise ProvisioningAuthorizationError("Completion nonce reused")
            connection.execute(
                "INSERT INTO tenant_provisioning_completions VALUES(?,?,?,?)",
                (
                    manifest.tenant_id,
                    json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")),
                    signature,
                    manifest.nonce,
                ),
            )
            connection.commit()
        except sqlite3.Error as exc:
            raise ProvisioningAuthorizationError(
                "Completion replay or unavailable evidence"
            ) from exc
        finally:
            connection.close()

    def completion(self, tenant_id: str) -> ProvisioningManifest | None:
        """Verify persisted completion signature against independently pinned trust."""
        if is_production() or not self._provider.verify_integrity():
            raise ProvisioningReservationError("Completion evidence is not admitted")
        connection = self._provider._get_connection()
        try:
            row = connection.execute(
                "SELECT manifest_json,signature,nonce FROM tenant_provisioning_completions WHERE tenant_id=?",
                (tenant_id,),
            ).fetchone()
            if row is None:
                return None
            manifest = ProvisioningManifest(**json.loads(row[0]))
            verify_provisioning_manifest(
                manifest,
                row[1],
                self._load_trust(connection),
                now=manifest.created_at,
                current_readiness_epoch=manifest.readiness_epoch,
            )
            if (
                manifest.action != "COMPLETE_TENANT_PROVISIONING"
                or manifest.tenant_id != tenant_id
                or row[2] != manifest.nonce
            ):
                raise ProvisioningAuthorizationError("Completion evidence mismatch")
            return manifest
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise ProvisioningAuthorizationError("Completion evidence is unverified") from exc
        finally:
            connection.close()

    def _trust_digest(self, trust: ProvisionerTrust) -> str:
        values = [
            trust.controller_id,
            trust.public_key.hex(),
            trust.deployment_id,
            trust.environment,
            trust.postgres_identity,
            trust.store_b_identity,
            trust.revoked,
        ]
        return hmac.new(
            self._provider._secret_key.encode(),
            b"WHITEPACT-PROVISIONER-TRUST-V1\x00"
            + json.dumps(values, separators=(",", ":")).encode(),
            hashlib.sha256,
        ).hexdigest()

    def consume(
        self,
        manifest: ProvisioningManifest,
        signature: str,
    ) -> str:
        """Verify scope and pending binding and consume exactly once atomically.

        The caller must already hold PostgreSQL authority locks before entering
        this Store B transaction. This method never opens or waits for Store A.
        It does not assert that the signed pending digest matches live Store A;
        that is a required controller check before lifecycle publication.
        """
        return self._consume(manifest, signature, publish=False)

    def publish(self, manifest: ProvisioningManifest, signature: str) -> str:
        """Atomically consume a controller attestation and publish its lifecycle.

        This is not completion or execution admission. The protected controller
        must hold and verify live Store A evidence before signing and calling.
        The PENDING reservation, verified signature and current READY epoch are
        mandatory even for direct calls; no caller-created grant is accepted.
        """
        return self._consume(manifest, signature, publish=True)

    def _consume(self, manifest: ProvisioningManifest, signature: str, *, publish: bool) -> str:
        if is_production() or not self._provider.verify_integrity():
            raise ProvisioningReservationError("Publication ledger is not admitted")
        if self._provider.get_readiness_state() != RestoreReadinessState.READY:
            raise ProvisioningAuthorizationError("Publication remains quarantined")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            trust = self._load_trust(connection)
            if manifest.action != "PUBLISH_TENANT_LIFECYCLE":
                raise ProvisioningAuthorizationError("Wrong publication action")
            readiness = connection.execute(
                "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
            ).fetchone()
            if readiness is None or readiness[0] != "READY":
                raise ProvisioningAuthorizationError("Provisioning requires durable READY evidence")
            now = int(time.time())
            digest = verify_provisioning_manifest(
                manifest,
                signature,
                trust,
                now=now,
                current_readiness_epoch=readiness[1],
            )
            reservation = connection.execute(
                "SELECT principal_id,operation_digest,tenant_id,generation_id,status "
                "FROM tenant_provisioning_reservations WHERE deployment_id=? AND request_id=?",
                (manifest.deployment_id, manifest.request_id),
            ).fetchone()
            if reservation != (
                manifest.principal_id,
                manifest.operation_digest,
                manifest.tenant_id,
                manifest.generation_id,
                "PENDING",
            ):
                raise ProvisioningAuthorizationError("Publication does not match reservation")
            if (
                connection.execute(
                    "SELECT 1 FROM durable_tenant_lifecycle_states WHERE tenant_id=?",
                    (manifest.tenant_id,),
                ).fetchone()
                is not None
            ):
                raise ProvisioningAuthorizationError("Tenant lifecycle is already established")
            connection.execute(
                "INSERT INTO provisioning_publication_consumptions VALUES(?,?,?,?,?,?,?,?)",
                (
                    manifest.request_id,
                    manifest.tenant_id,
                    manifest.generation_id,
                    manifest.nonce,
                    digest,
                    now,
                    json.dumps(asdict(manifest), sort_keys=True, separators=(",", ":")),
                    signature,
                ),
            )
            if publish:
                from datetime import UTC, datetime

                effective_at = datetime.fromtimestamp(manifest.created_at, UTC).isoformat()
                lifecycle_digest = compute_lifecycle_digest(
                    tenant_id=manifest.tenant_id,
                    generation_id=manifest.generation_id,
                    state="ACTIVE",
                    effective_at=effective_at,
                    security_epoch=manifest.security_epoch,
                    revocation_floor=manifest.revocation_floor,
                    erasure_request_ref="",
                    secret_key=self._provider._secret_key,
                )
                connection.execute(
                    "INSERT INTO durable_tenant_lifecycle_states "
                    "(tenant_id,generation_id,state,effective_at,security_epoch,"
                    "revocation_floor,erasure_request_ref,digest,updated_at) "
                    "VALUES(?,?,'ACTIVE',?,?,?,'',?,?)",
                    (
                        manifest.tenant_id,
                        manifest.generation_id,
                        effective_at,
                        manifest.security_epoch,
                        manifest.revocation_floor,
                        lifecycle_digest,
                        datetime.now(UTC).isoformat(),
                    ),
                )
            connection.commit()
            return digest
        except sqlite3.Error as exc:
            raise ProvisioningAuthorizationError(
                "Publication replay or unavailable evidence"
            ) from exc
        finally:
            connection.close()
