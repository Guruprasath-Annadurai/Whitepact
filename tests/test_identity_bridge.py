"""Tests for the Identity Bridge adapters (`integrations/identity_bridge.py`).

Sample payloads below are shaped to match each provider's own published
ID token claim reference (Microsoft identity platform, Google's OpenID
Connect docs, Okta's ID token reference, AWS Cognito's ID token
reference) -- not captured from a live tenant of any of these four
providers, per that module's own honesty note. These tests verify the
claims-shape mapping is correct against the documented shape, nothing
more.
"""

from __future__ import annotations

from responsibleai.integrations.identity_bridge import (
    aws_claims_to_identity,
    entra_claims_to_identity,
    google_claims_to_identity,
    map_groups_to_authority,
    okta_claims_to_identity,
)

# Shaped per Microsoft identity platform's v2.0 ID token claims reference.
_ENTRA_CLAIMS = {
    "aud": "6cb04018-a3f5-46a7-b995-940c78f5aef3",
    "iss": "https://login.microsoftonline.com/9188040d-6c67-4c5b-b112-36a304b66dad/v2.0",
    "iat": 1700000000,
    "nbf": 1700000000,
    "exp": 1700003600,
    "name": "Alice Treasury",
    "oid": "00000000-0000-0000-66f3-3332eca7ea81",
    "preferred_username": "alice@contoso.com",
    "sub": "AAAAAAAAAAAAAAAAAAAAAIkzqFVrSaSaFHy782bbtaQ",
    "tid": "9188040d-6c67-4c5b-b112-36a304b66dad",
    "ver": "2.0",
    "groups": ["4c8d1c9e-0d1c-4b1c-8d1c-4b1c8d1c4b1c", "8b1c4b1c-8d1c-4b1c-8d1c-4b1c8d1c4b1c"],
}

# Shaped per Google's OpenID Connect ID token payload documentation.
_GOOGLE_CLAIMS = {
    "iss": "https://accounts.google.com",
    "azp": "1234987819200.apps.googleusercontent.com",
    "aud": "1234987819200.apps.googleusercontent.com",
    "sub": "10769150350006150715113082367",
    "email": "alice@acme-corp.com",
    "email_verified": True,
    "hd": "acme-corp.com",
    "name": "Alice Treasury",
    "iat": 1700000000,
    "exp": 1700003600,
}

# Google personal account -- no Workspace org, so `hd` is genuinely absent.
_GOOGLE_PERSONAL_CLAIMS = {
    "iss": "https://accounts.google.com",
    "sub": "10769150350006150715113082367",
    "email": "alice.personal@gmail.com",
    "email_verified": True,
    "name": "Alice",
    "iat": 1700000000,
    "exp": 1700003600,
}

# Shaped per Okta's ID token claims reference (with a `groups` claim
# configured on the Authorization Server, and a hypothetical custom
# `org_id` claim -- Okta has no standard tenant claim, see the module
# docstring).
_OKTA_CLAIMS = {
    "sub": "00uid4BxXw6I6TV4m0g3",
    "name": "Alice Treasury",
    "email": "alice@acme.okta.com",
    "ver": 1,
    "iss": "https://acme.okta.com/oauth2/default",
    "aud": "6joaFA0z2XjkMwpxvQE1",
    "iat": 1700000000,
    "exp": 1700003600,
    "org_id": "acme-treasury",
    "groups": ["Finance-Admins", "Employees"],
}

# Shaped per AWS Cognito's ID token claims reference.
_COGNITO_CLAIMS = {
    "sub": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
    "cognito:groups": ["finance-admins"],
    "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ExamplePool",
    "cognito:username": "alice.treasury",
    "aud": "1example23456789",
    "event_id": "3f4de883-59a2-4b02-9c1e-example",
    "token_use": "id",
    "auth_time": 1700000000,
    "custom:org_id": "acme-treasury",
    "name": "Alice Treasury",
    "exp": 1700003600,
    "iat": 1700000000,
    "email": "alice@acme-corp.com",
}

# IAM Identity Center's OIDC-compliant token -- no cognito: prefix, no
# token_use claim, indistinguishable from generic OIDC by design.
_IDENTITY_CENTER_CLAIMS = {
    "sub": "a1b2c3d4-5678-90ab-cdef-1234567890ab",
    "iss": "https://identitycenter.amazonaws.com/ssoins-example",
    "aud": "example-client-id",
    "name": "Alice Treasury",
    "email": "alice@acme-corp.com",
    "groups": ["finance-admins"],
    "exp": 1700003600,
    "iat": 1700000000,
}


class TestEntraAdapter:
    def test_maps_oid_as_identity_and_tid_as_org(self) -> None:
        identity = entra_claims_to_identity(_ENTRA_CLAIMS)
        assert identity.provider == "entra"
        assert identity.identity_id == "00000000-0000-0000-66f3-3332eca7ea81"
        assert identity.org_id == "9188040d-6c67-4c5b-b112-36a304b66dad"
        assert identity.email == "alice@contoso.com"
        assert identity.groups == (
            "4c8d1c9e-0d1c-4b1c-8d1c-4b1c8d1c4b1c",
            "8b1c4b1c-8d1c-4b1c-8d1c-4b1c8d1c4b1c",
        )

    def test_falls_back_to_roles_when_groups_absent(self) -> None:
        claims = {k: v for k, v in _ENTRA_CLAIMS.items() if k != "groups"}
        claims["roles"] = ["TreasuryApprover"]
        identity = entra_claims_to_identity(claims)
        assert identity.groups == ("TreasuryApprover",)

    def test_identity_context_uses_oid_not_sub(self) -> None:
        ctx = entra_claims_to_identity(_ENTRA_CLAIMS).to_identity_context()
        assert ctx.identity_id == "00000000-0000-0000-66f3-3332eca7ea81"
        assert ctx.org_id == "9188040d-6c67-4c5b-b112-36a304b66dad"
        assert ctx.kind == "oidc"


class TestGoogleAdapter:
    def test_maps_hd_as_org_for_workspace_account(self) -> None:
        identity = google_claims_to_identity(_GOOGLE_CLAIMS)
        assert identity.provider == "google"
        assert identity.identity_id == "10769150350006150715113082367"
        assert identity.org_id == "acme-corp.com"
        assert identity.email == "alice@acme-corp.com"
        assert identity.groups == ()

    def test_personal_account_has_no_org(self) -> None:
        identity = google_claims_to_identity(_GOOGLE_PERSONAL_CLAIMS)
        assert identity.org_id is None
        assert identity.email == "alice.personal@gmail.com"


class TestOktaAdapter:
    def test_maps_groups_and_configurable_org_claim(self) -> None:
        identity = okta_claims_to_identity(_OKTA_CLAIMS)
        assert identity.provider == "okta"
        assert identity.identity_id == "00uid4BxXw6I6TV4m0g3"
        assert identity.org_id == "acme-treasury"
        assert identity.groups == ("Finance-Admins", "Employees")

    def test_custom_org_claim_name(self) -> None:
        claims = {**_OKTA_CLAIMS, "tenant": "acme-treasury", "org_id": None}
        identity = okta_claims_to_identity(claims, org_claim="tenant")
        assert identity.org_id == "acme-treasury"

    def test_missing_org_claim_yields_none_not_a_guess(self) -> None:
        claims = {k: v for k, v in _OKTA_CLAIMS.items() if k != "org_id"}
        identity = okta_claims_to_identity(claims)
        assert identity.org_id is None


class TestAwsAdapter:
    def test_cognito_token_uses_cognito_username_and_groups(self) -> None:
        identity = aws_claims_to_identity(_COGNITO_CLAIMS)
        assert identity.provider == "aws"
        assert identity.identity_id == "alice.treasury"
        assert identity.org_id == "acme-treasury"
        assert identity.groups == ("finance-admins",)

    def test_identity_center_token_falls_back_to_generic_oidc_shape(self) -> None:
        identity = aws_claims_to_identity(_IDENTITY_CENTER_CLAIMS)
        assert identity.identity_id == "a1b2c3d4-5678-90ab-cdef-1234567890ab"
        assert identity.groups == ("finance-admins",)
        # No cognito:org_id-equivalent claim in this token shape.
        assert identity.org_id is None

    def test_cognito_username_preferred_over_sub_when_both_present(self) -> None:
        identity = aws_claims_to_identity(_COGNITO_CLAIMS)
        assert identity.identity_id != _COGNITO_CLAIMS["sub"]


class TestMapGroupsToAuthority:
    def test_matched_groups_union_their_action_types(self) -> None:
        mapping = {
            "finance-admins": frozenset({"payment.execute", "payment.refund"}),
            "employees": frozenset({"rai_scan"}),
        }
        authority = map_groups_to_authority(
            ("finance-admins", "employees"), mapping, delegated_by="entra:acme-tenant"
        )
        assert authority is not None
        assert authority.granted_action_types == frozenset(
            {"payment.execute", "payment.refund", "rai_scan"}
        )
        assert authority.delegated_by == "entra:acme-tenant"

    def test_no_matching_group_returns_none_not_full_access(self) -> None:
        mapping = {"finance-admins": frozenset({"payment.execute"})}
        authority = map_groups_to_authority(("unmapped-group",), mapping, delegated_by="okta:acme")
        assert authority is None

    def test_empty_groups_returns_none(self) -> None:
        mapping = {"finance-admins": frozenset({"payment.execute"})}
        authority = map_groups_to_authority((), mapping, delegated_by="okta:acme")
        assert authority is None
