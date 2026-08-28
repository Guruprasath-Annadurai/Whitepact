"""Tests for Zero-Trust Identity Phase 1 (`IdentityKind`,
`governance/models.py`). See
docs/heart-production/03_ZERO_TRUST_IDENTITY.md.

Three things this file proves, beyond `test_identity_authority_adapter.py`'s
existing coverage of the kind -> RootType mapping itself:
1. `IdentityKind` covers all 8 identity types the remediation directive
   names (Human, Organization, Device, BCI Session, Agent, Service,
   Tool, Workload), plus the two pre-existing mechanism-flavored values
   this phase deliberately keeps (`OIDC`, `VERIFIED_CREDENTIAL`).
2. Backward compatibility: every call site that still passes a plain
   `str` literal (as ~30 existing test files across this repo do)
   continues to behave identically -- `IdentityKind` is a `StrEnum`,
   so string equality/hashing/dict-lookup all still work.
3. `identity_kind_from_holder_kind()` reconciles `PrincipalClaim`'s
   independent wire-format `holder_kind` field with `IdentityKind`
   without changing `PrincipalClaim`'s external VC wire values.
"""

from __future__ import annotations

from responsibleai.governance.identity_authority_adapter import (
    _KIND_TO_ROOT_TYPE,
    identity_context_to_root_type,
    identity_kind_from_holder_kind,
)
from responsibleai.governance.models import IdentityContext, IdentityKind
from responsibleai.governance.root_authority import RootType


class TestIdentityKindCoversTheNamedVocabulary:
    def test_all_eight_directive_named_kinds_exist(self) -> None:
        directive_named = {
            "HUMAN",
            "ORGANIZATION",
            "DEVICE",
            "BCI_SESSION",
            "AGENT",
            "SERVICE",
            "TOOL",
            "WORKLOAD",
        }
        assert directive_named.issubset({member.name for member in IdentityKind})

    def test_legacy_mechanism_values_still_present(self) -> None:
        """OIDC and VERIFIED_CREDENTIAL are kept -- not directive-named
        identity types, but removing them would break every existing
        caller. See IdentityKind's own docstring for why they're not
        fully resolved into pure identity types this phase."""
        assert IdentityKind.OIDC == "oidc"
        assert IdentityKind.VERIFIED_CREDENTIAL == "vc"

    def test_every_member_has_an_entry_in_the_root_type_mapping(self) -> None:
        """A member with no mapping entry would silently fall through to
        the fail-safe default instead of an intentional classification
        -- every IdentityKind must be a deliberate row in
        identity_authority_adapter.py's table."""
        for member in IdentityKind:
            assert member in _KIND_TO_ROOT_TYPE, f"{member} has no explicit RootType mapping"

    def test_no_identity_kind_maps_to_a_terminal_root_type_except_human_and_organization(
        self,
    ) -> None:
        terminal = {RootType.HUMAN, RootType.ORGANIZATION}
        for member, root_type in _KIND_TO_ROOT_TYPE.items():
            if member in (IdentityKind.HUMAN, IdentityKind.ORGANIZATION):
                assert root_type in terminal
            else:
                assert root_type not in terminal, (
                    f"{member} unexpectedly maps to a terminal root type {root_type} -- "
                    "only HUMAN/ORGANIZATION may self-originate authority"
                )


class TestNewlyAddedKindsClassifyNonTerminal:
    def test_device_maps_to_workload_identity(self) -> None:
        identity = IdentityContext(identity_id="dev-1", kind=IdentityKind.DEVICE)
        assert identity_context_to_root_type(identity) == RootType.WORKLOAD_IDENTITY

    def test_bci_session_maps_to_workload_identity(self) -> None:
        identity = IdentityContext(identity_id="session-1", kind=IdentityKind.BCI_SESSION)
        assert identity_context_to_root_type(identity) == RootType.WORKLOAD_IDENTITY

    def test_tool_maps_to_service_principal(self) -> None:
        identity = IdentityContext(identity_id="tool-1", kind=IdentityKind.TOOL)
        assert identity_context_to_root_type(identity) == RootType.SERVICE_PRINCIPAL

    def test_service_maps_to_service_principal(self) -> None:
        identity = IdentityContext(identity_id="svc-1", kind=IdentityKind.SERVICE)
        assert identity_context_to_root_type(identity) == RootType.SERVICE_PRINCIPAL


class TestBackwardCompatibilityWithPlainStrings:
    """`IdentityContext.kind` is now typed `IdentityKind`, but Python
    doesn't enforce dataclass field types at runtime, and `StrEnum`
    values compare/hash equal to their plain-string value -- so every
    existing caller passing `kind="human"` (not `IdentityKind.HUMAN`)
    must keep working identically. This is what makes the type
    annotation change non-breaking rather than requiring an update to
    every one of the ~30 test files across this repo that already
    construct `IdentityContext` with a raw string literal."""

    def test_plain_string_kind_still_maps_correctly(self) -> None:
        identity = IdentityContext(identity_id="u1", kind="human")  # type: ignore[arg-type]
        assert identity_context_to_root_type(identity) == RootType.HUMAN

    def test_plain_string_kind_equals_the_enum_member(self) -> None:
        identity = IdentityContext(identity_id="u1", kind="device")  # type: ignore[arg-type]
        assert identity.kind == IdentityKind.DEVICE

    def test_unrecognized_plain_string_still_fails_safe(self) -> None:
        identity = IdentityContext(identity_id="u1", kind="totally_unknown")  # type: ignore[arg-type]
        assert identity_context_to_root_type(identity) == RootType.WORKLOAD_IDENTITY


class TestHolderKindReconciliation:
    def test_service_account_maps_to_service(self) -> None:
        assert identity_kind_from_holder_kind("service_account") == IdentityKind.SERVICE

    def test_external_agent_maps_to_agent(self) -> None:
        assert identity_kind_from_holder_kind("external_agent") == IdentityKind.AGENT

    def test_unrecognized_holder_kind_fails_safe_to_agent(self) -> None:
        assert identity_kind_from_holder_kind("some_future_wire_value") == IdentityKind.AGENT

    def test_both_known_holder_kind_mappings_stay_non_terminal(self) -> None:
        """Whatever holder_kind maps to, it must never resolve to a
        terminal RootType -- a verified principal is never human by
        construction (see identity_authority_adapter.py's own
        docstring)."""
        for holder_kind in ("service_account", "external_agent", "unknown_future_value"):
            kind = identity_kind_from_holder_kind(holder_kind)
            assert _KIND_TO_ROOT_TYPE[kind] in (
                RootType.SERVICE_PRINCIPAL,
                RootType.WORKLOAD_IDENTITY,
            )
