"""WhitePact Community Core — local governance SDK, MCP, and CLI.

Import surface is intentionally narrow and lazy-safe: importing this
package does not pull enterprise dashboard, billing, or hosted SaaS code.
"""

from __future__ import annotations

from whitepact_community.errors import (
    CommunityCapabilityUnavailable,
    ConfigurationError,
    GovernanceDenied,
    WhitePactCommunityError,
)
from whitepact_community.models import (
    ActionRequest,
    AuthorityGrant,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from whitepact_community.sdk import GovernanceClient
from whitepact_community.version import __version__

__all__ = [
    "__version__",
    "ActionRequest",
    "AuthorityGrant",
    "CommunityCapabilityUnavailable",
    "ConfigurationError",
    "DecisionResult",
    "GovernanceClient",
    "GovernanceDecision",
    "GovernanceDenied",
    "IdentityContext",
    "WhitePactCommunityError",
]
