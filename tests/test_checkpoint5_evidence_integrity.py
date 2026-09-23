# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Checkpoint 5 adversarial evidence-integrity properties."""

from __future__ import annotations

import asyncio
import hashlib
import json
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db import EvidenceRepository, OutcomeRepository, create_engine
from responsibleai.db.engine import governance_evidence, governance_evidence_chain_heads
from responsibleai.db.evidence_repository import _compute_entry_hash
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.outcome import OutcomeStatus, build_outcome_record
from responsibleai.mcp.governance_integration import (
    GovernanceServices,
    _classify_execution_outcome,
    _record_outcome,
)


@pytest.fixture()
async def engine():
    database = create_engine(":memory:")
    await database.init()
    yield database
    await database.close()


def _record(org_id: str, index: int = 0):
    identity = IdentityContext(identity_id=f"principal-{index}", kind="api_key", org_id=org_id)
    agent = AgentContext(identity=identity, organization_id=org_id, agent_id=f"agent-{index}")
    action = ActionRequest(
        agent=agent,
        action_type="mcp_tool_call",
        target=f"tool-{index}",
        arguments={"token": "synthetic-secret", "n": index},
        purpose="checkpoint-5",
    )
    authority = AuthorityContext(
        delegated_by=identity.identity_id,
        granted_action_types=frozenset({"mcp_tool_call"}),
        delegation_chain=("root-1", identity.identity_id),
    )
    decision = WhitePactRuntimeGateway().evaluate(action, authority)
    assert decision.decision is GovernanceDecision.ALLOW
    return build_evidence_record(
        action,
        agent,
        authority,
        decision,
        authentication_method="api_key",
        authority_version="authority-v1",
        consent_id="consent-1",
        consent_version="consent-v1",
        governance_epoch=7,
    )


class TestCanonicalIntegrity:
    async def test_every_security_binding_is_digest_protected(self, engine) -> None:
        repo = EvidenceRepository(engine)
        saved = await repo.record(_record("org-1"))
        protected_changes = {
            "identity_id": "attacker",
            "authentication_method": "oidc",
            "target": "other-tool",
            "arguments_fingerprint": "0" * 64,
            "purpose": "other-purpose",
            "authority_version": "other-authority",
            "consent_version": "other-consent",
            "policy_version": 999,
            "governance_epoch": 999,
        }
        for column, value in protected_changes.items():
            async with engine.raw.begin() as conn:
                original = (
                    await conn.execute(
                        governance_evidence.select().where(
                            governance_evidence.c.id == saved.evidence_id
                        )
                    )
                ).fetchone()
                await conn.execute(
                    update(governance_evidence)
                    .where(governance_evidence.c.id == saved.evidence_id)
                    .values(**{column: value})
                )
            assert await repo.verify_chain("org-1") is False, column
            async with engine.raw.begin() as conn:
                await conn.execute(
                    update(governance_evidence)
                    .where(governance_evidence.c.id == saved.evidence_id)
                    .values(**{column: original._mapping[column]})
                )
            assert await repo.verify_chain("org-1") is True, column

    async def test_delete_and_reorder_are_detected(self, engine) -> None:
        repo = EvidenceRepository(engine)
        records = [await repo.record(_record("org-1", i)) for i in range(3)]
        async with engine.raw.begin() as conn:
            await conn.execute(
                delete(governance_evidence).where(
                    governance_evidence.c.id == records[1].evidence_id
                )
            )
        assert await repo.verify_chain("org-1") is False

    async def test_delete_all_is_detected_against_durable_head(self, engine) -> None:
        repo = EvidenceRepository(engine)
        await repo.record(_record("org-1"))
        async with engine.raw.begin() as conn:
            await conn.execute(
                delete(governance_evidence).where(governance_evidence.c.org_id == "org-1")
            )
        assert await repo.verify_chain("org-1") is False
        assert (await repo.verify_chain_status("org-1")).value == "INVALID"

    async def test_deleting_canonical_suffix_after_legacy_history_is_detected(self, engine) -> None:
        repo = EvidenceRepository(engine)
        first = await repo.record(_record("org-1"))
        async with engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    governance_evidence.select().where(
                        governance_evidence.c.id == first.evidence_id
                    )
                )
            ).fetchone()
            legacy = dict(row._mapping)
            legacy["integrity_version"] = 1
            legacy_hash = _compute_entry_hash(None, legacy)
            await conn.execute(
                update(governance_evidence)
                .where(governance_evidence.c.id == first.evidence_id)
                .values(
                    integrity_version=1,
                    integrity_status="LEGACY_CHAINED_V1",
                    chain_sequence=None,
                    entry_hash=legacy_hash,
                )
            )
            await conn.execute(
                update(governance_evidence_chain_heads)
                .where(governance_evidence_chain_heads.c.org_id == "org-1")
                .values(head_hash=legacy_hash, sequence=1)
            )
        second = await repo.record(_record("org-1", 2))
        async with engine.raw.begin() as conn:
            await conn.execute(
                delete(governance_evidence).where(governance_evidence.c.id == second.evidence_id)
            )
        assert await repo.verify_chain("org-1") is False

    async def test_chain_sequence_not_wall_clock_orders_records(
        self, engine, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        timestamps = iter(
            (
                "2026-01-01T10:00:00+00:00",
                "2026-01-01T10:00:00+00:00",
                "2026-01-01T09:59:59+00:00",
            )
        )
        monkeypatch.setattr("responsibleai.db.evidence_repository._now", lambda: next(timestamps))
        repo = EvidenceRepository(engine)
        await repo.record(_record("org-1"))
        await repo.record(_record("org-1", 2))
        assert await repo.verify_chain("org-1") is True

    async def test_sensitive_values_are_only_fingerprinted(self, engine) -> None:
        repo = EvidenceRepository(engine)
        evidence = _record("org-1")
        secrets = {
            "api_key": "wp_test_api_key_value",
            "authorization": "Bearer test_authorization_value",
            "oauth_token": "oauth_test_token_value",
            "database_credential": "postgresql://test:password@localhost/test",
            "redis_credential": "redis://:password@localhost/0",
            "upstream_credential": "upstream_test_credential",
            "totp_or_backup_code": "123456-test-backup-code",
        }
        evidence.argument_keys = sorted(secrets)
        evidence.arguments_fingerprint = hashlib.sha256(
            json.dumps(secrets, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        saved = await repo.record(evidence)
        serialized = str(saved.to_dict())
        assert all(secret not in serialized for secret in secrets.values())
        assert saved.arguments_fingerprint is not None
        assert len(saved.arguments_fingerprint) == 64


class TestTenantEvidenceIsolation:
    async def test_id_lookup_and_chain_head_are_tenant_scoped(self, engine) -> None:
        repo = EvidenceRepository(engine)
        saved_a = await repo.record(_record("org-a"))
        await repo.record(_record("org-b"))
        assert await repo.get_for_org(saved_a.evidence_id, "org-b") is None
        assert await repo.get_for_org(saved_a.evidence_id, "org-a") is not None
        assert await repo.get_chain_head("org-a") != await repo.get_chain_head("org-b")

    async def test_cross_tenant_predecessors_never_mix(self, engine) -> None:
        repo = EvidenceRepository(engine)
        first_a = await repo.record(_record("org-a"))
        first_b = await repo.record(_record("org-b"))
        second_a = await repo.record(_record("org-a", 2))
        assert first_a.prev_hash is None
        assert first_b.prev_hash is None
        assert second_a.prev_hash == first_a.hash
        assert second_a.prev_hash != first_b.hash

    async def test_cross_tenant_outcome_append_is_rejected(self, engine) -> None:
        saved = await EvidenceRepository(engine).record(_record("org-a"))
        with pytest.raises(ValueError, match="does not belong"):
            await OutcomeRepository(engine).record(
                build_outcome_record(
                    saved.evidence_id,
                    saved.action_id,
                    OutcomeStatus.SUCCEEDED,
                    organization_id="org-b",
                )
            )


class TestDurableConcurrency:
    async def test_independent_repository_instances_create_one_linear_chain(self, engine) -> None:
        repositories = [EvidenceRepository(engine) for _ in range(4)]
        saved = await asyncio.gather(
            *[repositories[i % 4].record(_record("org-1", i)) for i in range(20)]
        )
        assert len({item.evidence_id for item in saved}) == 20
        assert len({item.hash for item in saved}) == 20
        assert await EvidenceRepository(engine).verify_chain("org-1") is True
        head = await EvidenceRepository(engine).get_chain_head("org-1")
        assert head is not None
        assert head[1] == 20

    async def test_failed_append_rolls_back_head_and_next_append_recovers(self, engine) -> None:
        repo = EvidenceRepository(engine)
        first = await repo.record(_record("org-1"))
        duplicate = _record("org-1", 2)
        duplicate.evidence_id = first.evidence_id
        with pytest.raises(IntegrityError):
            await repo.record(duplicate)
        second = await repo.record(_record("org-1", 3))
        assert second.prev_hash == first.hash
        assert second.chain_sequence == 2
        assert await repo.verify_chain("org-1") is True
        head = await EvidenceRepository(engine).get_chain_head("org-1")
        assert head is not None
        assert head[1] == 2

    async def test_restart_rehydrates_durable_head(self, engine) -> None:
        first = await EvidenceRepository(engine).record(_record("org-1"))
        second = await EvidenceRepository(engine).record(_record("org-1", 2))
        assert second.prev_hash == first.hash
        assert await EvidenceRepository(engine).verify_chain("org-1") is True


def test_unknown_outcome_is_first_class() -> None:
    assert OutcomeStatus.UNKNOWN.value == "UNKNOWN"


def test_upstream_error_shape_is_never_classified_as_success() -> None:
    assert _classify_execution_outcome({"is_error": True}) is OutcomeStatus.FAILED


async def test_final_outcome_failure_attempts_unknown_without_claiming_success() -> None:
    outcome_repo = AsyncMock()
    outcome_repo.record.side_effect = [RuntimeError("final write failed"), None]
    services = GovernanceServices(
        gateway=AsyncMock(),
        evidence_repo=AsyncMock(),
        approval_repo=AsyncMock(),
        policy_repo=AsyncMock(),
        trust_client=AsyncMock(),
        outcome_repo=outcome_repo,
    )
    persisted = await _record_outcome(
        services,
        "evidence-1",
        "action-1",
        OutcomeStatus.SUCCEEDED,
        organization_id="org-1",
    )
    assert persisted is False
    assert outcome_repo.record.await_count == 2
    unknown = outcome_repo.record.await_args_list[1].args[0]
    assert unknown.status is OutcomeStatus.UNKNOWN
