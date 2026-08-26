"""Heart Phase H17 — Enterprise Hardening.

Locks in a real hardening gap this phase found and fixed: none of the
13 Heart modules (H1-H13) were re-exported from `governance/__init__.py`,
so every prior phase's own tests had to import directly from
`responsibleai.governance.<module>` rather than the clean
`from responsibleai.governance import ...` surface every other
governance type in this package already offers. This test both
confirms the fix and acts as a permanent regression guard: if a future
change accidentally removes one of these names from `__all__` (or
breaks an import cycle), this test fails immediately rather than the
gap silently reappearing.
"""

from __future__ import annotations

import responsibleai.governance as governance


class TestHeartSymbolsAreExported:
    """Every Heart phase's genuinely public API is reachable from
    `responsibleai.governance` directly, not only from its own
    submodule."""

    def test_root_authority_symbols_exported(self) -> None:
        for name in (
            "RootType",
            "RootAuthorityRecord",
            "RootResolver",
            "RootValidationStatus",
            "RootValidationResult",
            "build_root_authority_record",
            "validate_root_chain",
        ):
            assert hasattr(governance, name), f"{name} not exported from responsibleai.governance"
            assert name in governance.__all__

    def test_consent_proof_symbols_exported(self) -> None:
        for name in (
            "ConsentMethod",
            "ConsentProof",
            "ConsentValidationStatus",
            "ConsentValidationResult",
            "build_consent_proof",
            "validate_consent_proof",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_purpose_binding_symbols_exported(self) -> None:
        for name in (
            "PurposeBinding",
            "PurposeBindingStatus",
            "PurposeBindingValidationResult",
            "build_purpose_binding",
            "validate_purpose_binding",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_delegation_kernel_symbols_exported(self) -> None:
        for name in (
            "DelegationLegitimacyStatus",
            "DelegationLegitimacyResult",
            "validate_delegation_legitimacy",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_non_delegable_authority_symbols_exported(self) -> None:
        for name in ("NonDelegableScope", "NonDelegableViolation", "check_non_delegable_authority"):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_authority_lifetime_symbols_exported(self) -> None:
        for name in (
            "LifetimeWindow",
            "LifetimeStatus",
            "LifetimeCheckResult",
            "check_lifetime",
            "ROOT_AUTHORITY_LIFETIME_WINDOW",
            "CONSENT_PROOF_LIFETIME_WINDOW",
            "PURPOSE_BINDING_LIFETIME_WINDOW",
            "DELEGATION_LEGITIMACY_LIFETIME_WINDOW",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_revocation_kernel_symbols_exported(self) -> None:
        for name in (
            "RevocationEpoch",
            "bump_epoch",
            "RevocationEpochCheckStatus",
            "RevocationEpochCheckResult",
            "check_revocation_epoch",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_authority_conflict_resolver_symbols_exported(self) -> None:
        for name in (
            "ConflictResolutionStatus",
            "ConflictResolutionResult",
            "resolve_authority_conflicts",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_heart_veto_symbols_exported(self) -> None:
        for name in (
            "HeartVetoStatus",
            "HeartVetoRecord",
            "HeartVetoError",
            "apply_heart_veto",
            "enforce_heart_veto",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_legitimacy_envelope_symbols_exported(self) -> None:
        for name in ("LegitimacyEnvelope", "build_legitimacy_envelope"):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_sovereignty_kernel_module_exported(self) -> None:
        assert hasattr(governance, "sovereignty_kernel")
        assert "sovereignty_kernel" in governance.__all__
        assert hasattr(governance.sovereignty_kernel, "evaluate")

    def test_constitution_symbols_exported(self) -> None:
        for name in (
            "ConstitutionalLawCode",
            "AuthorityConstitutionVersion",
            "CONSTITUTION_V1",
            "build_constitution_version",
            "get_constitution_version",
            "current_constitution",
            "explain_constitution",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_authority_lattice_symbols_exported(self) -> None:
        for name in (
            "AuthorityEnvelope",
            "LatticeComparisonStatus",
            "LatticeComparisonResult",
            "UnrepresentableConstraintError",
            "compare_envelopes",
            "intersect_envelopes",
            "authority_context_to_envelope",
            "envelope_to_authority_context",
            "compare_authority_contexts",
        ):
            assert hasattr(governance, name)
            assert name in governance.__all__

    def test_authority_grant_symbols_exported(self) -> None:
        """Production Integration Phase 1's AuthorityGrant (the boundary
        object between the Heart and WhitePact's live decision path)
        is exported the same way every Heart symbol already is."""
        for name in ("AuthorityGrant", "build_authority_grant", "DEFAULT_GRANT_TTL_SECONDS"):
            assert hasattr(governance, name)
            assert name in governance.__all__


class TestEndToEndUsageViaPackageImport:
    """A caller using only `from responsibleai.governance import ...`
    (never touching an internal submodule path directly) can exercise
    a full Heart decision -- the actual point of exporting these
    symbols in the first place."""

    def test_full_heart_decision_via_package_level_imports_only(self) -> None:
        env = governance.sovereignty_kernel.evaluate("org1", "agent1")
        assert env.is_legitimate

    def test_root_authority_via_package_import(self) -> None:
        human = governance.build_root_authority_record(
            "u1", governance.RootType.HUMAN, "issuer", "oidc"
        )
        result = governance.validate_root_chain(human, lambda rid: None)
        assert result.is_valid
