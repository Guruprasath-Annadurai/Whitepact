# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Central authentication/security policy. Endpoints consume this; they do not duplicate it.

AUTHENTICATED != IDENTITY_VERIFIED
MFA_COMPLETE != IDENTITY_VERIFIED
GOOGLE_LOGIN != COMPANY_VERIFIED
SSO_SUCCESS != API_KEY_ELIGIBLE
OWNER != EXECUTION_AUTHORIZED
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class AuthMethod(StrEnum):
    PASSWORD = "PASSWORD"
    TOTP = "TOTP"
    PASSKEY_UV = "PASSKEY_UV"
    GOOGLE_OIDC = "GOOGLE_OIDC"
    MICROSOFT_OIDC = "MICROSOFT_OIDC"
    ENTERPRISE_SSO = "ENTERPRISE_SSO"
    RECOVERY = "RECOVERY"
    PHONE = "PHONE"


class SensitiveAction(StrEnum):
    CREATE_PRODUCTION_API_KEY = "CREATE_PRODUCTION_API_KEY"
    ROTATE_PRIVILEGED_API_KEY = "ROTATE_PRIVILEGED_API_KEY"
    CREATE_SERVICE_ACCOUNT = "CREATE_SERVICE_ACCOUNT"
    CHANGE_SERVICE_ACCOUNT_PRIVILEGES = "CHANGE_SERVICE_ACCOUNT_PRIVILEGES"
    TRANSFER_OWNERSHIP = "TRANSFER_OWNERSHIP"
    PROMOTE_OWNER = "PROMOTE_OWNER"
    PROMOTE_SECURITY_ADMIN = "PROMOTE_SECURITY_ADMIN"
    REMOVE_LAST_STRONG_AUTH = "REMOVE_LAST_STRONG_AUTH"
    DISABLE_MFA = "DISABLE_MFA"
    ADD_PASSKEY = "ADD_PASSKEY"
    REMOVE_PASSKEY = "REMOVE_PASSKEY"
    LINK_GOOGLE = "LINK_GOOGLE"
    LINK_MICROSOFT = "LINK_MICROSOFT"
    CONFIGURE_SSO = "CONFIGURE_SSO"
    DISABLE_REQUIRED_SSO = "DISABLE_REQUIRED_SSO"
    CHANGE_COMPANY_DOMAIN = "CHANGE_COMPANY_DOMAIN"
    CHANGE_ENTRA_BINDING = "CHANGE_ENTRA_BINDING"
    CHANGE_GOOGLE_WORKSPACE_BINDING = "CHANGE_GOOGLE_WORKSPACE_BINDING"
    HIGH_RISK_RECOVERY = "HIGH_RISK_RECOVERY"
    REVOKE_ALL_SESSIONS = "REVOKE_ALL_SESSIONS"
    CHANGE_RECOVERY_METHODS = "CHANGE_RECOVERY_METHODS"
    EMERGENCY_SECURITY_SETTINGS = "EMERGENCY_SECURITY_SETTINGS"


PHISHING_RESISTANT = frozenset({AuthMethod.PASSKEY_UV, AuthMethod.ENTERPRISE_SSO})
STRONG_BUT_PHISHABLE = frozenset({AuthMethod.TOTP})
NOT_STRONG = frozenset({AuthMethod.PASSWORD, AuthMethod.PHONE, AuthMethod.RECOVERY, AuthMethod.GOOGLE_OIDC, AuthMethod.MICROSOFT_OIDC})

# Provider OIDC is not automatically phishing-resistant.
ASSURANCE_RANK = {
    "NONE": 0,
    "PASSWORD": 10,
    "RECOVERY": 15,
    "GOOGLE_OIDC": 20,
    "MICROSOFT_OIDC": 20,
    "TOTP": 40,
    "ENTERPRISE_SSO": 70,
    "PASSKEY_UV": 90,
}


@dataclass(frozen=True)
class SessionAssurance:
    level: str
    methods: tuple[str, ...]
    auth_time: str
    phishing_resistant: bool
    session_id: str
    user_id: str
    org_id: str | None = None
    step_up_expires_at: str | None = None

    def rank(self) -> int:
        return ASSURANCE_RANK.get(self.level, 0)


@dataclass(frozen=True)
class OrgAuthPolicy:
    phishing_resistant_required: bool = False
    privileged_roles: tuple[str, ...] = ("OWNER", "SECURITY_ADMIN")
    sso_enforcement: str = "SSO_OPTIONAL"
    dual_control_actions: tuple[str, ...] = ()
    break_glass_user_id: str | None = None
    sso_provisioning: str = "INVITE_ONLY"


@dataclass
class PolicyDecision:
    allowed: bool
    code: str
    required_assurance: str = "PASSWORD"
    require_step_up: bool = False
    phishing_resistant_required: bool = False
    metadata: dict[str, str] = field(default_factory=dict)


class AuthenticationSecurityPolicy:
    """Answers required factor, assurance, step-up, SSO, recovery, and downgrade questions."""

    def required_assurance_for(self, action: SensitiveAction | str, *, role: str | None, org: OrgAuthPolicy) -> str:
        action_s = str(action)
        if org.phishing_resistant_required and role in org.privileged_roles:
            return "PASSKEY_UV"
        critical = {
            SensitiveAction.TRANSFER_OWNERSHIP,
            SensitiveAction.PROMOTE_OWNER,
            SensitiveAction.PROMOTE_SECURITY_ADMIN,
            SensitiveAction.DISABLE_REQUIRED_SSO,
            SensitiveAction.CHANGE_COMPANY_DOMAIN,
            SensitiveAction.CHANGE_ENTRA_BINDING,
            SensitiveAction.CHANGE_GOOGLE_WORKSPACE_BINDING,
            SensitiveAction.REMOVE_LAST_STRONG_AUTH,
            SensitiveAction.DISABLE_MFA,
            SensitiveAction.HIGH_RISK_RECOVERY,
            SensitiveAction.EMERGENCY_SECURITY_SETTINGS,
            SensitiveAction.CONFIGURE_SSO,
        }
        if action_s in {a.value for a in critical} or action in critical:
            return "PASSKEY_UV" if org.phishing_resistant_required else "TOTP"
        return "TOTP"

    def evaluate_login(
        self,
        *,
        methods: tuple[str, ...],
        role: str | None,
        org: OrgAuthPolicy,
        break_glass: bool = False,
    ) -> PolicyDecision:
        if org.sso_enforcement == "SSO_REQUIRED" and AuthMethod.ENTERPRISE_SSO not in methods:
            if break_glass and AuthMethod.PASSKEY_UV in methods:
                return PolicyDecision(True, "BREAK_GLASS_SSO", required_assurance="PASSKEY_UV")
            return PolicyDecision(False, "SSO_REQUIRED", required_assurance="ENTERPRISE_SSO")
        if org.phishing_resistant_required and role in org.privileged_roles:
            if AuthMethod.PASSKEY_UV not in methods and AuthMethod.ENTERPRISE_SSO not in methods:
                return PolicyDecision(
                    False,
                    "PASSKEY_REQUIRED",
                    required_assurance="PASSKEY_UV",
                    phishing_resistant_required=True,
                )
        if AuthMethod.PHONE in methods and set(methods) <= {AuthMethod.PHONE, AuthMethod.PASSWORD}:
            return PolicyDecision(False, "PHONE_VERIFIED_NOT_STRONG", required_assurance="TOTP")
        return PolicyDecision(True, "OK", required_assurance=self._login_level(methods))

    def evaluate_step_up(
        self,
        *,
        action: SensitiveAction | str,
        session: SessionAssurance,
        role: str | None,
        org: OrgAuthPolicy,
    ) -> PolicyDecision:
        required = self.required_assurance_for(action, role=role, org=org)
        if session.rank() < ASSURANCE_RANK.get(required, 0):
            return PolicyDecision(
                False,
                "AUTHENTICATION_ASSURANCE_TOO_LOW",
                required_assurance=required,
                require_step_up=True,
                phishing_resistant_required=required == "PASSKEY_UV",
            )
        return PolicyDecision(True, "OK", required_assurance=required, require_step_up=True)

    def evaluate_downgrade(
        self,
        *,
        action: str,
        remaining_strong_factors: int,
        session: SessionAssurance,
        org: OrgAuthPolicy,
    ) -> PolicyDecision:
        if action in {"DISABLE_REQUIRED_SSO", "REMOVE_LAST_STRONG_AUTH", "DISABLE_MFA"}:
            if remaining_strong_factors <= 0 or session.rank() < ASSURANCE_RANK["TOTP"]:
                return PolicyDecision(False, "SECURITY_DOWNGRADE_BLOCKED", require_step_up=True)
            if org.phishing_resistant_required and not session.phishing_resistant:
                return PolicyDecision(False, "SECURITY_DOWNGRADE_BLOCKED", phishing_resistant_required=True)
        return PolicyDecision(True, "OK")

    def provider_is_phishing_resistant(self, method: str, *, sso_satisfies_org_policy: bool = False) -> bool:
        if method == AuthMethod.PASSKEY_UV:
            return True
        if method == AuthMethod.ENTERPRISE_SSO:
            return sso_satisfies_org_policy
        return False

    @staticmethod
    def _login_level(methods: tuple[str, ...]) -> str:
        best = "PASSWORD"
        best_rank = 0
        for method in methods:
            rank = ASSURANCE_RANK.get(method, 0)
            if rank > best_rank:
                best_rank = rank
                best = method
        return best
