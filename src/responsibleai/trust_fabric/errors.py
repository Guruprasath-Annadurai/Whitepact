# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exception hierarchy for WhitePact Global Trust Fabric & Principal Intelligence."""

from __future__ import annotations


class TrustFabricError(Exception):
    """Base exception for all Trust Fabric domain errors."""


class PrincipalNotFoundError(TrustFabricError):
    """Raised when a requested principal does not exist."""


class PrincipalInactiveError(TrustFabricError):
    """Raised when an action is attempted on an inactive, disabled, or revoked principal."""


class IdentifierCollisionError(TrustFabricError):
    """Raised when an identifier is already claimed by an active principal."""


class IdentifierNotFoundError(TrustFabricError):
    """Raised when a lookup by identifier yields no results."""


class IdentifierResurrectionError(TrustFabricError):
    """Raised when an attempt is made to attach historical authority to a recycled identifier."""


class CrossTenantAccessError(TrustFabricError):
    """Raised when an operation crosses organizational tenant boundaries without federation."""


class OrganizationAlreadyBootstrappedError(TrustFabricError):
    """Raised when attempting to bootstrap an organization that already has a trust root."""


class BootstrapRaceError(TrustFabricError):
    """Raised when multiple concurrent bootstrap attempts race and lost."""


class BootstrapTokenExpiredError(TrustFabricError):
    """Raised when a bootstrap token has expired."""


class BootstrapTokenReplayError(TrustFabricError):
    """Raised when an already consumed bootstrap token is presented."""


class InvalidBootstrapNonceError(TrustFabricError):
    """Raised when a bootstrap nonce is invalid or mismatched."""


class TrustConflictError(TrustFabricError):
    """Raised when material contradictions between sources prevent a definitive decision."""


class TrustChallengeFailedError(TrustFabricError):
    """Raised when an entity fails a trust challenge."""


class TrustChallengeExpiredError(TrustFabricError):
    """Raised when responding to an expired trust challenge."""


class AuthorityExceededError(TrustFabricError):
    """Raised when requested transaction exceeds the principal's delegated authority ceiling."""


class AuthorityExpiredError(TrustFabricError):
    """Raised when an authority grant has passed its validity window."""


class AuthorityRevokedError(TrustFabricError):
    """Raised when an authority grant has been explicitly revoked."""


class TrustPassportTamperedError(TrustFabricError):
    """Raised when a Trust Passport fails cryptographic signature or hash verification."""


class FederatedAssertionInvalidError(TrustFabricError):
    """Raised when a federated assertion signature, audience, or payload is invalid."""


class FederatedAssertionExpiredError(TrustFabricError):
    """Raised when a federated assertion is past its expiration time."""


class FederatedAssertionReplayError(TrustFabricError):
    """Raised when a federated assertion nonce has already been consumed."""


class UnauthorizedBootstrapIssuanceError(TrustFabricError):
    """Raised when an unauthorized entity or platform operator attempts to issue a bootstrap token."""


class PassportKeyRevokedError(TrustFabricError):
    """Raised when a Trust Passport signing key has been revoked."""


class PassportExpiredError(TrustFabricError):
    """Raised when a Trust Passport is presented after its expiration date."""
