# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit non-production reference contract for identity software tests.

Setting these variables does not enroll a real identity provider and does not
authorize the canonical customer journey.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import uuid
from datetime import UTC, datetime

from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService

CONTRACT_ENV = {
    "WHITEPACT_IDENTITY_REFERENCE_CONTRACT": "1",
    "WHITEPACT_IDENTITY_APPROVED_PROVIDERS": "hmac-reference",
    "WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS": "government_id",
}


def enable_reference_contract() -> None:
    for key, value in CONTRACT_ENV.items():
        os.environ[key] = value


def sign_identity_event(
    body: dict, secret: str = "test-webhook-secret", ts: str | None = None
) -> tuple[bytes, str, str]:
    timestamp = ts or datetime.now(UTC).isoformat()
    payload = json.dumps(body, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), payload + timestamp.encode(), hashlib.sha256).hexdigest()
    return payload, signature, timestamp


async def verify_human_reference(
    engine,
    user_id: str,
    *,
    secret: str = "test-webhook-secret",
    event_id: str | None = None,
) -> None:
    enable_reference_contract()
    provider = HmacVerificationProvider(secret)
    verification = VerificationService(engine, provider)
    started = await verification.start_human_verification(user_id)
    body = {
        "event_id": event_id or f"evt-{uuid.uuid4().hex}",
        "event_type": "identity.verification",
        "subject_id": user_id,
        "reference_id": started["session_id"],
        "outcome": "VERIFIED",
        "assurance_level": "government_id",
    }
    payload, signature, timestamp = sign_identity_event(body, secret)
    await verification.apply_provider_event(
        payload=payload, signature=signature, timestamp=timestamp, expected_user_id=user_id
    )


async def verify_org_reference(
    engine,
    org_id: str,
    actor_user_id: str,
    *,
    secret: str = "test-webhook-secret",
    event_id: str,
    legal_name: str,
) -> None:
    enable_reference_contract()
    provider = HmacVerificationProvider(secret)
    verification = VerificationService(engine, provider)
    started = await verification.start_org_verification(org_id, actor_user_id=actor_user_id)
    body = {
        "event_id": event_id,
        "event_type": "identity.verification",
        "kind": "organization",
        "org_id": org_id,
        "reference_id": started["session_id"],
        "outcome": "VERIFIED",
        "accountable_owner_user_id": actor_user_id,
        "legal_name": legal_name,
    }
    payload, signature, timestamp = sign_identity_event(body, secret)
    await verification.apply_provider_event(
        payload=payload, signature=signature, timestamp=timestamp, expected_org_id=org_id
    )
