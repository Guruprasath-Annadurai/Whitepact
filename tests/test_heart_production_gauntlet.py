"""Heart Production Closure -- the end-to-end production authority
gauntlet the directive requires: one test proving the full chain from
identity through persisted root authority, persisted consent,
Heart legitimacy resolution, an enforcement boundary that actually
gates execution, evidence, and external anchor publication -- then
revocation of that same consent, re-running the identical action, and
proving it is now DENIED. Followed by every named attack variant the
directive lists, each proving DENY (or, honestly, named as not yet
enforced where this codebase's current architecture genuinely does not
enforce it -- never faked).

**Every building block used here is real and already independently
tested elsewhere** (`resolve_authority_grant()` --
`test_authority_resolver.py`; `RevocationEpochRepository` --
`test_revocation_epoch_repository.py`; the signed-anchor pipeline --
`test_audit_anchor.py`); this file's own job is proving they compose
correctly end to end, not re-testing each in isolation.

**The enforcement boundary** (`_enforcement_boundary()` below) is a
deliberately small, honest stand-in for "the one place a real governed
action actually executes." It encodes the exact invariant this whole
initiative is about: `grant.is_legitimate` is consulted, and nothing
executes unless it's `True` -- gating on any other field, or skipping
the check, is exactly the bypass class this initiative closes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.engine import create_engine
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance.audit_anchor import (
    AnchorVerificationStatus,
    LocalFileAnchorProvider,
    build_and_sign_anchor,
    publish_anchor,
    verify_anchor_from_provider,
)
from responsibleai.governance.authority_grant import AuthorityGrant
from responsibleai.governance.authority_resolver import resolve_authority_grant
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider
from responsibleai.governance.crypto.types import KeyPurpose
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.evidence_bundle import build_evidence_bundle
from responsibleai.governance.heart_production_gate import (
    HeartEnforcementError,
    verify_heart_production_enforcement,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    IdentityContext,
)
from responsibleai.governance.root_authority import RootType, build_root_authority_record


@dataclass(frozen=True)
class _ExecutionResult:
    outcome: str  # "EXECUTED" | "DENIED"
    detail: str


def _enforcement_boundary(
    grant: AuthorityGrant, *, requested_action_type: str, requested_target: str
) -> _ExecutionResult:
    """The one gate every governed action must pass. Denies on any of:
    illegitimate grant, or the action actually being attempted not
    matching what the grant was resolved for (action_mutation
    protection -- a grant legitimately issued for one action must
    never be reused to authorize a *different* one)."""
    if not grant.is_legitimate:
        return _ExecutionResult("DENIED", "grant.is_legitimate is False")
    if (
        grant.requested_action_type != requested_action_type
        or grant.requested_target != requested_target
    ):
        return _ExecutionResult(
            "DENIED",
            f"action mutation: grant was for "
            f"{grant.requested_action_type}/{grant.requested_target}, "
            f"execution attempted {requested_action_type}/{requested_target}",
        )
    return _ExecutionResult("EXECUTED", "legitimate grant, action matches")


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def root_repo(db):
    return RootAuthorityRepository(db)


@pytest.fixture()
async def consent_repo(db):
    return ConsentProofRepository(db)


def _identity(kind: str = "oidc", identity_id: str = "oidc:sub123") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind=kind, org_id="org-1")


def _agent(identity: IdentityContext, agent_id: str = "agent-1") -> AgentContext:
    return AgentContext(identity=identity, organization_id="org-1", agent_id=agent_id)


def _action(agent: AgentContext, action_type: str = "mcp_tool_call", target: str = "rai_scan"):
    return ActionRequest(agent=agent, action_type=action_type, target=target)


def _authority_context() -> AuthorityContext:
    return AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"mcp_tool_call"}))


def _record(action_id: str, decision: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=f"evidence-{action_id}",
        organization_id="org-1",
        action_id=action_id,
        agent_id="agent-1",
        identity_id="oidc:sub123",
        action_type="mcp_tool_call",
        target="rai_scan",
        argument_keys=[],
        authority_delegated_by="org-1",
        decision=decision,
        reason_codes=[],
        evaluated_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC).isoformat(),
        prev_hash=None,
        hash=f"hash-{action_id}",
    )


class TestFullProductionAuthorityGauntlet:
    async def test_full_chain_then_revoke_then_deny(self, root_repo, consent_repo, tmp_path):
        # 1. Human/org identity -> persisted root authority.
        admin_root = await root_repo.create(
            build_root_authority_record(
                "admin-1", RootType.ORGANIZATION, "idp", "oidc", organization_id="org-1"
            )
        )

        # 2. Persisted valid consent -- delegated authority from the
        # admin's root to agent-1, scoped to exactly the action it will
        # request.
        proof = build_consent_proof(
            "admin-1",
            admin_root.root_id,
            "agent-1",
            "run RAI scans on behalf of the org",
            "vendor risk review",
            ConsentMethod.API_AUTHENTICATED_REQUEST,
            allowed_action_types=("mcp_tool_call",),
            allowed_targets=("rai_scan",),
        )
        await consent_repo.create(proof)

        # 3. Agent requests a governed action.
        identity = _identity()
        agent = _agent(identity)
        action = _action(agent)

        # 4. Heart legitimacy resolution (Gap A) -- consent-backed,
        # against an acting identity whose OWN root is not terminal
        # (proving legitimacy came from the consent's root, not a
        # rubber stamp).
        grant = await resolve_authority_grant(
            identity,
            agent,
            action,
            _authority_context(),
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant.is_legitimate is True
        assert grant.root_reference == admin_root.root_id
        # Enterprise Readiness Phase 3: resolve_authority_grant() must
        # stamp which consent proof actually backed the grant, not just
        # that some consent existed -- feeds ExecutionAuthorization's
        # own consent_reference binding.
        assert grant.consent_reference == proof.consent_id

        # 5. Enforcement boundary -- policy/risk decision stands in for
        # a real Policy/RiskTier evaluation (out of this gauntlet's
        # scope; ExecutionAuthorization is exactly `grant.is_legitimate`
        # here) -- gates the simulated external action.
        result = _enforcement_boundary(
            grant, requested_action_type="mcp_tool_call", requested_target="rai_scan"
        )
        assert result.outcome == "EXECUTED"

        # 6. Audit/evidence + external anchor provider (Gap D).
        record = _record("action-1", decision="ALLOW")
        bundle = build_evidence_bundle([record], org_id="org-1", bundle_id="bundle-1")
        key_provider = LocalEnvelopeKeyProvider(root_key=b"\x00" * 32, environment="test")
        key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        anchor_record = build_and_sign_anchor(bundle, key_id, dek, anchor_id="anchor-1")
        provider = LocalFileAnchorProvider(tmp_path / "anchors")
        published = await publish_anchor(anchor_record, provider)
        assert published.destination_ref is not None

        verify_result = await verify_anchor_from_provider(
            current_bundle_digest=bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert verify_result.status == AnchorVerificationStatus.VALID

        # 7. Revoke the consent that made this legitimate.
        await consent_repo.revoke(proof.consent_id, revoked_by="admin-1", reason="offboarded")

        # 8. Repeat the EXACT same action -- must now be DENIED.
        grant_after_revoke = await resolve_authority_grant(
            identity,
            agent,
            action,
            _authority_context(),
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )
        assert grant_after_revoke.is_legitimate is False
        result_after_revoke = _enforcement_boundary(
            grant_after_revoke, requested_action_type="mcp_tool_call", requested_target="rai_scan"
        )
        assert result_after_revoke.outcome == "DENIED"


class TestAttackVariants:
    """The directive's ~14 named attack variants. Each must DENY.
    Where this codebase's current, honestly-scoped architecture does
    not yet enforce a variant (purpose matching, execution replay --
    see each test's own docstring), that is stated explicitly as a
    known limitation rather than faked as closed."""

    async def _legitimate_setup(self, root_repo, consent_repo, **consent_kwargs):
        admin_root = await root_repo.create(
            build_root_authority_record(
                "admin-1", RootType.ORGANIZATION, "idp", "oidc", organization_id="org-1"
            )
        )
        defaults = dict(
            subject_id="admin-1",
            consenting_root_id=admin_root.root_id,
            grantee_id="agent-1",
            scope_description="scope",
            purpose="purpose",
            consent_method=ConsentMethod.API_AUTHENTICATED_REQUEST,
            allowed_action_types=("mcp_tool_call",),
        )
        defaults.update(consent_kwargs)
        proof = build_consent_proof(
            defaults.pop("subject_id"),
            defaults.pop("consenting_root_id"),
            defaults.pop("grantee_id"),
            defaults.pop("scope_description"),
            defaults.pop("purpose"),
            defaults.pop("consent_method"),
            **defaults,
        )
        await consent_repo.create(proof)
        return admin_root, proof

    async def _grant(self, root_repo, consent_repo):
        identity = _identity()
        agent = _agent(identity)
        action = _action(agent)
        return await resolve_authority_grant(
            identity,
            agent,
            action,
            _authority_context(),
            root_repo,
            issuer="idp",
            verification_method="oidc",
            consent_repo=consent_repo,
        )

    async def test_01_no_consent(self, root_repo, consent_repo):
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_02_wrong_tenant(self, root_repo, consent_repo):
        other_org_root = await root_repo.create(
            build_root_authority_record(
                "admin-2", RootType.ORGANIZATION, "idp", "oidc", organization_id="org-2"
            )
        )
        proof = build_consent_proof(
            "admin-2",
            other_org_root.root_id,
            "agent-1",
            "scope",
            "purpose",
            ConsentMethod.API_AUTHENTICATED_REQUEST,
            allowed_action_types=("mcp_tool_call",),
        )
        await consent_repo.create(proof)
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_03_wrong_principal(self, root_repo, consent_repo):
        await self._legitimate_setup(root_repo, consent_repo, grantee_id="someone-else")
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_04_wrong_purpose_KNOWN_LIMITATION(self, root_repo, consent_repo):
        """`purpose`/`scope_description` remain free text
        (consent_proof.py's own module docstring) -- no ActionRequest
        field represents "the purpose this specific action is being
        requested for" to compare against, so purpose compatibility is
        NOT structurally enforced by this codebase today. Named
        honestly rather than faked: this variant currently does NOT
        deny on a purpose mismatch alone when action/target scope
        otherwise matches. Real purpose enforcement would require a
        requested-purpose input this phase does not invent."""
        await self._legitimate_setup(root_repo, consent_repo, purpose="totally different purpose")
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is True  # documents the known gap, does not hide it

    async def test_05_expired_consent(self, root_repo, consent_repo):
        await self._legitimate_setup(
            root_repo, consent_repo, expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_06_revoked_consent(self, root_repo, consent_repo):
        _root, proof = await self._legitimate_setup(root_repo, consent_repo)
        await consent_repo.revoke(proof.consent_id, revoked_by="admin-1", reason="offboarded")
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_07_revoked_parent_authority(self, root_repo, consent_repo):
        root, _proof = await self._legitimate_setup(root_repo, consent_repo)
        await root_repo.revoke(root.root_id, revoked_by="admin-1", reason="offboarded")
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_08_scope_escalation(self, root_repo, consent_repo):
        await self._legitimate_setup(
            root_repo, consent_repo, allowed_action_types=("payment.execute",)
        )
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_09_forged_proof(self, root_repo, consent_repo):
        import dataclasses

        admin_root = await root_repo.create(
            build_root_authority_record(
                "admin-1", RootType.ORGANIZATION, "idp", "oidc", organization_id="org-1"
            )
        )
        proof = build_consent_proof(
            "admin-1",
            admin_root.root_id,
            "agent-1",
            "scope",
            "purpose",
            ConsentMethod.API_AUTHENTICATED_REQUEST,
            allowed_action_types=("mcp_tool_call",),
        )
        tampered = dataclasses.replace(proof, scope_description="forged scope")
        await consent_repo.create(tampered)
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is False

    async def test_10_stale_revocation_cache(self, root_repo, consent_repo):
        """No cache exists on this path at all (Gap B's own audit
        finding) -- so "stale cache" is structurally impossible today;
        this proves that directly: revoke, then immediately re-check,
        must observe the revocation with zero propagation delay."""
        _root, proof = await self._legitimate_setup(root_repo, consent_repo)
        grant_before = await self._grant(root_repo, consent_repo)
        assert grant_before.is_legitimate is True
        await consent_repo.revoke(proof.consent_id, revoked_by="admin-1", reason="offboarded")
        grant_after = await self._grant(root_repo, consent_repo)
        assert grant_after.is_legitimate is False

    async def test_11_second_process_after_revoke(self, db):
        """A second repository/'process' instance against the same
        store must see the revocation too -- see
        test_revocation_propagation.py for the dedicated multi-instance
        version of this; reproduced narrowly here as part of the full
        attack-variant enumeration."""
        root_repo_a = RootAuthorityRepository(db)
        consent_repo_a = ConsentProofRepository(db)
        root_repo_b = RootAuthorityRepository(db)
        consent_repo_b = ConsentProofRepository(db)

        admin_root = await root_repo_a.create(
            build_root_authority_record(
                "admin-1", RootType.ORGANIZATION, "idp", "oidc", organization_id="org-1"
            )
        )
        proof = build_consent_proof(
            "admin-1",
            admin_root.root_id,
            "agent-1",
            "scope",
            "purpose",
            ConsentMethod.API_AUTHENTICATED_REQUEST,
            allowed_action_types=("mcp_tool_call",),
        )
        await consent_repo_a.create(proof)
        grant_b_before = await self._grant(root_repo_b, consent_repo_b)
        assert grant_b_before.is_legitimate is True

        await consent_repo_a.revoke(proof.consent_id, revoked_by="admin-1", reason="offboarded")
        grant_b_after = await self._grant(root_repo_b, consent_repo_b)
        assert grant_b_after.is_legitimate is False

    async def test_12_action_mutation(self, root_repo, consent_repo):
        """A grant legitimately resolved for one action must not
        authorize a DIFFERENT action being executed -- enforced by
        `_enforcement_boundary()`, not by resolve_authority_grant()
        itself (which correctly reports the grant it resolved as
        legitimate for the action it was ASKED about)."""
        await self._legitimate_setup(root_repo, consent_repo)
        grant = await self._grant(root_repo, consent_repo)
        assert grant.is_legitimate is True  # legitimate for mcp_tool_call/rai_scan

        result = _enforcement_boundary(
            grant, requested_action_type="payment.execute", requested_target="rai_scan"
        )
        assert result.outcome == "DENIED"

    async def test_13_execution_replay_KNOWN_LIMITATION(self, root_repo, consent_repo):
        """No nonce/single-use primitive exists anywhere in this
        codebase's authority model -- a legitimate grant has no notion
        of "already consumed." Reusing the same grant object for a
        second identical execution is therefore NOT denied today.
        Named honestly as a real, unclosed gap rather than faked: real
        replay protection would need an execution-id/idempotency-key
        primitive this phase does not invent."""
        await self._legitimate_setup(root_repo, consent_repo)
        grant = await self._grant(root_repo, consent_repo)
        first = _enforcement_boundary(
            grant, requested_action_type="mcp_tool_call", requested_target="rai_scan"
        )
        second = _enforcement_boundary(
            grant, requested_action_type="mcp_tool_call", requested_target="rai_scan"
        )
        assert first.outcome == "EXECUTED"
        assert second.outcome == "EXECUTED"  # documents the known gap, does not hide it

    async def test_14_heart_unavailable_fails_startup_not_silent_bypass(self):
        """In HEART_ENFORCED-equivalent mode (enterprise_mode=true),
        Heart being unavailable must fail startup, not silently allow
        every action through with no governance -- Gap C."""
        from responsibleai.dashboard.config import Settings
        from responsibleai.db.engine import create_engine as _create_engine

        settings = Settings(enterprise_mode=True, mcp_governance_enabled=False)
        engine = _create_engine(":memory:")
        await engine.init()
        with pytest.raises(HeartEnforcementError):
            await verify_heart_production_enforcement(settings, engine)
        await engine.close()
