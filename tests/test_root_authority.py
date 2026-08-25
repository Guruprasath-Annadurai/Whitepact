"""Tests for Heart Phase H3 — Root of Authority (`governance/root_authority.py`).

Covers every `RootValidationStatus` branch of `validate_root_chain()` plus
Hypothesis property tests for the chain-walking invariants: a chain that
terminates at a HUMAN/ORGANIZATION root is always VALID, a cycle is always
detected before `_MAX_CHAIN_DEPTH` is exhausted, and a non-terminal root
with no `authority_source` is never valid.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.root_authority import (
    RootAuthorityRecord,
    RootResolver,
    RootType,
    RootValidationResult,
    RootValidationStatus,
    build_root_authority_record,
    compute_root_digest,
    validate_root_chain,
)


def _resolver(store: dict[str, RootAuthorityRecord]) -> RootResolver:
    def resolve(root_id: str) -> RootAuthorityRecord | None:
        return store.get(root_id)

    return resolve


class TestRootAuthorityRecord:
    def test_human_is_terminal(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        assert record.is_terminal()

    def test_organization_is_terminal(self) -> None:
        record = build_root_authority_record("org1", RootType.ORGANIZATION, "issuer", "saml")
        assert record.is_terminal()

    def test_service_principal_is_not_terminal(self) -> None:
        record = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        assert not record.is_terminal()

    def test_workload_identity_is_not_terminal(self) -> None:
        record = build_root_authority_record("wi1", RootType.WORKLOAD_IDENTITY, "issuer", "spiffe")
        assert not record.is_terminal()

    def test_canonical_digest_is_deterministic(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        expected = compute_root_digest(
            record.root_id,
            record.root_type,
            record.subject_id,
            record.organization_id,
            record.issuer,
            record.verification_method,
            record.authority_source,
            record.issued_at,
        )
        assert record.canonical_digest == expected

    def test_two_records_same_fields_different_digest_due_to_root_id(self) -> None:
        r1 = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        r2 = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        assert r1.canonical_digest != r2.canonical_digest  # distinct root_id/issued_at

    def test_to_dict_round_trips_key_fields(self) -> None:
        record = build_root_authority_record(
            "u1", RootType.HUMAN, "issuer", "oidc", organization_id="org1"
        )
        d = record.to_dict()
        assert d["root_id"] == record.root_id
        assert d["root_type"] == "HUMAN"
        assert d["subject_id"] == "u1"
        assert d["organization_id"] == "org1"

    def test_is_temporally_valid_true_by_default(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        assert record.is_temporally_valid()

    def test_is_temporally_valid_false_when_revoked(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(record, "revoked_at", datetime.now(UTC))
        assert not record.is_temporally_valid()

    def test_is_temporally_valid_false_when_not_yet_valid(self) -> None:
        record = build_root_authority_record(
            "u1", RootType.HUMAN, "issuer", "oidc", not_before=datetime.now(UTC) + timedelta(days=1)
        )
        assert not record.is_temporally_valid()

    def test_is_temporally_valid_false_when_expired(self) -> None:
        record = build_root_authority_record(
            "u1", RootType.HUMAN, "issuer", "oidc", expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        assert not record.is_temporally_valid()

    def test_is_temporally_valid_at_exact_expiry_boundary_is_expired(self) -> None:
        now = datetime.now(UTC)
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc", expires_at=now)
        assert not record.is_temporally_valid(now=now)


class TestValidateRootChainTerminal:
    def test_human_root_valid_immediately(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.VALID
        assert result.is_valid
        assert result.chain == (record.root_id,)

    def test_organization_root_valid_immediately(self) -> None:
        record = build_root_authority_record("org1", RootType.ORGANIZATION, "issuer", "saml")
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.VALID

    def test_revoked_human_root_is_revoked(self) -> None:
        record = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(record, "revoked_at", datetime.now(UTC))
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.REVOKED
        assert not result.is_valid

    def test_not_yet_valid_human_root(self) -> None:
        record = build_root_authority_record(
            "u1", RootType.HUMAN, "issuer", "oidc", not_before=datetime.now(UTC) + timedelta(days=1)
        )
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.NOT_YET_VALID

    def test_expired_human_root(self) -> None:
        record = build_root_authority_record(
            "u1", RootType.HUMAN, "issuer", "oidc", expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.EXPIRED


class TestValidateRootChainWalking:
    def test_service_principal_chain_to_organization_is_valid(self) -> None:
        org = build_root_authority_record("org1", RootType.ORGANIZATION, "issuer", "saml")
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org.root_id
        )
        store = {org.root_id: org, sp.root_id: sp}
        result = validate_root_chain(sp, _resolver(store))
        assert result.status == RootValidationStatus.VALID
        assert result.chain == (sp.root_id, org.root_id)

    def test_multi_hop_chain_to_human_is_valid(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        sp1 = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=human.root_id
        )
        sp2 = build_root_authority_record(
            "sp2", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=sp1.root_id
        )
        store = {human.root_id: human, sp1.root_id: sp1, sp2.root_id: sp2}
        result = validate_root_chain(sp2, _resolver(store))
        assert result.status == RootValidationStatus.VALID
        assert result.chain == (sp2.root_id, sp1.root_id, human.root_id)

    def test_service_principal_with_no_source_cannot_self_originate(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        result = validate_root_chain(sp, _resolver({}))
        assert result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE

    def test_workload_identity_with_no_source_cannot_self_originate(self) -> None:
        wi = build_root_authority_record("wi1", RootType.WORKLOAD_IDENTITY, "issuer", "spiffe")
        result = validate_root_chain(wi, _resolver({}))
        assert result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE

    def test_dangling_authority_source_is_source_not_found(self) -> None:
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source="does-not-exist"
        )
        result = validate_root_chain(sp, _resolver({}))
        assert result.status == RootValidationStatus.SOURCE_NOT_FOUND

    def test_two_node_cycle_detected(self) -> None:
        a = build_root_authority_record("a", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        b = build_root_authority_record(
            "b", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=a.root_id
        )
        object.__setattr__(a, "authority_source", b.root_id)
        store = {a.root_id: a, b.root_id: b}
        result = validate_root_chain(a, _resolver(store))
        assert result.status == RootValidationStatus.CYCLE_DETECTED

    def test_self_referential_cycle_detected(self) -> None:
        a = build_root_authority_record("a", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        object.__setattr__(a, "authority_source", a.root_id)
        store = {a.root_id: a}
        result = validate_root_chain(a, _resolver(store))
        assert result.status == RootValidationStatus.CYCLE_DETECTED

    def test_chain_too_deep(self) -> None:
        prev = build_root_authority_record("root0", RootType.ORGANIZATION, "issuer", "saml")
        store: dict[str, RootAuthorityRecord] = {prev.root_id: prev}
        for i in range(40):
            nxt = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=prev.root_id
            )
            store[nxt.root_id] = nxt
            prev = nxt
        result = validate_root_chain(prev, _resolver(store))
        assert result.status == RootValidationStatus.CHAIN_TOO_DEEP

    def test_revoked_intermediate_ancestor_invalidates_chain(self) -> None:
        """Regression test for the H3 bug: the code originally branched on
        the ancestor's TYPE instead of its TEMPORAL state, so a revoked
        ORGANIZATION ancestor was misreported as SOURCE_NOT_HUMAN_OR_ORG or
        ROOT_TYPE_CANNOT_SELF_ORIGINATE instead of REVOKED."""
        org = build_root_authority_record("org1", RootType.ORGANIZATION, "issuer", "saml")
        object.__setattr__(org, "revoked_at", datetime.now(UTC))
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org.root_id
        )
        store = {org.root_id: org, sp.root_id: sp}
        result = validate_root_chain(sp, _resolver(store))
        assert result.status == RootValidationStatus.REVOKED
        assert result.detail is not None and "revoked" in result.detail

    def test_not_yet_valid_intermediate_ancestor(self) -> None:
        org = build_root_authority_record(
            "org1", RootType.ORGANIZATION, "issuer", "saml", not_before=datetime.now(UTC) + timedelta(days=1)
        )
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org.root_id
        )
        store = {org.root_id: org, sp.root_id: sp}
        result = validate_root_chain(sp, _resolver(store))
        assert result.status == RootValidationStatus.NOT_YET_VALID

    def test_expired_intermediate_ancestor(self) -> None:
        org = build_root_authority_record(
            "org1", RootType.ORGANIZATION, "issuer", "saml", expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org.root_id
        )
        store = {org.root_id: org, sp.root_id: sp}
        result = validate_root_chain(sp, _resolver(store))
        assert result.status == RootValidationStatus.EXPIRED

    def test_expired_ancestor_deep_in_chain_still_caught(self) -> None:
        """The bug this regression suite guards against would only surface
        once a resolved ancestor is checked mid-walk, not at the leaf --
        verify a 3-hop chain still catches an expired ancestor at hop 2."""
        org = build_root_authority_record(
            "org1", RootType.ORGANIZATION, "issuer", "saml", expires_at=datetime.now(UTC) - timedelta(days=1)
        )
        sp1 = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org.root_id
        )
        sp2 = build_root_authority_record(
            "sp2", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=sp1.root_id
        )
        store = {org.root_id: org, sp1.root_id: sp1, sp2.root_id: sp2}
        result = validate_root_chain(sp2, _resolver(store))
        assert result.status == RootValidationStatus.EXPIRED
        assert result.chain == (sp2.root_id, sp1.root_id)


class TestRootValidationResult:
    def test_is_valid_true_only_for_valid_status(self) -> None:
        assert RootValidationResult(RootValidationStatus.VALID, "r1").is_valid
        assert not RootValidationResult(RootValidationStatus.REVOKED, "r1").is_valid
        assert not RootValidationResult(RootValidationStatus.CYCLE_DETECTED, "r1").is_valid


class TestRootAuthorityProperties:
    """Hypothesis property tests for the chain-walking invariants."""

    @given(
        depth=st.integers(min_value=0, max_value=10),
        terminal_type=st.sampled_from([RootType.HUMAN, RootType.ORGANIZATION]),
    )
    def test_chain_terminating_at_human_or_org_is_always_valid(
        self, depth: int, terminal_type: RootType
    ) -> None:
        root = build_root_authority_record("root", terminal_type, "issuer", "method")
        store: dict[str, RootAuthorityRecord] = {root.root_id: root}
        current = root
        for i in range(depth):
            current = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=current.root_id
            )
            store[current.root_id] = current
        result = validate_root_chain(current, _resolver(store))
        assert result.status == RootValidationStatus.VALID

    @given(cycle_length=st.integers(min_value=1, max_value=8))
    def test_any_cycle_length_is_always_detected(self, cycle_length: int) -> None:
        records = [
            build_root_authority_record(f"n{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
            for i in range(cycle_length)
        ]
        for i, record in enumerate(records):
            next_record = records[(i + 1) % cycle_length]
            object.__setattr__(record, "authority_source", next_record.root_id)
        store = {r.root_id: r for r in records}
        result = validate_root_chain(records[0], _resolver(store))
        assert result.status == RootValidationStatus.CYCLE_DETECTED

    @given(root_type=st.sampled_from([RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY]))
    def test_non_terminal_type_with_no_source_is_never_valid(self, root_type: RootType) -> None:
        record = build_root_authority_record("n1", root_type, "issuer", "method")
        result = validate_root_chain(record, _resolver({}))
        assert result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE
        assert not result.is_valid

    @given(depth=st.integers(min_value=1, max_value=40))
    def test_chain_never_exceeds_max_depth_before_terminating(self, depth: int) -> None:
        """Whatever happens, validate_root_chain() must always terminate
        (never loop forever) and never report VALID for a chain longer
        than _MAX_CHAIN_DEPTH that never reaches a terminal root."""
        prev = build_root_authority_record(
            "sp_first", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source="nonexistent"
        )
        store: dict[str, RootAuthorityRecord] = {}
        current = prev
        for i in range(depth):
            nxt = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=current.root_id
            )
            store[current.root_id] = current
            current = nxt
        result = validate_root_chain(current, _resolver(store))
        assert result.status in (
            RootValidationStatus.SOURCE_NOT_FOUND,
            RootValidationStatus.CHAIN_TOO_DEEP,
        )
