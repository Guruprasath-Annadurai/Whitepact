"""Tests for Heart Production Integration Phase 3 (persistence):
`RootAuthorityRepository` and `ConsentProofRepository`. See
docs/enterprise-neural/REMEDIATION_GAP3_HEART_PRODUCTION_INTEGRATION.md.

Beyond plain round-trip persistence, this file also proves the
existing, already-tested Heart validation logic
(`root_authority.validate_root_chain()`, `consent_proof.validate_consent_proof()`)
composes correctly with *persisted, retrieved-from-a-real-DB* records,
not just in-memory ones -- the property the remediation directive asks
for: an authority tree assembled from real storage still rejects
revoked-root reuse and consenting-root identity substitution exactly
as the in-memory unit tests already prove it does for
constructed-in-place objects.
"""

from __future__ import annotations

import pytest

from responsibleai.db.consent_proof_repository import (
    ConsentProofNotFoundError,
    ConsentProofRepository,
)
from responsibleai.db.engine import create_engine
from responsibleai.db.root_authority_repository import (
    RootAuthorityRecordNotFoundError,
    RootAuthorityRepository,
)
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.consent_proof import validate_consent_proof as validate_consent
from responsibleai.governance.root_authority import (
    RootType,
    RootValidationStatus,
    build_root_authority_record,
)
from responsibleai.governance.root_authority import validate_root_chain as validate_root


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


class TestRootAuthorityRepositoryRoundTrip:
    async def test_create_and_get_round_trips_every_field(self, root_repo):
        record = build_root_authority_record(
            subject_id="user-42",
            root_type=RootType.HUMAN,
            issuer="internal-idp",
            verification_method="oidc",
            organization_id="org-1",
            jurisdiction="US",
            evidence_refs=("oidc-sub-abc", "session-xyz"),
        )
        await root_repo.create(record)

        fetched = await root_repo.get(record.root_id)
        assert fetched is not None
        assert fetched.root_id == record.root_id
        assert fetched.subject_id == "user-42"
        assert fetched.root_type == RootType.HUMAN
        assert fetched.organization_id == "org-1"
        assert fetched.jurisdiction == "US"
        assert fetched.evidence_refs == ("oidc-sub-abc", "session-xyz")
        assert fetched.canonical_digest == record.canonical_digest
        assert fetched.revoked_at is None

    async def test_get_unknown_root_returns_none(self, root_repo):
        assert await root_repo.get("does-not-exist") is None

    async def test_non_terminal_record_persists_its_authority_source(self, root_repo):
        parent = build_root_authority_record(
            subject_id="org-1",
            root_type=RootType.ORGANIZATION,
            issuer="idp",
            verification_method="oidc",
        )
        await root_repo.create(parent)
        child = build_root_authority_record(
            subject_id="svc-billing",
            root_type=RootType.SERVICE_PRINCIPAL,
            issuer="internal",
            verification_method="mtls",
            authority_source=parent.root_id,
        )
        await root_repo.create(child)

        fetched = await root_repo.get(child.root_id)
        assert fetched is not None
        assert fetched.authority_source == parent.root_id


class TestRootAuthorityRepositoryRevocation:
    async def test_revoke_sets_revocation_fields(self, root_repo):
        record = build_root_authority_record(
            subject_id="user-1", root_type=RootType.HUMAN, issuer="idp", verification_method="oidc"
        )
        await root_repo.create(record)

        revoked = await root_repo.revoke(record.root_id, revoked_by="admin-1", reason="offboarded")
        assert revoked.revoked_at is not None
        assert revoked.revoked_by == "admin-1"
        assert revoked.revoke_reason == "offboarded"

    async def test_revoke_unknown_root_raises(self, root_repo):
        with pytest.raises(RootAuthorityRecordNotFoundError):
            await root_repo.revoke("does-not-exist", revoked_by="admin-1")


class TestConsentProofRepositoryRoundTrip:
    async def test_create_and_get_round_trips_every_field(self, consent_repo):
        proof = build_consent_proof(
            subject_id="user-42",
            consenting_root_id="root-abc",
            grantee_id="agent-1",
            scope_description="read billing records",
            purpose="quarterly audit",
            consent_method=ConsentMethod.EXPLICIT_UI_ACTION,
            evidence_refs=("click-event-123",),
        )
        await consent_repo.create(proof)

        fetched = await consent_repo.get(proof.consent_id)
        assert fetched is not None
        assert fetched.consent_id == proof.consent_id
        assert fetched.consenting_root_id == "root-abc"
        assert fetched.grantee_id == "agent-1"
        assert fetched.consent_method == ConsentMethod.EXPLICIT_UI_ACTION
        assert fetched.evidence_refs == ("click-event-123",)
        assert fetched.canonical_digest == proof.canonical_digest

    async def test_get_unknown_consent_returns_none(self, consent_repo):
        assert await consent_repo.get("does-not-exist") is None


class TestConsentProofRepositoryRevocation:
    async def test_revoke_sets_revocation_fields(self, consent_repo):
        proof = build_consent_proof(
            subject_id="user-1",
            consenting_root_id="root-1",
            grantee_id="agent-1",
            scope_description="x",
            purpose="y",
            consent_method=ConsentMethod.SIGNED_DOCUMENT,
        )
        await consent_repo.create(proof)

        revoked = await consent_repo.revoke(
            proof.consent_id, revoked_by="user-1", reason="withdrew consent"
        )
        assert revoked.revoked_at is not None
        assert revoked.revoked_by == "user-1"
        assert revoked.revoke_reason == "withdrew consent"

    async def test_revoke_unknown_consent_raises(self, consent_repo):
        with pytest.raises(ConsentProofNotFoundError):
            await consent_repo.revoke("does-not-exist", revoked_by="user-1")


class TestPersistedChainStillEnforcesHeartInvariants:
    """The property the remediation directive asks for: real, persisted
    (not merely in-memory-constructed) authority records must still
    fail closed under revocation and identity substitution once
    resolved back out of storage."""

    async def test_persisted_two_hop_chain_resolves_to_terminal_root(self, root_repo):
        org_root = build_root_authority_record(
            subject_id="org-1",
            root_type=RootType.ORGANIZATION,
            issuer="idp",
            verification_method="oidc",
        )
        await root_repo.create(org_root)
        service_root = build_root_authority_record(
            subject_id="svc-billing",
            root_type=RootType.SERVICE_PRINCIPAL,
            issuer="internal",
            verification_method="mtls",
            authority_source=org_root.root_id,
        )
        await root_repo.create(service_root)

        store = {org_root.root_id: org_root, service_root.root_id: service_root}
        fetched_service = await root_repo.get(service_root.root_id)
        assert fetched_service is not None
        result = validate_root(fetched_service, lambda rid: store.get(rid))
        assert result.status == RootValidationStatus.VALID
        assert result.chain == (service_root.root_id, org_root.root_id)

    async def test_revoked_root_reused_as_a_chain_ancestor_fails_closed(self, root_repo):
        """A previously-legitimate root, now revoked, must not silently
        keep validating a descendant chain that points at it -- the
        'revoked-grant reuse' attack the directive names."""
        org_root = build_root_authority_record(
            subject_id="org-1",
            root_type=RootType.ORGANIZATION,
            issuer="idp",
            verification_method="oidc",
        )
        await root_repo.create(org_root)
        await root_repo.revoke(org_root.root_id, revoked_by="admin", reason="org offboarded")
        revoked_org_root = await root_repo.get(org_root.root_id)
        assert revoked_org_root is not None

        service_root = build_root_authority_record(
            subject_id="svc-billing",
            root_type=RootType.SERVICE_PRINCIPAL,
            issuer="internal",
            verification_method="mtls",
            authority_source=org_root.root_id,
        )
        await root_repo.create(service_root)

        store = {org_root.root_id: revoked_org_root, service_root.root_id: service_root}
        fetched_service = await root_repo.get(service_root.root_id)
        assert fetched_service is not None
        result = validate_root(fetched_service, lambda rid: store.get(rid))
        assert result.status == RootValidationStatus.REVOKED
        assert result.is_valid is False

    async def test_consent_proof_identity_substitution_is_rejected(self, root_repo, consent_repo):
        """A ConsentProof claiming a different consenting_root_id than
        the one actually validated must be rejected as ROOT_MISMATCH --
        the 'identity substitution' attack the directive names. This
        stays true even when both records are round-tripped through
        real persistence rather than held in-memory."""
        real_root = build_root_authority_record(
            subject_id="user-1", root_type=RootType.HUMAN, issuer="idp", verification_method="oidc"
        )
        await root_repo.create(real_root)
        impostor_root_id = "not-" + real_root.root_id

        proof = build_consent_proof(
            subject_id="user-1",
            consenting_root_id=impostor_root_id,
            grantee_id="agent-1",
            scope_description="transfer funds",
            purpose="payroll",
            consent_method=ConsentMethod.API_AUTHENTICATED_REQUEST,
        )
        await consent_repo.create(proof)

        fetched_proof = await consent_repo.get(proof.consent_id)
        fetched_root = await root_repo.get(real_root.root_id)
        assert fetched_proof is not None
        assert fetched_root is not None

        root_result = validate_root(fetched_root, lambda rid: None)
        outcome = validate_consent(fetched_proof, root_result)
        assert outcome.status.name == "ROOT_MISMATCH"
        assert outcome.is_valid is False

    async def test_revoked_consent_proof_fails_closed_even_with_a_legitimate_root(
        self, root_repo, consent_repo
    ):
        real_root = build_root_authority_record(
            subject_id="user-1", root_type=RootType.HUMAN, issuer="idp", verification_method="oidc"
        )
        await root_repo.create(real_root)

        proof = build_consent_proof(
            subject_id="user-1",
            consenting_root_id=real_root.root_id,
            grantee_id="agent-1",
            scope_description="read records",
            purpose="audit",
            consent_method=ConsentMethod.EXPLICIT_UI_ACTION,
        )
        await consent_repo.create(proof)
        await consent_repo.revoke(proof.consent_id, revoked_by="user-1", reason="changed mind")

        fetched_proof = await consent_repo.get(proof.consent_id)
        fetched_root = await root_repo.get(real_root.root_id)
        assert fetched_proof is not None
        assert fetched_root is not None

        root_result = validate_root(fetched_root, lambda rid: None)
        outcome = validate_consent(fetched_proof, root_result)
        assert outcome.status.name == "REVOKED"
        assert outcome.is_valid is False
