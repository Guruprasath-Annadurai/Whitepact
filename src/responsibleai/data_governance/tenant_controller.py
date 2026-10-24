# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Bounded single-host cross-store controller; no production activation.

The controller must run separately from the application with protected Store B
write access and a separately authorized PostgreSQL principal. Application DB
credentials must not be members of whitepact_tenant_controller. Disposable test
enrollment does not establish production process isolation or key custody.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import math
import os
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, replace
from datetime import UTC, datetime

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.provisioning_manifest import (
    ProvisionerTrust,
    ProvisioningAuthorizationError,
    ProvisioningManifest,
)
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    PublicationAuthorizationLedger,
)
from responsibleai.db.engine import DatabaseEngine
from responsibleai.environment import is_production


def canonical_digest(value: dict) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("ascii")
    ).hexdigest()


async def postgres_identity(connection) -> str:
    identity = (
        await connection.execute(
            text(
                "SELECT current_database(),oid::text,(SELECT system_identifier::text FROM pg_control_system()) "
                "FROM pg_database WHERE datname=current_database()"
            )
        )
    ).one()
    return canonical_digest({"postgres": list(identity)})


def store_b_identity(provider: SqliteDurableLifecycleStateProvider) -> str:
    info = provider.path.stat()
    return canonical_digest(
        {"path": str(provider.path.resolve()), "device": info.st_dev, "inode": info.st_ino}
    )


class ProtectedTenantController:
    def __init__(
        self,
        engine: DatabaseEngine,
        provider: SqliteDurableLifecycleStateProvider,
        trust: ProvisionerTrust,
        signing_key: Ed25519PrivateKey,
    ) -> None:
        if is_production() or engine.raw.dialect.name != "postgresql":
            raise ProvisioningAuthorizationError("Controller deployment is not qualified")
        if signing_key.public_key().public_bytes_raw() != trust.public_key:
            raise ProvisioningAuthorizationError("Controller key does not match enrolled trust")
        self.engine = engine
        self.provider = provider
        self.trust = trust
        self.key = signing_key
        self.reservations = PendingTenantReservations(provider)
        self.ledger = PublicationAuthorizationLedger(provider)

    @asynccontextmanager
    async def transaction(self):
        if is_production():
            raise ProvisioningAuthorizationError("Production provisioning is not authorized")
        async with self.engine.raw.begin() as connection:
            # No untrusted database principal can gain this role by calling Python.
            await connection.execute(text("SET LOCAL ROLE whitepact_tenant_controller"))
            await connection.execute(text("SET LOCAL search_path TO pg_catalog,public,pg_temp"))
            if await connection.scalar(text("SELECT version_num FROM alembic_version")) != "0067":
                raise ProvisioningAuthorizationError("Provisioning schema is incompatible")
            if (
                await postgres_identity(connection) != self.trust.postgres_identity
                or store_b_identity(self.provider) != self.trust.store_b_identity
                or os.environ.get("WHITEPACT_ENV") != self.trust.environment
            ):
                raise ProvisioningAuthorizationError("Controller deployment identity mismatch")
            store_connection = self.provider._get_connection()
            try:
                if self.ledger._load_trust(store_connection) != self.trust:
                    raise ProvisioningAuthorizationError("Controller enrollment mismatch")
            finally:
                store_connection.close()
            yield connection

    async def authenticate(self, connection, token: str, csrf: str) -> tuple[str, str]:
        if not token or not csrf:
            raise ProvisioningAuthorizationError("Authenticated browser session and CSRF required")
        now = datetime.now(UTC).isoformat()
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT s.user_id,s.session_id,s.csrf_hash,s.inactivity_expires_at "
                        "FROM web_sessions s JOIN web_users u ON u.id=s.user_id "
                        "WHERE s.token_hash=:token AND s.revoked=0 AND s.expires_at>:now "
                        "AND u.disabled=0 AND u.email_verified_at IS NOT NULL "
                        "AND (u.verification_status IS NULL OR u.verification_status<>'SUSPENDED') "
                        "FOR UPDATE OF s,u"
                    ),
                    {"token": token_hash, "now": now},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or (row["inactivity_expires_at"] and row["inactivity_expires_at"] <= now):
            raise ProvisioningAuthorizationError("Creation session is not current")
        if not hmac.compare_digest(row["csrf_hash"], hashlib.sha256(csrf.encode()).hexdigest()):
            raise ProvisioningAuthorizationError("Creation CSRF verification failed")
        return row["user_id"], token_hash

    async def lock(self, connection, request_id: str):
        # Existing organization authority is locked before its projection and B.
        row = (
            (
                await connection.execute(
                    text("SELECT * FROM tenant_provisioning_records WHERE request_id=:request"),
                    {"request": request_id},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row:
            await connection.execute(
                text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"),
                {"id": row["tenant_id"]},
            )
            row = (
                (
                    await connection.execute(
                        text(
                            "SELECT * FROM tenant_provisioning_records WHERE request_id=:request FOR UPDATE"
                        ),
                        {"request": request_id},
                    )
                )
                .mappings()
                .one()
            )
        return row

    def readiness_epoch(self) -> int:
        if self.provider.get_readiness_state() != RestoreReadinessState.READY:
            raise ProvisioningAuthorizationError("Provisioning remains quarantined")
        connection = self.provider._get_connection()
        try:
            row = connection.execute(
                "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
            ).fetchone()
            if row is None or row[0] != "READY" or not self.provider.verify_integrity():
                raise ProvisioningAuthorizationError("Provisioning remains quarantined")
            return row[1]
        finally:
            connection.close()

    def sign(self, manifest: ProvisioningManifest) -> str:
        return base64.b64encode(self.key.sign(manifest.canonical_bytes())).decode("ascii")

    async def create(
        self,
        *,
        session_token: str,
        csrf: str,
        request_id: str,
        name: str,
        slug: str,
        kind: str = "ORGANIZATION",
        attach_session: bool = False,
        monthly_budget_usd: float = 10000.0,
    ) -> str:
        if (
            not isinstance(request_id, str)
            or not 1 <= len(request_id) <= 128
            or not 1 <= len(name.strip()) <= 200
            or not 2 <= len(slug) <= 100
            or kind not in {"ORGANIZATION", "INDIVIDUAL"}
            or type(attach_session) is not bool
            or type(monthly_budget_usd) not in {float, int}
            or not math.isfinite(monthly_budget_usd)
            or not 0 <= monthly_budget_usd <= 1_000_000_000
        ):
            raise ProvisioningAuthorizationError("Invalid creation operation")
        name = name.strip()
        monthly_budget_usd = float(monthly_budget_usd)
        # Phase A/B: durable B reservation, then disabled A and immutable receipt.
        async with self.transaction() as connection:
            await connection.execute(
                text("SELECT pg_advisory_xact_lock(hashtextextended(:request,0))"),
                {"request": request_id},
            )
            existing = await self.lock(connection, request_id)
            principal, token_hash = await self.authenticate(connection, session_token, csrf)
            operation = canonical_digest(
                {
                    "principal": principal,
                    "name": name,
                    "slug": slug,
                    "kind": kind,
                    "attach_session": attach_session,
                    "monthly_budget_usd": monthly_budget_usd,
                }
            )
            if await connection.scalar(
                text(
                    "SELECT 1 FROM tenant_tombstones WHERE org_id=:tenant OR original_name=:name LIMIT 1"
                ),
                {"tenant": existing["tenant_id"] if existing else "", "name": name},
            ):
                raise ProvisioningAuthorizationError("Tombstoned tenant identity or name")
            self.readiness_epoch()
            if existing:
                reservation = self.reservations.get(
                    deployment_id=self.trust.deployment_id, request_id=request_id
                )
                if reservation is None:
                    raise ProvisioningAuthorizationError(
                        "Store B provisioning intent is missing or rolled back"
                    )
            else:
                reservation = self.reservations.reserve(
                    deployment_id=self.trust.deployment_id,
                    request_id=request_id,
                    principal_id=principal,
                    operation_digest=operation,
                )
            tenant = reservation.tenant_id
            pending_digest = canonical_digest(
                {
                    "deployment": self.trust.deployment_id,
                    "request": request_id,
                    "tenant": tenant,
                    "generation": reservation.generation_id,
                    "principal": principal,
                    "operation": operation,
                }
            )
            if existing:
                if (
                    existing["tenant_id"],
                    existing["generation_id"],
                    existing["principal_id"],
                    existing["operation_digest"],
                    existing["pending_receipt_digest"],
                ) != (tenant, reservation.generation_id, principal, operation, pending_digest):
                    raise ProvisioningAuthorizationError("Conflicting persisted creation evidence")
            else:
                if (
                    self.provider.get_state(tenant) is not None
                    or self.ledger.publication(tenant) is not None
                ):
                    raise ProvisioningAuthorizationError(
                        "Store A rollback or tenant resurrection refused"
                    )
                created_at = datetime.now(UTC).isoformat()
                await connection.execute(
                    text(
                        "INSERT INTO organizations(id,name,slug,monthly_budget_usd,created_at,plan,governance_status,workspace_kind,owner_user_id,settings_json,sso_required,mfa_required) "
                        "VALUES(:tenant,:name,:slug,:budget,:now,'FREE','DISABLED',:kind,:principal,'{}',0,0)"
                    ),
                    {
                        "tenant": tenant,
                        "name": name,
                        "slug": slug,
                        "now": created_at,
                        "kind": kind,
                        "principal": principal,
                        "budget": monthly_budget_usd,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO tenant_provisioning_records(tenant_id,deployment_id,request_id,generation_id,principal_id,operation_digest,pending_receipt_digest,security_epoch,revocation_floor,state) "
                        "VALUES(:tenant,:deployment,:request,:generation,:principal,:operation,:pending,1,1,'PENDING')"
                    ),
                    {
                        "tenant": tenant,
                        "deployment": self.trust.deployment_id,
                        "request": request_id,
                        "generation": reservation.generation_id,
                        "principal": principal,
                        "operation": operation,
                        "pending": pending_digest,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO web_memberships(id,user_id,org_id,role,status,created_at,updated_at,accepted_at) "
                        "VALUES(:id,:principal,:tenant,'OWNER','ACTIVE',:now,:now,:now)"
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "principal": principal,
                        "tenant": tenant,
                        "now": created_at,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO governance_revocation_epochs(organization_id,scope,epoch,updated_at) "
                        "VALUES(:tenant,'governance',1,:now)"
                    ),
                    {"tenant": tenant, "now": created_at},
                )
                for env in ("DEVELOPMENT", "STAGING", "PRODUCTION"):
                    await connection.execute(
                        text(
                            "INSERT INTO enterprise_environments(id,org_id,type,name,status,created_at,metadata_json) "
                            "VALUES(:id,:tenant,:type,:name,'ACTIVE',:now,:metadata)"
                        ),
                        {
                            "id": str(uuid.uuid4()),
                            "tenant": tenant,
                            "type": env,
                            "name": env.title(),
                            "now": created_at,
                            "metadata": json.dumps({"stricter_defaults": env == "PRODUCTION"}),
                        },
                    )

        async def verify_stage(connection, row):
            who, _ = await self.authenticate(connection, session_token, csrf)
            if who != principal or row["principal_id"] != principal:
                raise ProvisioningAuthorizationError("Creation principal changed")
            current = (
                await connection.execute(
                    text(
                        "SELECT name,slug,workspace_kind,monthly_budget_usd,owner_user_id,plan,governance_status "
                        "FROM organizations WHERE id=:tenant"
                    ),
                    {"tenant": tenant},
                )
            ).one()
            expected_status = "ACTIVE" if row["state"] == "COMPLETE" else "DISABLED"
            if tuple(current) != (
                name,
                slug,
                kind,
                monthly_budget_usd,
                principal,
                "FREE",
                expected_status,
            ):
                raise ProvisioningAuthorizationError("Committed Store A creation evidence changed")
            self.readiness_epoch()

        # Phase C: commit the signed operation before B publication so a process
        # death can be reconciled without synthesizing a replacement generation.
        async with self.transaction() as connection:
            row = await self.lock(connection, request_id)
            await verify_stage(connection, row)
            if row["state"] == "PENDING":
                published = self.ledger.publication(tenant)
                if published is None:
                    now = int(time.time())
                    manifest = ProvisioningManifest(
                        deployment_id=self.trust.deployment_id,
                        environment=self.trust.environment,
                        postgres_identity=self.trust.postgres_identity,
                        store_b_identity=self.trust.store_b_identity,
                        request_id=request_id,
                        principal_id=principal,
                        tenant_id=tenant,
                        generation_id=reservation.generation_id,
                        operation_digest=operation,
                        pending_receipt_digest=pending_digest,
                        readiness_epoch=self.readiness_epoch(),
                        security_epoch=1,
                        revocation_floor=1,
                        created_at=now,
                        expires_at=now + 60,
                        nonce=secrets.token_hex(32),
                        controller_id=self.trust.controller_id,
                    )
                    await connection.execute(
                        text(
                            "UPDATE tenant_provisioning_records SET publication_manifest=:manifest,publication_signature=:signature WHERE tenant_id=:tenant AND state='PENDING'"
                        ),
                        {
                            "manifest": json.dumps(asdict(manifest), sort_keys=True),
                            "signature": self.sign(manifest),
                            "tenant": tenant,
                        },
                    )
        async with self.transaction() as connection:
            row = await self.lock(connection, request_id)
            await verify_stage(connection, row)
            self.readiness_epoch()
            if row["state"] == "PENDING":
                manifest = ProvisioningManifest(**json.loads(row["publication_manifest"]))
                if (
                    manifest.pending_receipt_digest != pending_digest
                    or manifest.generation_id != reservation.generation_id
                ):
                    raise ProvisioningAuthorizationError("Committed publication evidence mismatch")
                published = self.ledger.publication(tenant)
                if published is None:
                    self.ledger.publish(manifest, row["publication_signature"])
                elif published.digest() != manifest.digest():
                    raise ProvisioningAuthorizationError(
                        "Interrupted publication evidence mismatch"
                    )
                await connection.execute(
                    text(
                        "UPDATE tenant_provisioning_records SET state='PUBLISHED',publication_digest=:digest WHERE tenant_id=:tenant AND state='PENDING'"
                    ),
                    {"tenant": tenant, "digest": manifest.digest()},
                )
        # Phase D: guarded final A CAS, still denied at admission until B COMPLETE.
        async with self.transaction() as connection:
            row = await self.lock(connection, request_id)
            await verify_stage(connection, row)
            self.readiness_epoch()
            published = self.ledger.publication(tenant)
            lifecycle = self.provider.get_state(tenant)
            if (
                published is None
                or published.digest() != row["publication_digest"]
                or lifecycle is None
                or lifecycle.state.value != "ACTIVE"
                or lifecycle.generation_id != reservation.generation_id
                or lifecycle.security_epoch != row["security_epoch"]
                or lifecycle.revocation_floor != row["revocation_floor"]
            ):
                raise ProvisioningAuthorizationError("Live publication evidence is inconsistent")
            if row["state"] == "PUBLISHED":
                receipt = {
                    "receipt_id": canonical_digest(
                        {"deployment": self.trust.deployment_id, "request": request_id}
                    ),
                    "deployment": self.trust.deployment_id,
                    "request": request_id,
                    "tenant": tenant,
                    "principal": principal,
                    "pending": pending_digest,
                    "publication": published.digest(),
                    "generation": reservation.generation_id,
                    "security_epoch": row["security_epoch"],
                    "revocation_floor": row["revocation_floor"],
                    "from": "DISABLED",
                    "to": "ACTIVE",
                    "action": "FINALIZE_TENANT",
                }
                completion_digest = canonical_digest(receipt)
                await connection.execute(
                    text(
                        "INSERT INTO tenant_provisioning_outbox(receipt_id,tenant_id,generation_id,receipt_digest,receipt_json,created_at) "
                        "VALUES(:id,:tenant,:generation,:digest,:payload,:now)"
                    ),
                    {
                        "id": receipt["receipt_id"],
                        "tenant": tenant,
                        "generation": reservation.generation_id,
                        "digest": completion_digest,
                        "payload": json.dumps(receipt, sort_keys=True, separators=(",", ":")),
                        "now": datetime.now(UTC).isoformat(),
                    },
                )
                await connection.execute(
                    text(
                        "UPDATE tenant_provisioning_records SET state='COMPLETE',completion_digest=:digest WHERE tenant_id=:tenant AND state='PUBLISHED'"
                    ),
                    {"tenant": tenant, "digest": completion_digest},
                )
                result = await connection.execute(
                    text(
                        "UPDATE organizations SET governance_status='ACTIVE' WHERE id=:tenant AND governance_status='DISABLED' AND owner_user_id=:principal"
                    ),
                    {"tenant": tenant, "principal": principal},
                )
                if result.rowcount != 1:
                    raise ProvisioningAuthorizationError("Final tenant activation CAS failed")
        # Phase E: both committed stores must match before reporting success.
        async with self.transaction() as connection:
            row = await self.lock(connection, request_id)
            await verify_stage(connection, row)
            complete = self.ledger.completion(tenant)
            if complete is None:
                now = int(time.time())
                manifest = replace(
                    published,
                    action="COMPLETE_TENANT_PROVISIONING",
                    publication_digest=published.digest(),
                    completion_digest=row["completion_digest"],
                    created_at=now,
                    expires_at=now + 60,
                    nonce=secrets.token_hex(32),
                    readiness_epoch=self.readiness_epoch(),
                )
                self.ledger.complete(manifest, self.sign(manifest))
                complete = self.ledger.completion(tenant)
            if (
                complete is None
                or complete.completion_digest != row["completion_digest"]
                or row["state"] != "COMPLETE"
            ):
                raise ProvisioningAuthorizationError("Cross-store completion is unresolved")
            if attach_session:
                await connection.execute(
                    text("UPDATE web_sessions SET org_id=:tenant WHERE token_hash=:token"),
                    {"tenant": tenant, "token": token_hash},
                )
        return tenant
