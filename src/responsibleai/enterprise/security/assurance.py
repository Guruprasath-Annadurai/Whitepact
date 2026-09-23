# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence-based authentication assurance.

Organization policy cannot declare SSO phishing-resistant. Only signed
provider evidence (amr/acr/AuthnContext) or a verified WebAuthn UV ceremony
can raise assurance. Unknown evidence maps to the lower safe level.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from responsibleai.enterprise.security.policy import ASSURANCE_RANK, AuthMethod

PASSWORD = "PASSWORD"
PASSWORD_PLUS_TOTP = "PASSWORD_PLUS_TOTP"
PASSKEY_UV = "PASSKEY_UV"
HARDWARE_BOUND_PASSKEY = "HARDWARE_BOUND_PASSKEY"
ENTERPRISE_SSO_STANDARD = "ENTERPRISE_SSO_STANDARD"
ENTERPRISE_SSO_PHISHING_RESISTANT = "ENTERPRISE_SSO_PHISHING_RESISTANT"
GOOGLE_OIDC = "GOOGLE_OIDC"
MICROSOFT_OIDC = "MICROSOFT_OIDC"
RECOVERY = "RECOVERY"

# Reviewed phishing-resistant AMR values from signed ID tokens / assertions.
# Generic ``mfa`` / ``otp`` / ``pwd`` / ``wia`` are intentionally absent.
PHISHING_RESISTANT_AMR = frozenset({"hwk", "pop", "sc", "fpt"})

PHISHING_RESISTANT_ACR = frozenset(
    {
        "urn:oasis:names:tc:SAML:2.0:ac:classes:SmartcardPKI",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:Smartcard",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:X509",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:HardwareToken",
        "http://schemas.microsoft.com/claims/authnmethodsreferences/x509",
        "http://schemas.microsoft.com/ws/2008/06/identity/authenticationmethod/smartcard",
        "urn:microsoft:authentication:method:hardwareprotected",
    }
)

# Explicitly NOT phishing-resistant even if an org checkbox says otherwise.
NON_PHISHING_RESISTANT_ACR = frozenset(
    {
        "urn:oasis:names:tc:SAML:2.0:ac:classes:Password",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:PasswordProtectedTransport",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:InternetProtocol",
        "urn:oasis:names:tc:SAML:2.0:ac:classes:unspecified",
        "http://schemas.microsoft.com/claims/multipleauthn",
        "https://refeds.org/profile/mfa",
        "https://refeds.org/profile/sfa",
    }
)


@dataclass(frozen=True)
class AssuranceDecision:
    level: str
    phishing_resistant: bool
    evidence: str


def _norm_list(values: Iterable[Any] | None) -> tuple[str, ...]:
    if not values:
        return ()
    out: list[str] = []
    for item in values:
        text = str(item).strip()
        if text:
            out.append(text)
    return tuple(out)


def map_authentication_assurance(
    *,
    methods: tuple[str, ...],
    amr: Iterable[str] | None = None,
    acr: str | None = None,
    authn_context: str | None = None,
    webauthn_uv: bool | None = None,
    webauthn_backup_eligible: bool | None = None,
    org_policy_claims_phishing_resistant: bool = False,
) -> AssuranceDecision:
    """Derive assurance from ceremony evidence. Org policy is ignored."""
    del org_policy_claims_phishing_resistant  # never authoritative
    method_set = {str(m) for m in methods}
    amr_n = tuple(v.casefold() for v in _norm_list(amr))
    acr_n = (acr or "").strip()
    ctx_n = (authn_context or "").strip() or acr_n

    if AuthMethod.PASSKEY_UV in method_set or webauthn_uv is True:
        if webauthn_uv is False:
            return AssuranceDecision(PASSWORD, False, "webauthn_missing_uv")
        if webauthn_backup_eligible is False and webauthn_uv:
            return AssuranceDecision(
                HARDWARE_BOUND_PASSKEY, True, "webauthn_uv_not_backup_eligible"
            )
        return AssuranceDecision(PASSKEY_UV, True, "webauthn_uv")

    if AuthMethod.ENTERPRISE_SSO in method_set:
        if ctx_n in NON_PHISHING_RESISTANT_ACR or acr_n in NON_PHISHING_RESISTANT_ACR:
            return AssuranceDecision(
                ENTERPRISE_SSO_STANDARD, False, "idp_acr_not_phishing_resistant"
            )
        amr_hit = any(item in PHISHING_RESISTANT_AMR for item in amr_n)
        acr_hit = ctx_n in PHISHING_RESISTANT_ACR or acr_n in PHISHING_RESISTANT_ACR
        if amr_hit or acr_hit:
            return AssuranceDecision(
                ENTERPRISE_SSO_PHISHING_RESISTANT, True, "signed_idp_phishing_resistant_evidence"
            )
        return AssuranceDecision(
            ENTERPRISE_SSO_STANDARD, False, "enterprise_sso_without_reviewed_evidence"
        )

    if AuthMethod.TOTP in method_set:
        return AssuranceDecision(PASSWORD_PLUS_TOTP, False, "totp")
    if AuthMethod.GOOGLE_OIDC in method_set:
        return AssuranceDecision(GOOGLE_OIDC, False, "google_oidc")
    if AuthMethod.MICROSOFT_OIDC in method_set:
        return AssuranceDecision(MICROSOFT_OIDC, False, "microsoft_oidc")
    if AuthMethod.RECOVERY in method_set:
        return AssuranceDecision(RECOVERY, False, "recovery")
    if AuthMethod.PASSWORD in method_set:
        return AssuranceDecision(PASSWORD, False, "password")
    best = "NONE"
    best_rank = 0
    for method in methods:
        rank = ASSURANCE_RANK.get(method, 0)
        if rank > best_rank:
            best_rank = rank
            best = method
    return AssuranceDecision(best, False, "unknown_lower_safe")


# Session storage uses the historical ASSURANCE_RANK keys. Map evidence levels
# onto those ranks without inflating phishing-resistance.
SESSION_LEVEL = {
    PASSWORD: "PASSWORD",
    PASSWORD_PLUS_TOTP: "TOTP",
    PASSKEY_UV: "PASSKEY_UV",
    HARDWARE_BOUND_PASSKEY: "PASSKEY_UV",
    ENTERPRISE_SSO_STANDARD: "ENTERPRISE_SSO",
    ENTERPRISE_SSO_PHISHING_RESISTANT: "ENTERPRISE_SSO",
    GOOGLE_OIDC: "GOOGLE_OIDC",
    MICROSOFT_OIDC: "MICROSOFT_OIDC",
    RECOVERY: "RECOVERY",
}
