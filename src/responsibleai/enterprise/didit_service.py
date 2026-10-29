# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Didit session binding, durable evidence and serialized identity decisions.

Uses existing provider-event/session tables: init markers bind tenant and
provider configuration; event markers enforce idempotency and source ordering.
No raw documents, decision bodies or secrets are retained.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import (
    identity_provider_events,
    identity_verifications,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.didit import DiditProvider, canonical, deny
from responsibleai.enterprise.verification import VerificationService, _iso


class DiditVerificationService(VerificationService):
    def __init__(self, engine, provider: DiditProvider):
        super().__init__(engine, provider)

    def _context_hash(self, user, org):
        p = self._provider
        return hashlib.sha256(
            canonical(
                dict(
                    subject=user,
                    tenant=org,
                    application=p.application_id,
                    workflow=p.workflow_id,
                    environment=p.environment,
                )
            )
        ).hexdigest()

    async def start_human_verification(self, user_id, *, org_id=None, request_id=None):
        if not org_id:
            raise deny("CROSS_TENANT", "Active tenant context is required for Didit enrollment.")
        async with self._engine.raw.connect() as conn:
            user = (
                await conn.execute(select(web_users).where(web_users.c.id == user_id))
            ).fetchone()
            member = (
                await conn.execute(
                    select(web_memberships.c.id).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
        if not user or user.verification_status == "SUSPENDED" or not member:
            raise deny("CROSS_TENANT")
        session = await asyncio.to_thread(
            self._provider.start_session, subject_id=user_id, return_url=None
        )
        sid = session["session_id"]
        try:
            async with self._engine.raw.begin() as conn:
                # Duplicate provider references are not rebound to another caller.
                await conn.execute(
                    insert(identity_verifications).values(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        status="REVIEW_REQUIRED",
                        provider=self._provider.name,
                        provider_reference_id=sid,
                        created_at=_iso(),
                        updated_at=_iso(),
                    )
                )
                await conn.execute(
                    insert(identity_provider_events).values(
                        id=str(uuid.uuid4()),
                        provider=self._provider.name,
                        event_id="init:" + sid,
                        user_id=user_id,
                        org_id=org_id,
                        payload_hash=self._context_hash(user_id, org_id),
                        received_at=_iso(),
                    )
                )
                await self.audit.record(
                    actor_type="human",
                    actor_id=user_id,
                    org_id=org_id,
                    action="verification.initiated",
                    target_type="user",
                    target_id=user_id,
                    result="ALLOWED",
                    request_id=request_id,
                    metadata={
                        "provider": self._provider.name,
                        "session_id": sid,
                        "workflow_id": self._provider.workflow_id,
                        "environment": self._provider.environment,
                    },
                    conn=conn,
                )
        except IntegrityError as exc:
            raise deny("VERIFICATION_CONFLICT", "Provider session cannot be rebound.") from exc
        return {
            "verification_id": sid,
            **session,
            "status": "REVIEW_REQUIRED",
            "environment": self._provider.environment,
        }

    async def apply_didit_event(
        self, *, payload, signature, timestamp, test_delivery=False, request_id=None
    ):
        event = self._provider.verify_webhook(
            payload=payload, signature=signature, timestamp=timestamp, test_delivery=test_delivery
        )
        if test_delivery:
            # Try Webhook uses sample session IDs: prove delivery without
            # creating/binding a subject or changing any identity state.
            if self._provider.environment != "sandbox":
                raise deny()
            return await self._record_test(event, request_id)
        session = event.get("session_id")
        try:
            uuid.UUID(session)
        except (TypeError, ValueError, AttributeError):
            raise deny() from None
        digest = hashlib.sha256(
            canonical({k: v for k, v in event.items() if k != "timestamp"})
        ).hexdigest()
        async with self._engine.raw.connect() as conn:
            prior = (
                await conn.execute(
                    select(identity_provider_events).where(
                        identity_provider_events.c.provider == self._provider.name,
                        identity_provider_events.c.event_id == "event:" + event["event_id"],
                    )
                )
            ).fetchone()
        if prior:
            if prior.payload_hash != digest:
                raise deny("PROVIDER_REPLAY")
            return {"status": "ALREADY_PROCESSED", "duplicate": True, "identity_transition": False}
        # Provider retrieval is an actual authenticated API request, not the
        # browser redirect or a caller's asserted result. Never auto-retry it.
        decision = await asyncio.to_thread(self._provider.retrieve_decision, session)
        self._provider.validate_decision(decision, event)
        return await self._commit_event(event, request_id)

    async def _record_test(self, event, request_id):
        key = "test:" + event["event_id"]
        body = {k: v for k, v in event.items() if k != "timestamp"}
        digest = hashlib.sha256(canonical(body)).hexdigest()
        try:
            async with self._engine.raw.begin() as conn:
                found = (
                    await conn.execute(
                        select(identity_provider_events).where(
                            identity_provider_events.c.provider == self._provider.name,
                            identity_provider_events.c.event_id == key,
                        )
                    )
                ).fetchone()
                if found:
                    if found.payload_hash != digest:
                        raise deny("PROVIDER_REPLAY")
                    return {
                        "status": "TEST_RECEIPT_ONLY",
                        "duplicate": True,
                        "identity_transition": False,
                    }
                await conn.execute(
                    insert(identity_provider_events).values(
                        id=str(uuid.uuid4()),
                        provider=self._provider.name,
                        event_id=key,
                        payload_hash=digest,
                        received_at=_iso(),
                    )
                )
                await self.audit.record(
                    actor_type="provider",
                    actor_id=self._provider.name,
                    action="verification.test_delivery",
                    target_type="provider",
                    target_id=self._provider.application_id,
                    result="ALLOWED",
                    request_id=request_id,
                    metadata={
                        "event_id": event["event_id"],
                        "environment": "sandbox",
                        "identity_transition": False,
                    },
                    conn=conn,
                )
        except IntegrityError:
            # Racing identical test deliveries get a deterministic retry on
            # the next HTTP delivery; never claim a record we could not commit.
            raise deny("VERIFICATION_CONFLICT", "Reconcile the original test delivery.") from None
        return {"status": "TEST_RECEIPT_ONLY", "duplicate": False, "identity_transition": False}

    async def _commit_event(self, event, request_id):
        p = self._provider
        sid = event["session_id"]
        digest = hashlib.sha256(
            canonical({k: v for k, v in event.items() if k != "timestamp"})
        ).hexdigest()
        event_key = "event:" + event["event_id"]
        async with self._engine.raw.begin() as conn:
            # PostgreSQL row lock serializes decisions for one initiated
            # session across processes, in addition to unique event admission.
            binding = (
                await conn.execute(
                    select(identity_provider_events)
                    .where(
                        identity_provider_events.c.provider == p.name,
                        identity_provider_events.c.event_id == "init:" + sid,
                    )
                    .with_for_update()
                )
            ).fetchone()
            if not binding:
                raise deny("VERIFICATION_SESSION_UNKNOWN")
            if binding.user_id != event.get(
                "vendor_data"
            ) or binding.payload_hash != self._context_hash(binding.user_id, binding.org_id):
                raise deny("CROSS_TENANT")
            prior = (
                await conn.execute(
                    select(identity_provider_events).where(
                        identity_provider_events.c.provider == p.name,
                        identity_provider_events.c.event_id == event_key,
                    )
                )
            ).fetchone()
            if prior:
                if prior.payload_hash != digest:
                    raise deny("PROVIDER_REPLAY")
                return {
                    "status": "ALREADY_PROCESSED",
                    "duplicate": True,
                    "identity_transition": False,
                }
            ids = (
                (
                    await conn.execute(
                        select(identity_provider_events.c.event_id).where(
                            identity_provider_events.c.provider == p.name,
                            identity_provider_events.c.event_id.like(sid + ":%"),
                        )
                    )
                )
                .scalars()
                .all()
            )
            latest = max((int(e.split(":")[1]) for e in ids), default=-1)
            if event["created_at"] <= latest:
                raise deny(
                    "PROVIDER_EVENT_OUT_OF_ORDER",
                    "Reconcile conflicting or older provider decisions.",
                )
            current = (
                await conn.execute(
                    select(identity_verifications).where(
                        identity_verifications.c.provider == p.name,
                        identity_verifications.c.provider_reference_id == sid,
                    )
                )
            ).fetchone()
            if not current:
                raise deny("VERIFICATION_SESSION_UNKNOWN")
            mapping = {
                "Approved": "VERIFIED",
                "Declined": "REJECTED",
                "In Review": "REVIEW",
                "Not Started": "REVIEW",
                "In Progress": "REVIEW",
                "Resubmitted": "REVIEW",
                "Expired": "REJECTED",
                "Abandoned": "REJECTED",
                "Kyc Expired": "SUSPENDED",
            }
            outcome = mapping.get(event.get("status"))
            if not outcome:
                raise deny()
            if current.status == "IDENTITY_VERIFIED" and outcome != "VERIFIED":
                outcome = "SUSPENDED"
            assurance = (
                "didit_sandbox_id_liveness_face"
                if p.environment == "sandbox"
                else "didit_id_liveness_face"
            )
            normalized = {
                "subject_id": binding.user_id,
                "org_id": binding.org_id,
                "assurance_level": assurance,
                "event_type": "identity.verification",
            }
            # Durable evidence and state/audit are a single transaction: any
            # failed write rolls back authority. No external JSON persisted.
            for key in (event_key, f"{sid}:{event['created_at']}:{event['event_id']}"):
                await conn.execute(
                    insert(identity_provider_events).values(
                        id=str(uuid.uuid4()),
                        provider=p.name,
                        event_id=key,
                        user_id=binding.user_id,
                        org_id=binding.org_id,
                        payload_hash=digest,
                        received_at=_iso(),
                    )
                )
            result = await self._apply_human_outcome(
                conn,
                claimed_user_id=binding.user_id,
                outcome=outcome,
                event=normalized,
                reference_id=sid,
                request_id=request_id,
            )
            if outcome == "VERIFIED":
                # Integration starts with a short, bounded freshness window;
                # commercial assurance/retention policy is not inferred here.
                expires = _iso(datetime.now(UTC) + timedelta(hours=24))
                await conn.execute(
                    update(identity_verifications)
                    .where(identity_verifications.c.id == current.id)
                    .values(expires_at=expires)
                )
            await self.audit.record(
                actor_type="provider",
                actor_id=p.name,
                org_id=binding.org_id,
                action="verification.didit_processed",
                target_type="user",
                target_id=binding.user_id,
                result="ALLOWED",
                request_id=request_id,
                metadata={
                    "session_id": sid,
                    "event_id": event["event_id"],
                    "source_created_at": event["created_at"],
                    "environment": p.environment,
                    "decision_hash": digest,
                },
                conn=conn,
            )
            return {**result, "provider": p.name, "environment": p.environment, "duplicate": False}

    async def start_org_verification(self, *args, **kwargs):
        raise deny(
            "PROVIDER_NOT_ENROLLED", "Didit human workflow cannot establish organization authority."
        )

    async def reconcile(self, session_id, *, user_id, org_id):
        """Read-only server retrieval; never elevates without a signed event."""
        async with self._engine.raw.connect() as conn:
            binding = (
                await conn.execute(
                    select(identity_provider_events).where(
                        identity_provider_events.c.provider == self._provider.name,
                        identity_provider_events.c.event_id == "init:" + session_id,
                        identity_provider_events.c.user_id == user_id,
                        identity_provider_events.c.org_id == org_id,
                    )
                )
            ).fetchone()
        if not binding:
            raise deny("VERIFICATION_SESSION_UNKNOWN")
        decision = await asyncio.to_thread(self._provider.retrieve_decision, session_id)
        return {
            "session_id": session_id,
            "provider_status": decision.get("status"),
            "identity_transition": False,
            "required_action": "Obtain or resend the authentic signed provider event.",
        }
