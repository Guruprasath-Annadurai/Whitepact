# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Approved historical fixture evolution, never synthetic lifecycle authority."""

from functools import partial

from sqlalchemy import text

from responsibleai.data_governance.backup_defense import LifecycleState, compute_lifecycle_digest
from responsibleai.data_governance.tenant_admission import verify_tenant_completion_evidence
from responsibleai.db.revocation_epoch_repository import lock_epoch


async def protected_failure_matrix_setup(controller):
    service, _, owner, token, csrf = controller
    tenant = await service.create(
        session_token=token,
        csrf=csrf,
        request_id="historical-failure-matrix",
        name="Historical Failure Matrix",
        slug="historical-failure-matrix",
    )
    lifecycle = service.provider.get_state(tenant)
    publication = service.ledger.publication(tenant)
    completion = service.ledger.completion(tenant)
    assert lifecycle is not None and lifecycle.state == LifecycleState.ACTIVE
    assert publication is not None and completion is not None
    assert lifecycle.generation_id == publication.generation_id == completion.generation_id
    assert lifecycle.security_epoch == 1 and lifecycle.revocation_floor == 1
    async with service.engine.raw.begin() as connection:
        server_version = int(await connection.scalar(text("SHOW server_version_num")))
        assert 160000 <= server_version < 170000
        row = (
            await connection.execute(
                text(
                    "SELECT p.generation_id,p.state,o.owner_user_id FROM tenant_provisioning_records p "
                    "JOIN organizations o ON o.id=p.tenant_id WHERE tenant_id=:tenant FOR UPDATE"
                ),
                {"tenant": tenant},
            )
        ).one()
        assert tuple(row) == (lifecycle.generation_id, "COMPLETE", owner)
        epoch = await lock_epoch(connection, tenant)
        assert epoch == 1
        await verify_tenant_completion_evidence(connection, tenant, epoch, service.provider)
    assert service.provider.verify_integrity()
    # Bind the original test's normal digest calculations to this disposable
    # Store B's real integrity key. Its tampered-digest attack is unchanged.
    digest = partial(compute_lifecycle_digest, secret_key=service.provider._secret_key)
    return service.provider, tenant, lifecycle.generation_id, lifecycle.effective_at, digest
