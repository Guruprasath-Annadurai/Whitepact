# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WS-2 mandatory dependency fail-closed matrix (hosted + upstream MCP)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from responsibleai.governance import WhitePactRuntimeGateway
from responsibleai.governance.authority_resolver import AuthorityDenied, AuthorityResolver
from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
from responsibleai.mcp.upstream_dispatch import apply_upstream_governance
from responsibleai.rbac.models import OrgContext, Plan, Role

pytest_plugins = ("tests.test_mcp_governance_dispatch",)


@pytest.fixture
async def engine():
    from responsibleai.db.engine import create_engine

    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


def _hosted_services(engine, seed_runtime_authority, **overrides) -> GovernanceServices:
    from responsibleai.db import OrgRepository
    from responsibleai.db.consent_proof_repository import ConsentProofRepository
    from responsibleai.db.delegation_repository import DelegationRepository
    from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
    from responsibleai.db.root_authority_repository import RootAuthorityRepository

    base = {
        "gateway": WhitePactRuntimeGateway(),
        "evidence_repo": MagicMock(record=AsyncMock()),
        "approval_repo": MagicMock(),
        "policy_repo": MagicMock(get_policy=AsyncMock(return_value=MagicMock(version=1))),
        "trust_client": MagicMock(),
        "org_repo": OrgRepository(engine),
        "epoch_repo": RevocationEpochRepository(engine),
        "nonce_repo": MagicMock(),
        "authority_resolver": AuthorityResolver(
            RootAuthorityRepository(engine),
            ConsentProofRepository(engine),
            DelegationRepository(engine),
        ),
    }
    base.update(overrides)
    return GovernanceServices(**base)


async def _seed_org(engine, seed_runtime_authority) -> tuple[str, str]:
    from responsibleai.db import OrgRepository

    repo = OrgRepository(engine)
    org = await repo.create_org("FC", f"fc-{uuid.uuid4().hex[:8]}")
    principal = "principal-fc"
    await seed_runtime_authority(
        engine,
        organization_id=org.id,
        principal_id=principal,
        action_types=("rai_health",),
        targets=("rai_health",),
    )
    return org.id, principal


class TestHostedDependencyFailClosed:
    @pytest.mark.parametrize(
        "override_key,override_value",
        [
            ("authority_resolver", None),
            ("approval_repo", MagicMock(create=AsyncMock(side_effect=RuntimeError("db")))),
            ("epoch_repo", None),
            ("nonce_repo", MagicMock()),
        ],
    )
    async def test_apply_governance_dependency_failure(
        self,
        engine,
        seed_runtime_authority,
        monkeypatch,
        override_key,
        override_value,
    ) -> None:
        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        services = _hosted_services(engine, seed_runtime_authority)
        if override_key == "epoch_repo" and override_value is None:
            services = _hosted_services(
                engine,
                seed_runtime_authority,
                nonce_repo=MagicMock(),
                epoch_repo=None,
            )
            with pytest.raises(ValueError, match="both nonce and epoch"):
                await apply_governance(
                    "rai_health",
                    {},
                    OrgContext(
                        key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE
                    ),
                    services,
                    purpose="ws2-fc",
                )
            dispatch.assert_not_awaited()
            return
        setattr(services, override_key, override_value)
        if override_key == "authority_resolver" and override_value is None:
            outcome = await apply_governance(
                "rai_health",
                {},
                OrgContext(
                    key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE
                ),
                services,
                purpose="ws2-fc",
            )
            assert outcome.proceed is False
            assert outcome.blocked_response["error"] == "governance_authority_unavailable"
        else:
            outcome = await apply_governance(
                "rai_health",
                {},
                OrgContext(
                    key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE
                ),
                services,
                purpose="ws2-fc",
            )
            assert outcome.proceed is False
        dispatch.assert_not_awaited()

    async def test_policy_repo_failure_fail_closed(
        self, engine, seed_runtime_authority, monkeypatch
    ) -> None:
        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        policy = MagicMock()
        policy.get_policy = AsyncMock(side_effect=RuntimeError("db"))
        services = _hosted_services(engine, seed_runtime_authority, policy_repo=policy)
        try:
            outcome = await apply_governance(
                "rai_health",
                {},
                OrgContext(
                    key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE
                ),
                services,
                purpose="ws2-fc",
            )
        except RuntimeError:
            pass
        else:
            assert outcome.proceed is False
        dispatch.assert_not_awaited()

    async def test_resolver_authority_denied_fail_closed(
        self, engine, seed_runtime_authority, monkeypatch
    ) -> None:
        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        resolver = MagicMock(spec=AuthorityResolver)
        resolver.resolve = AsyncMock(side_effect=AuthorityDenied("denied"))
        services = _hosted_services(engine, seed_runtime_authority, authority_resolver=resolver)
        outcome = await apply_governance(
            "rai_health",
            {},
            OrgContext(key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE),
            services,
            purpose="ws2-fc",
        )
        assert outcome.proceed is False
        assert outcome.blocked_response["error"] in {
            "governance_denied",
            "governance_evidence_unavailable",
        }
        dispatch.assert_not_awaited()

    async def test_evidence_repo_failure_fail_closed(
        self, engine, seed_runtime_authority, monkeypatch
    ) -> None:
        dispatch = AsyncMock()
        monkeypatch.setattr("responsibleai.mcp.tools.dispatch_tool", dispatch)
        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        evidence = MagicMock()
        evidence.record = AsyncMock(side_effect=RuntimeError("db down"))
        services = _hosted_services(engine, seed_runtime_authority, evidence_repo=evidence)
        outcome = await apply_governance(
            "rai_health",
            {},
            OrgContext(key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE),
            services,
            purpose="ws2-fc",
        )
        assert outcome.proceed is False
        assert outcome.blocked_response["error"] == "governance_evidence_unavailable"
        dispatch.assert_not_awaited()


class TestUpstreamDependencyFailClosed:
    async def test_upstream_registry_missing_never_executes(
        self, engine, seed_runtime_authority, monkeypatch
    ) -> None:
        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        executor = MagicMock()
        executor.execute = AsyncMock()
        registry = MagicMock()
        registry.get = AsyncMock(return_value=None)
        from responsibleai.db import ApprovalRepository, EvidenceRepository, PolicyRepository
        from responsibleai.db.consent_proof_repository import ConsentProofRepository
        from responsibleai.db.delegation_repository import DelegationRepository
        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
        from responsibleai.db.root_authority_repository import RootAuthorityRepository
        from responsibleai.db.tool_trust_repository import ToolTrustRepository

        outcome = await apply_upstream_governance(
            "missing",
            "tool",
            {},
            OrgContext(key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE),
            purpose="ws2-fc",
            authority_resolver=AuthorityResolver(
                RootAuthorityRepository(engine),
                ConsentProofRepository(engine),
                DelegationRepository(engine),
            ),
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=EvidenceRepository(engine),
            policy_repo=PolicyRepository(engine),
            approval_repo=ApprovalRepository(engine),
            upstream_registry=registry,
            executor=executor,
            tool_trust_repo=ToolTrustRepository(engine),
            epoch_repo=RevocationEpochRepository(engine),
        )
        assert outcome.proceed is False
        assert outcome.blocked_response["error"] == "governance_denied"
        executor.execute.assert_not_awaited()

    async def test_upstream_resolver_denied_never_executes(
        self, engine, seed_runtime_authority, monkeypatch
    ) -> None:
        from types import SimpleNamespace

        org_id, principal = await _seed_org(engine, seed_runtime_authority)
        server = SimpleNamespace(
            server_id="s1",
            org_id=org_id,
            enabled=True,
            url="https://example.com/mcp",
            auth_token=None,
        )
        registry = MagicMock()
        registry.get = AsyncMock(return_value=server)
        executor = MagicMock()
        executor.execute = AsyncMock()
        resolver = MagicMock(spec=AuthorityResolver)
        resolver.resolve = AsyncMock(side_effect=AuthorityDenied("no"))
        from responsibleai.db import ApprovalRepository, EvidenceRepository, PolicyRepository
        from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
        from responsibleai.db.tool_trust_repository import ToolTrustRepository

        outcome = await apply_upstream_governance(
            "s1",
            "tool",
            {},
            OrgContext(key_id=principal, role=Role.ANALYST, org_id=org_id, plan=Plan.ENTERPRISE),
            purpose="ws2-fc",
            authority_resolver=resolver,
            gateway=WhitePactRuntimeGateway(),
            evidence_repo=EvidenceRepository(engine),
            policy_repo=PolicyRepository(engine),
            approval_repo=ApprovalRepository(engine),
            upstream_registry=registry,
            executor=executor,
            tool_trust_repo=ToolTrustRepository(engine),
            epoch_repo=RevocationEpochRepository(engine),
        )
        assert outcome.proceed is False
        executor.execute.assert_not_awaited()
