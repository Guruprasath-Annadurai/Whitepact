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
