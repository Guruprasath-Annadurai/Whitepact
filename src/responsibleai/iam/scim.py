# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SCIM 2.0 Identity Management & Enterprise Deprovisioning Service."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    iam_scim_users,
    trust_fabric_principals,
)
from responsibleai.iam.session import SessionService


class ScimService:
    """RFC 7643 / RFC 7644 SCIM 2.0 service enforcing cascading deprovisioning."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.session_service = SessionService(db)

    def get_service_provider_config(self) -> dict[str, Any]:
        """Return standard SCIM ServiceProviderConfig metadata."""
        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:ServiceProviderConfig"],
            "patch": {"supported": True},
            "bulk": {"supported": False},
            "filter": {"supported": True, "maxResults": 100},
            "changePassword": {"supported": False},
            "sort": {"supported": False},
            "etag": {"supported": False},
            "authenticationSchemes": [
                {
                    "name": "OAuth Bearer Token",
                    "description": "Authentication scheme using OAuth Bearer Token",
                    "type": "oauthbearertoken",
                }
            ],
        }

    async def create_user(
        self,
        *,
        org_id: str,
        user_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Provision a new user via SCIM. Strictly blocks root/owner escalation."""
        now = datetime.now(UTC).isoformat()
        user_name = user_data.get("userName") or user_data.get("name")
        if not user_name:
            raise ValueError("userName is required.")

        # Invariant: SCIM cannot create or elevate to OWNER/ROOT
        role_str = (user_data.get("role") or "ANALYST").upper()
        if role_str in {"OWNER", "ROOT"}:
            raise ValueError("SCIM cannot provision root or owner authority.")

        scim_user_id = f"scim_usr_{uuid.uuid4().hex}"
        principal_id = f"prin_{uuid.uuid4().hex}"
        external_id = user_data.get("externalId")
        active = user_data.get("active", True)

        async with self.db.raw.begin() as conn:
            # 1. Create entry in trust_fabric_principals
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=principal_id,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name=user_name,
                    lifecycle_state="ACTIVE" if active else "SUSPENDED",
                    created_at=now,
                    updated_at=now,
                    metadata_json=json.dumps({"scim_id": scim_user_id, "external_id": external_id}),
                )
            )

            # 2. Create entry in iam_scim_users
            await conn.execute(
                insert(iam_scim_users).values(
                    id=scim_user_id,
                    org_id=org_id,
                    principal_id=principal_id,
                    external_id=external_id,
                    user_name=user_name,
                    email=user_data.get("email", ""),
                    active=1 if active else 0,
                    attributes_json=json.dumps(user_data),
                    created_at=now,
                    updated_at=now,
                )
            )

        return {
            "schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"],
            "id": scim_user_id,
            "userName": user_name,
            "externalId": external_id,
            "active": active,
            "meta": {"resourceType": "User", "created": now, "lastModified": now},
        }

    async def deprovision_user(self, *, org_id: str, scim_user_id: str) -> bool:
        """Immediately deprovision a user and cascade revocation across all sessions, keys, and JIT grants."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            # Fetch user
            stmt = select(iam_scim_users).where(
                and_(
                    iam_scim_users.c.id == scim_user_id,
                    iam_scim_users.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                return False

            usr = dict(row._mapping)
            principal_id = usr["principal_id"]

            # 1. Deactivate SCIM user
            await conn.execute(
                update(iam_scim_users)
                .where(iam_scim_users.c.id == scim_user_id)
                .values(active=0, updated_at=now)
            )

            # 2. Suspend/Revoke principal in trust fabric
            await conn.execute(
                update(trust_fabric_principals)
                .where(trust_fabric_principals.c.id == principal_id)
                .values(lifecycle_state="SUSPENDED", updated_at=now)
            )

        # 3. Cascading invalidation: revoke all active sessions
        await self.session_service.revoke_all_principal_sessions(org_id=org_id, principal_id=principal_id)

        # 4. Revoke all active JIT grants
        from responsibleai.db.engine import iam_jit_grants

        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(iam_jit_grants)
                .where(
                    and_(
                        iam_jit_grants.c.org_id == org_id,
                        iam_jit_grants.c.principal_id == principal_id,
                        iam_jit_grants.c.status == "ACTIVE",
                    )
                )
                .values(status="REVOKED", revoked_at=now)
            )

        return True
