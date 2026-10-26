# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable authenticated provisioning for recovery freshness qualification."""

import uuid

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import text

from responsibleai.data_governance.provisioning_manifest import ProvisionerTrust
from responsibleai.data_governance.tenant_controller import (
    ProtectedTenantController,
    postgres_identity,
    store_b_identity,
)
from responsibleai.data_governance.tenant_provisioning import (
    PendingTenantReservations,
    PublicationAuthorizationLedger,
)
from responsibleai.db.web_identity_repository import WebIdentityRepository


async def provision_freshness_tenant(engine, provider):
    key = Ed25519PrivateKey.generate()
    async with engine.raw.connect() as connection:
        pg = await postgres_identity(connection)
    trust = ProvisionerTrust(
        "disposable-freshness",
        key.public_key().public_bytes_raw(),
        "freshness-isolated",
        "staging",
        pg,
        store_b_identity(provider),
    )
    PendingTenantReservations(provider).initialize()
    PublicationAuthorizationLedger(provider).initialize(trust)
    identity = WebIdentityRepository(engine)
    user, verification = await identity.register(
        "Freshness Owner", f"{uuid.uuid4().hex}@example.test", "Independent-Test-Only-42!"
    )
    assert await identity.verify_email(verification)
    token, csrf = await identity.create_session(user)
    service = ProtectedTenantController(engine, provider, trust, key)
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="freshness-established",
        name="Freshness Tenant",
        slug="freshness-tenant",
    )
    lifecycle = provider.get_state(tenant)
    completion = service.ledger.completion(tenant)
    assert completion.generation_id == lifecycle.generation_id
    assert lifecycle.state.value == "ACTIVE"
    async with engine.raw.connect() as connection:
        row = (
            (
                await connection.execute(
                    text(
                        "SELECT generation_id,state,completion_digest FROM tenant_provisioning_records "
                        "WHERE tenant_id=:tenant"
                    ),
                    {"tenant": tenant},
                )
            )
            .mappings()
            .one()
        )
        assert row["state"] == "COMPLETE"
        assert row["generation_id"] == lifecycle.generation_id
        assert row["completion_digest"] == completion.completion_digest
    return service, tenant, token, csrf
