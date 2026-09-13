# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM Enumerations & Risk Classifications."""

from __future__ import annotations

from enum import StrEnum


class PrivilegeRiskTier(StrEnum):
    """Privileged operation risk classifications."""

    PRIVILEGED_STANDARD = "PRIVILEGED_STANDARD"
    PRIVILEGED_HIGH = "PRIVILEGED_HIGH"
    PRIVILEGED_CRITICAL = "PRIVILEGED_CRITICAL"


class PrivilegedAction(StrEnum):
    """Enumeration of all recognized privileged control-plane operations."""

    # Standard Administrative Operations
    CREATE_API_KEY = "CREATE_API_KEY"
    UPDATE_BUDGET = "UPDATE_BUDGET"
    READ_AUDIT_LOG = "READ_AUDIT_LOG"
    READ_SCIM_RESOURCES = "READ_SCIM_RESOURCES"

    # High Risk Operations
    ROTATE_API_KEY = "ROTATE_API_KEY"
    REVOKE_API_KEY = "REVOKE_API_KEY"
    ENROLL_MFA = "ENROLL_MFA"
    RESET_MFA = "RESET_MFA"
    UPDATE_MFA_POLICY = "UPDATE_MFA_POLICY"
    UPDATE_AUTHORITY_CEILING = "UPDATE_AUTHORITY_CEILING"
    MODIFY_POLICY_RULE = "MODIFY_POLICY_RULE"
    MODIFY_WORKFLOW_RULE = "MODIFY_WORKFLOW_RULE"
    GRANT_JIT_ACCESS = "GRANT_JIT_ACCESS"
    REVOKE_JIT_ACCESS = "REVOKE_JIT_ACCESS"
    PROVISION_SCIM_USER = "PROVISION_SCIM_USER"
    DEPROVISION_SCIM_USER = "DEPROVISION_SCIM_USER"
    SYNC_SCIM_GROUP = "SYNC_SCIM_GROUP"
    DELEGATE_AUTHORITY = "DELEGATE_AUTHORITY"
    REVOKE_DELEGATION = "REVOKE_DELEGATION"
    REVOKE_PASSPORT = "REVOKE_PASSPORT"

    # Critical Operations (Irreversible, Sovereign Root, Dual-Custody)
    TRANSFER_ROOT_AUTHORITY = "TRANSFER_ROOT_AUTHORITY"
    RECOVER_ROOT_AUTHORITY = "RECOVER_ROOT_AUTHORITY"
    DESTROY_TENANT = "DESTROY_TENANT"
    UPDATE_SSO_IDP_CONFIG = "UPDATE_SSO_IDP_CONFIG"
    EXECUTE_BREAK_GLASS = "EXECUTE_BREAK_GLASS"
    EXECUTE_FOUR_EYES_ACTION = "EXECUTE_FOUR_EYES_ACTION"
    MUTATE_CRITICAL_POLICY = "MUTATE_CRITICAL_POLICY"


# Canonical mapping of privileged actions to risk tiers
ACTION_RISK_TIERS: dict[PrivilegedAction, PrivilegeRiskTier] = {
    PrivilegedAction.CREATE_API_KEY: PrivilegeRiskTier.PRIVILEGED_STANDARD,
    PrivilegedAction.UPDATE_BUDGET: PrivilegeRiskTier.PRIVILEGED_STANDARD,
    PrivilegedAction.READ_AUDIT_LOG: PrivilegeRiskTier.PRIVILEGED_STANDARD,
    PrivilegedAction.READ_SCIM_RESOURCES: PrivilegeRiskTier.PRIVILEGED_STANDARD,

    PrivilegedAction.ROTATE_API_KEY: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.REVOKE_API_KEY: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.ENROLL_MFA: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.RESET_MFA: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.UPDATE_MFA_POLICY: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.UPDATE_AUTHORITY_CEILING: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.MODIFY_POLICY_RULE: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.MODIFY_WORKFLOW_RULE: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.GRANT_JIT_ACCESS: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.REVOKE_JIT_ACCESS: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.PROVISION_SCIM_USER: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.DEPROVISION_SCIM_USER: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.SYNC_SCIM_GROUP: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.DELEGATE_AUTHORITY: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.REVOKE_DELEGATION: PrivilegeRiskTier.PRIVILEGED_HIGH,
    PrivilegedAction.REVOKE_PASSPORT: PrivilegeRiskTier.PRIVILEGED_HIGH,

    PrivilegedAction.TRANSFER_ROOT_AUTHORITY: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.RECOVER_ROOT_AUTHORITY: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.DESTROY_TENANT: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.UPDATE_SSO_IDP_CONFIG: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.EXECUTE_BREAK_GLASS: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.EXECUTE_FOUR_EYES_ACTION: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
    PrivilegedAction.MUTATE_CRITICAL_POLICY: PrivilegeRiskTier.PRIVILEGED_CRITICAL,
}


class StepUpMethod(StrEnum):
    """Supported step-up reauthentication methods."""

    MFA_TOTP = "MFA_TOTP"
    OIDC_AUTH_TIME = "OIDC_AUTH_TIME"
    WEBAUTHN = "WEBAUTHN"


class JitGrantStatus(StrEnum):
    """Lifecycle status of a Just-In-Time access grant."""

    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


class FourEyesStatus(StrEnum):
    """Lifecycle status of a dual-custody authorization request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTED = "EXECUTED"
    EXPIRED = "EXPIRED"


class BreakGlassCapability(StrEnum):
    """Explicitly scoped capabilities permissible under emergency break-glass."""

    RESTORE_IDP_CONFIGURATION = "RESTORE_IDP_CONFIGURATION"
    REVOKE_COMPROMISED_CREDENTIAL = "REVOKE_COMPROMISED_CREDENTIAL"
    RESTORE_OPERATIONAL_POLICY_CONFIGURATION = "RESTORE_OPERATIONAL_POLICY_CONFIGURATION"
    REPAIR_TENANT_SECURITY_EPOCH = "REPAIR_TENANT_SECURITY_EPOCH"
