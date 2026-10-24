# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""New-tenant insertion is distinct from changing established lifecycle evidence."""

import hashlib
from dataclasses import asdict
from pathlib import Path

import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import RestoreReadinessState
from responsibleai.data_governance.operator_recovery_control import prepare_offline_recovery
from tests.stage3_freshness_setup import provision_freshness_tenant
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign


def test_original_freshness_source_remains_immutable():
    source = (
        Path(__file__).parent
        / "historical_evidence"
        / "operator_recovery_postgres_before_stage3_freshness.py.txt"
    ).read_bytes()
    digest = hashlib.sha1(
        b"blob " + str(len(source)).encode() + b"\0" + source, usedforsecurity=False
    ).hexdigest()
    assert digest == "de912fe82925310dfb9f791ac47abc7a6e3613ee"


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["freshness"], indirect=True)
async def test_new_tenant_insertion_after_approval_is_denied_by_quarantine(real_recovery):
    engine, provider, gate, profile_path, private = real_recovery
    service, tenant, token, csrf = await provision_freshness_tenant(engine, provider)
    baseline = provider.get_state(tenant)
    provider.set_readiness_state(RestoreReadinessState.FAILED)
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    original = asdict(manifest)
    signatures = sign(manifest, private)
    signature_copy = dict(signatures)
    from responsibleai.data_governance.provisioning_manifest import ProvisioningAuthorizationError

    with pytest.raises(ProvisioningAuthorizationError, match="quarantined"):
        await service.create(
            session_token=token,
            csrf=csrf,
            request_id="post-approval-new-tenant",
            name="Must Not Appear",
            slug="must-not-appear",
        )
    assert asdict(manifest) == original
    assert signatures == signature_copy
    assert provider.list_all() == [baseline]
    assert gate.state == RestoreReadinessState.FAILED
    async with engine.raw.connect() as connection:
        assert await connection.scalar(text("SELECT count(*) FROM organizations")) == 1
        assert (
            await connection.scalar(text("SELECT count(*) FROM tenant_provisioning_records")) == 1
        )
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM governance_execution_authorizations")
            )
            == 0
        )
        assert (
            await connection.scalar(text("SELECT count(*) FROM governance_root_authority_records"))
            == 0
        )
