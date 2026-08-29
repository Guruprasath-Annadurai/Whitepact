"""Tests for `governance/oidc_subject_classifier.py` — the deployer-
configured resolution of the "oidc" kind's documented mechanism-vs-
identity-type ambiguity. See that module's docstring and
docs/heart-production/03_ZERO_TRUST_IDENTITY.md.
"""

from __future__ import annotations

from responsibleai.governance.models import IdentityKind
from responsibleai.governance.oidc_subject_classifier import classify_oidc_subject


class TestUnconfiguredBehaviorIsUnchanged:
    """The default (human_indicator_claim=None) must reproduce this
    codebase's existing behavior exactly -- every OIDC identity stays
    IdentityKind.OIDC, regardless of what's in the token."""

    def test_no_configured_claim_returns_oidc_even_with_amr_present(self) -> None:
        claims = {"sub": "user-1", "amr": ["pwd", "mfa"]}
        assert classify_oidc_subject(claims, human_indicator_claim=None) == IdentityKind.OIDC

    def test_empty_claims_with_no_config_returns_oidc(self) -> None:
        assert classify_oidc_subject({}, human_indicator_claim=None) == IdentityKind.OIDC


class TestConfiguredClaimMatching:
    def test_matching_value_in_a_list_claim_returns_human(self) -> None:
        claims = {"sub": "user-1", "amr": ["pwd", "mfa"]}
        result = classify_oidc_subject(
            claims, human_indicator_claim="amr", human_indicator_values=["pwd", "mfa", "otp"]
        )
        assert result == IdentityKind.HUMAN

    def test_matching_scalar_value_returns_human(self) -> None:
        claims = {"sub": "user-1", "gty": "password"}
        result = classify_oidc_subject(
            claims, human_indicator_claim="gty", human_indicator_values=["password"]
        )
        assert result == IdentityKind.HUMAN

    def test_non_matching_value_returns_oidc(self) -> None:
        claims = {"sub": "svc-1", "gty": "client-credentials"}
        result = classify_oidc_subject(
            claims, human_indicator_claim="gty", human_indicator_values=["password"]
        )
        assert result == IdentityKind.OIDC

    def test_absent_claim_returns_oidc(self) -> None:
        """A client-credentials token from a well-behaved IdP simply
        omits amr entirely -- this must fail safe to OIDC, not raise
        or guess."""
        claims = {"sub": "svc-1"}
        result = classify_oidc_subject(
            claims, human_indicator_claim="amr", human_indicator_values=["pwd", "mfa"]
        )
        assert result == IdentityKind.OIDC

    def test_configured_claim_with_no_expected_values_returns_oidc(self) -> None:
        """A misconfiguration (claim set, but no values to match
        against) must fail safe, not treat presence alone as a match."""
        claims = {"sub": "user-1", "amr": ["pwd"]}
        result = classify_oidc_subject(
            claims, human_indicator_claim="amr", human_indicator_values=[]
        )
        assert result == IdentityKind.OIDC

    def test_never_returns_human_without_an_explicit_matching_signal(self) -> None:
        """The core safety property: HUMAN is only ever returned when
        every one of (configured claim name, claim present, value
        matches) holds. Never a side effect of some other field."""
        claims = {"sub": "user-1", "email": "someone@example.com", "name": "Someone"}
        result = classify_oidc_subject(
            claims, human_indicator_claim="amr", human_indicator_values=["pwd"]
        )
        assert result == IdentityKind.OIDC
