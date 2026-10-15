# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority & Trust Fabric Bridge errors."""

from __future__ import annotations

from responsibleai.enterprise.errors import EnterpriseError

ROOT_ALREADY_EXISTS = "ROOT_ALREADY_EXISTS"
BOOTSTRAP_TOKEN_INVALID = "BOOTSTRAP_TOKEN_INVALID"
BOOTSTRAP_TOKEN_EXPIRED = "BOOTSTRAP_TOKEN_EXPIRED"
BOOTSTRAP_TOKEN_REPLAY = "BOOTSTRAP_TOKEN_REPLAY"
CONSENT_PARAMETERS_INVALID = "CONSENT_PARAMETERS_INVALID"
UNAUTHORIZED_BOOTSTRAP_CALLER = "UNAUTHORIZED_BOOTSTRAP_CALLER"
ROOT_NOT_FOUND = "ROOT_NOT_FOUND"
AGENT_NOT_FOUND = "AGENT_NOT_FOUND"
AGENT_REGISTRATION_INVALID = "AGENT_REGISTRATION_INVALID"
IDENTITY_ASSURANCE_REQUIRED = "IDENTITY_ASSURANCE_REQUIRED"


def root_already_exists(msg: str = "Organization already has an active Root of Authority.") -> EnterpriseError:
    return EnterpriseError(ROOT_ALREADY_EXISTS, msg, http_status=409)


def bootstrap_invalid(msg: str = "Bootstrap token or nonce is invalid.") -> EnterpriseError:
    return EnterpriseError(BOOTSTRAP_TOKEN_INVALID, msg, http_status=403)


def bootstrap_expired(msg: str = "Bootstrap ceremony has expired.") -> EnterpriseError:
    return EnterpriseError(BOOTSTRAP_TOKEN_EXPIRED, msg, http_status=403)


def bootstrap_replay(msg: str = "Bootstrap token has already been consumed.") -> EnterpriseError:
    return EnterpriseError(BOOTSTRAP_TOKEN_REPLAY, msg, http_status=409)


def consent_invalid(msg: str = "Explicit scoped consent parameters are required and cannot be empty.") -> EnterpriseError:
    return EnterpriseError(CONSENT_PARAMETERS_INVALID, msg, http_status=400)


def unauthorized_caller(msg: str = "Only a verified organization owner can perform root authority bootstrap.") -> EnterpriseError:
    return EnterpriseError(UNAUTHORIZED_BOOTSTRAP_CALLER, msg, http_status=403)


def root_not_found(msg: str = "Active root authority not found.") -> EnterpriseError:
    return EnterpriseError(ROOT_NOT_FOUND, msg, http_status=404)


def agent_not_found(msg: str = "Agent not found.") -> EnterpriseError:
    return EnterpriseError(AGENT_NOT_FOUND, msg, http_status=404)


def assurance_required(msg: str = "Customer identity verification required before establishing root authority.") -> EnterpriseError:
    return EnterpriseError(IDENTITY_ASSURANCE_REQUIRED, msg, http_status=403)


PASSKEY_STEP_UP_REQUIRED = "PASSKEY_STEP_UP_REQUIRED"
WEBAUTHN_ASSERTION_INVALID = "WEBAUTHN_ASSERTION_INVALID"
WEBAUTHN_CHALLENGE_EXPIRED = "WEBAUTHN_CHALLENGE_EXPIRED"
WEBAUTHN_CHALLENGE_REPLAY = "WEBAUTHN_CHALLENGE_REPLAY"
PROOF_OF_POSSESSION_INVALID = "PROOF_OF_POSSESSION_INVALID"
CONTAINMENT_FORBIDDEN = "CONTAINMENT_FORBIDDEN"
CONTAINMENT_INVALID_TARGET = "CONTAINMENT_INVALID_TARGET"
RECOVERY_REQUEST_NOT_FOUND = "RECOVERY_REQUEST_NOT_FOUND"
QUORUM_NOT_MET = "QUORUM_NOT_MET"
SELF_APPROVAL_BLOCKED = "SELF_APPROVAL_BLOCKED"
ALREADY_VOTED = "ALREADY_VOTED"
RECOVERY_EXPIRED = "RECOVERY_EXPIRED"
RECOVERY_ALREADY_EXECUTED = "RECOVERY_ALREADY_EXECUTED"
RECOVERY_DIGEST_MISMATCH = "RECOVERY_DIGEST_MISMATCH"


def passkey_step_up_required(msg: str = "Phishing-resistant passkey step-up required.") -> EnterpriseError:
    return EnterpriseError(PASSKEY_STEP_UP_REQUIRED, msg, http_status=403)


def webauthn_assertion_invalid(msg: str = "WebAuthn assertion is invalid.") -> EnterpriseError:
    return EnterpriseError(WEBAUTHN_ASSERTION_INVALID, msg, http_status=403)


def webauthn_challenge_expired(msg: str = "WebAuthn challenge has expired.") -> EnterpriseError:
    return EnterpriseError(WEBAUTHN_CHALLENGE_EXPIRED, msg, http_status=403)


def webauthn_challenge_replay(msg: str = "WebAuthn challenge has already been consumed.") -> EnterpriseError:
    return EnterpriseError(WEBAUTHN_CHALLENGE_REPLAY, msg, http_status=409)


def proof_of_possession_invalid(msg: str = "Proof of possession signature is invalid.") -> EnterpriseError:
    return EnterpriseError(PROOF_OF_POSSESSION_INVALID, msg, http_status=403)


def containment_forbidden(msg: str = "Emergency containment operation not permitted.") -> EnterpriseError:
    return EnterpriseError(CONTAINMENT_FORBIDDEN, msg, http_status=403)


def containment_invalid_target(msg: str = "Invalid containment target.") -> EnterpriseError:
    return EnterpriseError(CONTAINMENT_INVALID_TARGET, msg, http_status=400)


def recovery_request_not_found(msg: str = "Recovery request not found.") -> EnterpriseError:
    return EnterpriseError(RECOVERY_REQUEST_NOT_FOUND, msg, http_status=404)


def quorum_not_met(msg: str = "Required recovery quorum has not been satisfied.") -> EnterpriseError:
    return EnterpriseError(QUORUM_NOT_MET, msg, http_status=409)


def self_approval_blocked(msg: str = "Requester cannot vote to approve their own recovery request.") -> EnterpriseError:
    return EnterpriseError(SELF_APPROVAL_BLOCKED, msg, http_status=403)


def already_voted(msg: str = "Administrator has already cast a vote on this recovery request.") -> EnterpriseError:
    return EnterpriseError(ALREADY_VOTED, msg, http_status=409)


def recovery_expired(msg: str = "Recovery request has expired.") -> EnterpriseError:
    return EnterpriseError(RECOVERY_EXPIRED, msg, http_status=403)


def recovery_already_executed(msg: str = "Recovery request has already been executed.") -> EnterpriseError:
    return EnterpriseError(RECOVERY_ALREADY_EXECUTED, msg, http_status=409)


def recovery_digest_mismatch(msg: str = "Action digest does not match the proposed recovery parameters.") -> EnterpriseError:
    return EnterpriseError(RECOVERY_DIGEST_MISMATCH, msg, http_status=400)

