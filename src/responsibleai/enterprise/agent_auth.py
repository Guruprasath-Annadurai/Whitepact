# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Default-disabled, online development agent PoP authentication; never grants execution."""

from __future__ import annotations

import base64
import hashlib
import json
import secrets
from datetime import UTC, datetime

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from sqlalchemy import (
    Column,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    delete,
    insert,
    select,
    text,
    update,
)

from responsibleai.db.engine import (
    authority_recovery_requests,
    governance_consent_proofs,
    governance_delegations,
    governance_root_authority_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection, lock_epoch
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.authority.assurance import require_recent_owner, timestamp
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter
from responsibleai.enterprise.service import Actor
from responsibleai.environment import is_production
from responsibleai.rbac.models import OrgContext, Role

ISSUER = "whitepact:dev-agent-auth:v1"
AUDIENCE = "whitepact:dev-agent-intent:v1"
CREDENTIAL_SECONDS = 120
CHALLENGE_SECONDS = 30
INTENT_PATH = "/api/dev/agent-auth/intent"
prototype_metadata = MetaData()
credentials = Table(
    "dev_b1_credentials",
    prototype_metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), nullable=False, index=True),
    Column("agent_id", String(64), nullable=False),
    Column("binding", Text, nullable=False),
    Column("issued", Integer, nullable=False),
    Column("expires", Integer, nullable=False),
    Column("revoked", Integer, nullable=False, default=0),
)
challenges = Table(
    "dev_b1_challenges",
    prototype_metadata,
    Column("id", String(64), primary_key=True),
    Column("org_id", String(36), nullable=False, index=True),
    Column("agent_id", String(64), nullable=False),
    Column("kind", String(16), nullable=False),
    Column("message", Text, nullable=False),
    Column("issued", Integer, nullable=False),
    Column("expires", Integer, nullable=False),
    Column("consumed", Integer, nullable=False, default=0),
)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def canonical(value) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(encoded.encode()) > 16384:
        raise EnterpriseError("B1_INVALID", "Prototype request exceeds16KiB.", 400)
    return encoded


def reject(message="Agent proof or current qualification is invalid."):
    return EnterpriseError("B1_AUTHENTICATION_DENIED", message, 403)


def alive(row, now):
    return (
        row
        and not row.revoked_at
        and (not getattr(row, "not_before", None) or timestamp(row.not_before) <= now)
        and (not row.expires_at or now < timestamp(row.expires_at))
    )


class DevelopmentAgentAuth:
    def __init__(self, engine, settings):
        self.engine, self.settings = engine, settings
        self.limiter = DurableIdentityRateLimiter(engine)

    def gate(self):
        if (
            not getattr(self.settings, "dev_agent_auth_enabled", False)
            or self.settings.environment != "development"
            or self.settings.is_production
            or is_production()
        ):
            raise EnterpriseError(
                "B1_DISABLED", "Development agent authentication is unavailable.", 404
            )
        if self.engine.raw.dialect.name != "postgresql":
            raise EnterpriseError(
                "B1_POSTGRES_REQUIRED", "Qualified PostgreSQL storage is required.", 503
            )

    async def initialize(self):
        self.gate()
        async with self.engine.raw.begin() as conn:
            await conn.execute(text("SELECT pg_advisory_xact_lock(759672917)"))
            await conn.run_sync(prototype_metadata.create_all)

    async def _binding(self, conn, actor, agent_id, public_key):
        epoch = await lock_epoch(conn, actor.org_id)
        await require_recent_owner(conn, actor, actor.org_id)
        now = datetime.now(UTC)
        pending = await conn.scalar(
            select(authority_recovery_requests.c.id)
            .where(
                authority_recovery_requests.c.org_id == actor.org_id,
                authority_recovery_requests.c.status == "PENDING",
                authority_recovery_requests.c.expires_at > now.isoformat(),
            )
            .limit(1)
        )
        if pending:
            raise reject()
        agent = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.id == agent_id,
                    trust_fabric_principals.c.org_id == actor.org_id,
                    trust_fabric_principals.c.principal_type == "AI_AGENT",
                    trust_fabric_principals.c.lifecycle_state == "ACTIVE",
                )
            )
        ).first()
        if not agent:
            raise reject()
        metadata = json.loads(agent.metadata_json or "{}")
        app_id = metadata.get("application_id")
        app = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.id == app_id,
                    trust_fabric_principals.c.org_id == actor.org_id,
                    trust_fabric_principals.c.principal_type == "APPLICATION",
                    trust_fabric_principals.c.lifecycle_state == "ACTIVE",
                )
            )
        ).first()
        principal = (
            await conn.execute(
                select(trust_fabric_principals).where(
                    trust_fabric_principals.c.id == actor.user_id,
                    trust_fabric_principals.c.org_id == actor.org_id,
                    trust_fabric_principals.c.lifecycle_state == "ACTIVE",
                )
            )
        ).first()
        if (
            not app
            or not principal
            or json.loads(app.metadata_json or "{}").get("owner_user_id") != actor.user_id
        ):
            raise reject()
        root = (
            await conn.execute(
                select(governance_root_authority_records)
                .where(
                    governance_root_authority_records.c.organization_id == actor.org_id,
                    governance_root_authority_records.c.subject_id == actor.user_id,
                    governance_root_authority_records.c.revoked_at.is_(None),
                )
                .order_by(governance_root_authority_records.c.issued_at.desc())
                .limit(1)
            )
        ).first()
        delegation = (
            await conn.execute(
                select(governance_delegations)
                .where(
                    governance_delegations.c.org_id == actor.org_id,
                    governance_delegations.c.to_identity_id == agent_id,
                    governance_delegations.c.from_identity_id == actor.user_id,
                    governance_delegations.c.revoked_at.is_(None),
                )
                .order_by(governance_delegations.c.granted_at.desc())
                .limit(1)
            )
        ).first()
        consent = (
            await conn.execute(
                select(governance_consent_proofs)
                .where(
                    governance_consent_proofs.c.organization_id == actor.org_id,
                    governance_consent_proofs.c.grantee_id == agent_id,
                    governance_consent_proofs.c.revoked_at.is_(None),
                )
                .order_by(governance_consent_proofs.c.consented_at.desc())
                .limit(1)
            )
        ).first()
        trust_root = (
            await conn.execute(
                select(trust_fabric_trust_roots).where(
                    trust_fabric_trust_roots.c.org_id == actor.org_id,
                    trust_fabric_trust_roots.c.root_principal_id == actor.user_id,
                    trust_fabric_trust_roots.c.status == "ACTIVE",
                )
            )
        ).first()
        if (
            not all(alive(row, now) for row in (root, delegation, consent))
            or not trust_root
            or consent.consenting_root_id != root.root_id
        ):
            raise reject()
        try:
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
        except (ValueError, TypeError):
            raise reject() from None
        return dict(
            issuer=ISSUER,
            audience=AUDIENCE,
            org_id=actor.org_id,
            owner_id=actor.user_id,
            session_id=actor.session_id,
            agent_id=agent_id,
            application_id=app_id,
            root_id=root.root_id,
            root_key_digest=digest(trust_root.root_public_key),
            delegation_id=delegation.id,
            consent_id=consent.consent_id,
            public_key=public_key,
            epoch=epoch,
        )

    async def _challenge(self, conn, binding, kind, **fields):
        identifier = secrets.token_hex(32)
        issued = int(datetime.now(UTC).timestamp())
        expires = issued + CHALLENGE_SECONDS
        message = canonical(
            dict(binding=binding, kind=kind, nonce=identifier, expires=expires, **fields)
        )
        await conn.execute(
            delete(challenges).where(
                challenges.c.org_id == binding["org_id"],
                challenges.c.agent_id == binding["agent_id"],
                challenges.c.kind == kind,
            )
        )
        await conn.execute(
            insert(challenges).values(
                id=identifier,
                org_id=binding["org_id"],
                agent_id=binding["agent_id"],
                kind=kind,
                message=message,
                issued=issued,
                expires=expires,
                consumed=0,
            )
        )
        return dict(
            challenge_id=identifier,
            message=base64.urlsafe_b64encode(message.encode()).decode(),
            expires_at=expires,
        )

    async def begin_issue(self, actor, agent_id, public_key, *, rotate_from=None):
        self.gate()
        await self.limiter.check(
            f"b1-issue:{actor.org_id}:{actor.user_id}", limit=10, window_seconds=60
        )
        async with self.engine.raw.begin() as conn:
            binding = await self._binding(conn, actor, agent_id, public_key)
            return await self._challenge(conn, binding, "issue", rotate_from=rotate_from)

    async def _consume(self, conn, identifier, signature, kind, org_id):
        row = (
            await conn.execute(
                select(challenges)
                .where(
                    challenges.c.id == identifier,
                    challenges.c.kind == kind,
                    challenges.c.org_id == org_id,
                    challenges.c.consumed == 0,
                )
                .with_for_update()
            )
        ).first()
        now = int(datetime.now(UTC).timestamp())
        if not row or not row.issued <= now < row.expires <= row.issued + CHALLENGE_SECONDS:
            raise reject()
        payload = json.loads(row.message)
        if (
            payload.get("nonce") != row.id
            or payload.get("expires") != row.expires
            or payload.get("kind") != kind
        ):
            raise reject()
        try:
            signature_bytes = base64.b64decode(
                signature + "=" * (-len(signature) % 4), altchars=b"-_", validate=True
            )
            Ed25519PublicKey.from_public_bytes(
                bytes.fromhex(payload["binding"]["public_key"])
            ).verify(signature_bytes, row.message.encode())
        except (InvalidSignature, ValueError, TypeError):
            raise reject() from None
        consumed = await conn.execute(
            update(challenges)
            .where(challenges.c.id == identifier, challenges.c.consumed == 0)
            .values(consumed=1)
        )
        if consumed.rowcount != 1:
            raise reject()
        return payload

    async def finish_issue(self, actor, challenge_id, signature):
        self.gate()
        await self.limiter.check(
            f"b1-issue:{actor.org_id}:{actor.user_id}", limit=10, window_seconds=60
        )
        token = secrets.token_urlsafe(32)
        async with self.engine.raw.begin() as conn:
            await lock_epoch(conn, actor.org_id)
            payload = await self._consume(conn, challenge_id, signature, "issue", actor.org_id)
            binding = payload["binding"]
            if binding != await self._binding(
                conn, actor, binding["agent_id"], binding["public_key"]
            ):
                raise reject()
            live = (
                await conn.execute(
                    select(credentials)
                    .where(
                        credentials.c.org_id == actor.org_id,
                        credentials.c.agent_id == binding["agent_id"],
                        credentials.c.revoked == 0,
                        credentials.c.expires > int(datetime.now(UTC).timestamp()),
                    )
                    .with_for_update()
                )
            ).first()
            if (live and payload["rotate_from"] != live.id) or (
                payload["rotate_from"] and not live
            ):
                raise reject("An active credential or rotation predecessor conflicts.")
            if live:
                binding["epoch"] = await bump_epoch_on_connection(conn, actor.org_id)
            await conn.execute(
                update(credentials)
                .where(
                    credentials.c.org_id == actor.org_id,
                    credentials.c.agent_id == binding["agent_id"],
                )
                .values(revoked=1)
            )
            issued = int(datetime.now(UTC).timestamp())
            expires = issued + CREDENTIAL_SECONDS
            await conn.execute(
                insert(credentials).values(
                    id=digest(token),
                    org_id=actor.org_id,
                    agent_id=binding["agent_id"],
                    binding=canonical(binding),
                    issued=issued,
                    expires=expires,
                    revoked=0,
                )
            )
            await EnterpriseAuditLog(self.engine).record(
                action="DEV_B1_CREDENTIAL_ISSUED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=actor.org_id,
                target_type="agent_credential",
                target_id=digest(token),
                result="SUCCESS",
                conn=conn,
                metadata={
                    "agent_id": binding["agent_id"],
                    "epoch": binding["epoch"],
                    "development_only": True,
                },
            )
        return dict(
            credential=token,
            credential_id=digest(token),
            issuer=ISSUER,
            audience=AUDIENCE,
            expires_at=expires,
            authentication_only=True,
            development_only=True,
        )

    async def _credential(self, conn, token, audience):
        if not isinstance(token, str) or len(token) > 128 or audience != AUDIENCE:
            raise reject()
        row = (
            await conn.execute(select(credentials).where(credentials.c.id == digest(token)))
        ).first()
        now = int(datetime.now(UTC).timestamp())
        if (
            not row
            or row.revoked
            or not row.issued <= now < row.expires <= row.issued + CREDENTIAL_SECONDS
        ):
            raise reject()
        binding = json.loads(row.binding)
        if binding["issuer"] != ISSUER or binding["audience"] != AUDIENCE:
            raise reject()
        actor = Actor(
            "human",
            binding["owner_id"],
            binding["owner_id"],
            binding["org_id"],
            Role.OWNER,
            "ACTIVE",
            session_id=binding["session_id"],
        )
        if binding != await self._binding(conn, actor, binding["agent_id"], binding["public_key"]):
            raise reject()
        return row, binding

    async def _request_limit(self, token, audience):
        await self.limiter.check("b1-request:unauthenticated", limit=600, window_seconds=60)
        async with self.engine.raw.begin() as conn:
            row, _ = await self._credential(conn, token, audience)
            credential_id = row.id
        # Never acquire a second pooled connection while holding authority locks.
        # The operation transaction rechecks qualification after this limit check.
        await self.limiter.check(f"b1-request:{credential_id}", limit=60, window_seconds=60)

    async def begin_request(self, token, *, audience, method, path, body):
        self.gate()
        if method != "POST" or path != INTENT_PATH:
            raise reject()
        await self._request_limit(token, audience)
        async with self.engine.raw.begin() as conn:
            row, binding = await self._credential(conn, token, audience)
            return await self._challenge(
                conn,
                binding,
                "request",
                credential_id=row.id,
                method=method,
                path=path,
                body_digest=digest(canonical(body)),
            )

    async def authenticate(self, token, challenge_id, signature, *, audience, method, path, body):
        self.gate()
        await self._request_limit(token, audience)
        async with self.engine.raw.begin() as conn:
            row, binding = await self._credential(conn, token, audience)
            payload = await self._consume(
                conn, challenge_id, signature, "request", binding["org_id"]
            )
            if (
                payload["binding"] != binding
                or payload["credential_id"] != row.id
                or payload["method"] != method
                or payload["path"] != path
                or payload["body_digest"] != digest(canonical(body))
            ):
                raise reject()
        return OrgContext(
            key_id=binding["agent_id"],
            org_id=binding["org_id"],
            role=Role.ANALYST,
            key_name="development-agent-pop",
            authentication_method="agent_pop",
            authentication_epoch=binding["epoch"],
        )

    async def revoke(self, actor, credential_id):
        self.gate()
        async with self.engine.raw.begin() as conn:
            await lock_epoch(conn, actor.org_id)
            await require_recent_owner(conn, actor, actor.org_id)
            row = (
                await conn.execute(
                    select(credentials).where(
                        credentials.c.id == credential_id, credentials.c.org_id == actor.org_id
                    )
                )
            ).first()
            if not row or json.loads(row.binding)["owner_id"] != actor.user_id:
                raise reject()
            await conn.execute(
                update(credentials).where(credentials.c.id == credential_id).values(revoked=1)
            )
            await bump_epoch_on_connection(conn, actor.org_id)
            await EnterpriseAuditLog(self.engine).record(
                action="DEV_B1_CREDENTIAL_REVOKED",
                actor_type=actor.actor_type,
                actor_id=actor.actor_id,
                org_id=actor.org_id,
                target_type="agent_credential",
                target_id=credential_id,
                result="SUCCESS",
                conn=conn,
                metadata={"development_only": True},
            )
        return dict(revoked=True, development_only=True)
