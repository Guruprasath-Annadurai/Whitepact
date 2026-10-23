# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact completion fence under PostgreSQL authority locks, never for cleanup."""

import hashlib
import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
    get_restore_readiness_gate,
)
from responsibleai.data_governance.provisioning_manifest import ProvisioningAuthorizationError
from responsibleai.data_governance.tenant_provisioning import PublicationAuthorizationLedger


async def verify_tenant_completion_evidence(
    connection: AsyncConnection,
    tenant_id: str,
    current_epoch: int,
    provider: SqliteDurableLifecycleStateProvider,
) -> None:
    """ACTIVE/ACTIVE is insufficient. Caller holds organization and epoch locks.

    No Store B lock is retained across a PostgreSQL await. Restrictive cleanup,
    uncertainty recording and containment must not require this admission fence.
    """
    if connection.dialect.name != "postgresql":
        raise ProvisioningAuthorizationError("Tenant admission requires PostgreSQL")
    if type(provider) is not SqliteDurableLifecycleStateProvider:
        raise ProvisioningAuthorizationError("Authoritative durable tenant evidence required")
    row = (
        (
            await connection.execute(
                text("SELECT * FROM tenant_provisioning_records WHERE tenant_id=:tenant"),
                {"tenant": tenant_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["state"] != "COMPLETE":
        raise ProvisioningAuthorizationError("Tenant provisioning is incomplete")
    receipt = (
        (
            await connection.execute(
                text("SELECT * FROM tenant_provisioning_outbox WHERE tenant_id=:tenant"),
                {"tenant": tenant_id},
            )
        )
        .mappings()
        .one_or_none()
    )
    if receipt is None:
        raise ProvisioningAuthorizationError("Final CAS receipt is missing")
    try:
        content = json.loads(receipt["receipt_json"])
        digest = hashlib.sha256(
            json.dumps(
                content, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
            ).encode("ascii")
        ).hexdigest()
        if (
            digest != receipt["receipt_digest"]
            or digest != row["completion_digest"]
            or content["receipt_id"] != receipt["receipt_id"]
            or content["tenant"] != tenant_id
            or content["generation"] != row["generation_id"]
            or content["pending"] != row["pending_receipt_digest"]
            or content["publication"] != row["publication_digest"]
            or content["to"] != "ACTIVE"
            or receipt["generation_id"] != row["generation_id"]
        ):
            raise ValueError("Final CAS receipt mismatch")
    except (ValueError, TypeError, KeyError) as exc:
        raise ProvisioningAuthorizationError("Final CAS receipt is unverified") from exc
    if not provider.verify_integrity():
        raise ProvisioningAuthorizationError("Tenant authority remains quarantined")
    ledger = PublicationAuthorizationLedger(provider)
    complete = ledger.completion(tenant_id)
    publication = ledger.publication(tenant_id)
    lifecycle = provider.get_state(tenant_id)
    if complete is None or publication is None or lifecycle is None:
        raise ProvisioningAuthorizationError("Cross-store completion evidence is missing")
    if (
        lifecycle.state.value != "ACTIVE"
        or lifecycle.generation_id != row["generation_id"]
        or complete.publication_digest != publication.digest()
        or publication.digest() != row["publication_digest"]
        or complete.completion_digest != row["completion_digest"]
        or lifecycle.security_epoch < row["security_epoch"]
        or lifecycle.revocation_floor < row["revocation_floor"]
        or current_epoch < max(lifecycle.security_epoch, lifecycle.revocation_floor)
    ):
        raise ProvisioningAuthorizationError("Tenant lifecycle or completion mismatch")
    fields = {
        "tenant_id": tenant_id,
        "generation_id": row["generation_id"],
        "deployment_id": row["deployment_id"],
        "request_id": row["request_id"],
        "principal_id": row["principal_id"],
        "operation_digest": row["operation_digest"],
        "pending_receipt_digest": row["pending_receipt_digest"],
        "security_epoch": row["security_epoch"],
        "revocation_floor": row["revocation_floor"],
    }
    if any(
        getattr(complete, name) != value or getattr(publication, name) != value
        for name, value in fields.items()
    ):
        raise ProvisioningAuthorizationError("Exact tenant completion tuple differs")


async def assert_tenant_provisioning_complete(
    connection: AsyncConnection, tenant_id: str, current_epoch: int
) -> None:
    """Admission always requires verified global READY as well as tenant completion."""
    gate = get_restore_readiness_gate()
    await gate.assert_current_traffic_admitted()
    provider = gate.provider
    if (
        type(provider) is not SqliteDurableLifecycleStateProvider
        or provider.get_readiness_state() != RestoreReadinessState.READY
    ):
        raise ProvisioningAuthorizationError("Tenant authority remains quarantined")
    await verify_tenant_completion_evidence(connection, tenant_id, current_epoch, provider)
