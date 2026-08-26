"""Tests for Heart Production Integration Phase 2 — the Identity →
Heart Root-Authority Adapter (`governance/identity_authority_adapter.py`).

Covers the full `IdentityContext.kind` → `RootType` mapping, the
fail-safe default for unrecognized kinds, the `PrincipalClaim` path,
and — the actual point of the adapter — that a record it produces
still correctly fails closed via `validate_root_chain()` (H3) without
a resolvable authority source, and correctly validates once one is
supplied. Plus Hypothesis property tests for the core invariant: only
`"human"` and `"api_key"` ever map to a terminal `RootType`; every
other kind, known or unknown, always maps to non-terminal.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.identity_authority_adapter import (
    build_root_authority_record_from_identity,
    build_root_authority_record_from_principal_claim,
    identity_context_to_root_type,
)
from responsibleai.governance.models import IdentityContext
from responsibleai.governance.principal import PrincipalClaim
from responsibleai.governance.root_authority import (
    RootType,
    RootValidationStatus,
    validate_root_chain,
)

_KNOWN_KINDS = ("human", "api_key", "oidc", "vc", "agent", "workload")
_TERMINAL_KINDS = ("human", "api_key")
_NON_TERMINAL_KNOWN_KINDS = tuple(k for k in _KNOWN_KINDS if k not in _TERMINAL_KINDS)


def _identity(kind: str, identity_id: str = "id1", org_id: str | None = "org1") -> IdentityContext:
    return IdentityContext(identity_id=identity_id, kind=kind, org_id=org_id)


class TestKindToRootTypeMapping:
    def test_human_maps_to_terminal_human(self) -> None:
        assert identity_context_to_root_type(_identity("human")) == RootType.HUMAN

    def test_api_key_maps_to_terminal_organization(self) -> None:
        assert identity_context_to_root_type(_identity("api_key")) == RootType.ORGANIZATION

    def test_oidc_maps_to_non_terminal_workload_identity(self) -> None:
        assert identity_context_to_root_type(_identity("oidc")) == RootType.WORKLOAD_IDENTITY

    def test_vc_maps_to_non_terminal_service_principal(self) -> None:
        assert identity_context_to_root_type(_identity("vc")) == RootType.SERVICE_PRINCIPAL

    def test_agent_maps_to_non_terminal_service_principal(self) -> None:
        assert identity_context_to_root_type(_identity("agent")) == RootType.SERVICE_PRINCIPAL

    def test_workload_maps_to_non_terminal_workload_identity(self) -> None:
        assert identity_context_to_root_type(_identity("workload")) == RootType.WORKLOAD_IDENTITY

    def test_unrecognized_kind_maps_to_fail_safe_non_terminal_default(self) -> None:
        assert (
            identity_context_to_root_type(_identity("some_future_kind"))
            == RootType.WORKLOAD_IDENTITY
        )


class TestBuildRootAuthorityRecordFromIdentity:
    def test_record_carries_identity_and_org_fields(self) -> None:
        identity = _identity("human", identity_id="u1", org_id="org-42")
        record = build_root_authority_record_from_identity(
            identity, issuer="dashboard", verification_method="saml_session"
        )
        assert record.subject_id == "u1"
        assert record.organization_id == "org-42"
        assert record.root_type == RootType.HUMAN

    def test_terminal_record_validates_immediately_with_no_resolver(self) -> None:
        identity = _identity("api_key")
        record = build_root_authority_record_from_identity(
            identity, issuer="org_repository", verification_method="api_key_hash"
        )
        result = validate_root_chain(record, lambda rid: None)
        assert result.is_valid

    def test_non_terminal_record_fails_closed_without_authority_source(self) -> None:
        identity = _identity("oidc")
        record = build_root_authority_record_from_identity(
            identity, issuer="idp", verification_method="oidc"
        )
        result = validate_root_chain(record, lambda rid: None)
        assert result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE
        assert not result.is_valid

    def test_non_terminal_record_validates_once_a_resolvable_source_is_supplied(self) -> None:
        org_identity = _identity("api_key")
        org_root = build_root_authority_record_from_identity(
            org_identity, issuer="org_repository", verification_method="api_key_hash"
        )
        oidc_identity = _identity("oidc", identity_id="oidc:sub123")
        oidc_record = build_root_authority_record_from_identity(
            oidc_identity,
            issuer="idp",
            verification_method="oidc",
            authority_source=org_root.root_id,
        )
        store = {org_root.root_id: org_root}
        result = validate_root_chain(oidc_record, lambda rid: store.get(rid))
        assert result.is_valid


class TestBuildRootAuthorityRecordFromPrincipalClaim:
    def test_always_service_principal_regardless_of_holder_kind(self) -> None:
        for holder_kind in ("service_account", "external_agent"):
            claim = PrincipalClaim(
                principal_id="p1",
                org_id="org1",
                issuer="https://issuer.example.com",
                credential_type="jwt_vc",
                holder_kind=holder_kind,
            )
            record = build_root_authority_record_from_principal_claim(claim)
            assert record.root_type == RootType.SERVICE_PRINCIPAL
            assert not record.is_terminal()

    def test_carries_issuer_and_credential_type_directly(self) -> None:
        claim = PrincipalClaim(
            principal_id="p1",
            org_id="org1",
            issuer="https://issuer.example.com",
            credential_type="jwt_vc",
            holder_kind="service_account",
        )
        record = build_root_authority_record_from_principal_claim(claim)
        assert record.issuer == "https://issuer.example.com"
        assert record.verification_method == "jwt_vc"

    def test_verification_id_carried_as_evidence_ref(self) -> None:
        claim = PrincipalClaim(
            principal_id="p1",
            org_id="org1",
            issuer="iss",
            credential_type="jwt_vc",
            holder_kind="service_account",
        )
        record = build_root_authority_record_from_principal_claim(claim)
        assert record.evidence_refs == (claim.verification_id,)

    def test_fails_closed_without_authority_source(self) -> None:
        claim = PrincipalClaim(
            principal_id="p1",
            org_id="org1",
            issuer="iss",
            credential_type="jwt_vc",
            holder_kind="external_agent",
        )
        record = build_root_authority_record_from_principal_claim(claim)
        result = validate_root_chain(record, lambda rid: None)
        assert result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE


class TestIdentityAuthorityAdapterProperties:
    """Hypothesis property tests for the core invariant."""

    @given(kind=st.sampled_from(_TERMINAL_KINDS))
    def test_terminal_kinds_always_map_to_terminal_root_type(self, kind: str) -> None:
        root_type = identity_context_to_root_type(_identity(kind))
        assert root_type in (RootType.HUMAN, RootType.ORGANIZATION)

    @given(kind=st.sampled_from(_NON_TERMINAL_KNOWN_KINDS))
    def test_known_non_terminal_kinds_never_map_to_terminal_root_type(self, kind: str) -> None:
        root_type = identity_context_to_root_type(_identity(kind))
        assert root_type in (RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY)

    @given(kind=st.text(min_size=1, max_size=20).filter(lambda k: k not in _KNOWN_KINDS))
    def test_arbitrary_unknown_kinds_never_map_to_terminal_root_type(self, kind: str) -> None:
        root_type = identity_context_to_root_type(_identity(kind))
        assert root_type in (RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY)

    @given(kind=st.sampled_from(_NON_TERMINAL_KNOWN_KINDS))
    def test_non_terminal_identity_records_never_self_validate_without_a_source(
        self, kind: str
    ) -> None:
        identity = _identity(kind)
        record = build_root_authority_record_from_identity(
            identity, issuer="iss", verification_method="method"
        )
        result = validate_root_chain(record, lambda rid: None)
        assert not result.is_valid
