# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Founder-ratified A2 account/authenticator control, never legal identity proof."""

import json
from datetime import UTC, datetime

from sqlalchemy import select

from responsibleai.db.engine import (
    org_security_policies,
    organizations,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.enterprise.errors import EnterpriseError

MAX_UV_AGE_SECONDS = 300


def denied():
    return EnterpriseError(
        "A2_AUTHENTICATION_REQUIRED", "Recent verified owner WebAuthn UV is required.", 403
    )


def timestamp(value):
    result = datetime.fromisoformat(value)
    return result.replace(tzinfo=UTC) if result.tzinfo is None else result


async def require_recent_owner(conn, actor, org_id):
    """Recheck persisted facts under write locks; never trust caller assurance flags."""
    if not actor.session_id:
        raise denied()
    rows = []
    for table, conditions in (
        (web_users, (web_users.c.id == actor.user_id,)),
        (organizations, (organizations.c.id == org_id,)),
        (
            web_memberships,
            (web_memberships.c.user_id == actor.user_id, web_memberships.c.org_id == org_id),
        ),
        (web_sessions, (web_sessions.c.session_id == actor.session_id,)),
    ):
        rows.append(
            (await conn.execute(select(table).where(*conditions).with_for_update())).first()
        )
    user, org, member, session = rows
    if not all(rows) or actor.org_id != org_id or actor.actor_id != actor.user_id:
        raise denied()
    if (
        user.disabled
        or not user.email_verified_at
        or user.verification_status in {"SUSPENDED", "REJECTED"}
        or org.governance_status != "ACTIVE"
        or org.deactivated_at
        or org.owner_user_id != actor.user_id
        or member.role != "OWNER"
        or member.status != "ACTIVE"
        or session.user_id != actor.user_id
        or session.org_id != org_id
        or session.revoked
    ):
        raise denied()
    now = datetime.now(UTC)
    try:
        methods = json.loads(session.auth_methods_json or "[]")
        if (
            not isinstance(methods, list)
            or "PASSKEY_UV" not in methods
            or not session.phishing_resistant
        ):
            raise denied()
        if not 0 <= (now - timestamp(session.auth_time)).total_seconds() <= MAX_UV_AGE_SECONDS:
            raise denied()
        if now >= timestamp(session.expires_at) or (
            session.inactivity_expires_at and now >= timestamp(session.inactivity_expires_at)
        ):
            raise denied()
    except (ValueError, TypeError):
        raise denied() from None
    policy = (
        await conn.execute(
            select(org_security_policies).where(org_security_policies.c.org_id == org_id)
        )
    ).first()
    if policy and policy.sso_enforcement == "SSO_REQUIRED" and "ENTERPRISE_SSO" not in methods:
        raise denied()
    return session
