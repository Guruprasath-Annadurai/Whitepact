# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Outbound Egress & Network Boundary Protection."""

from responsibleai.net.egress import (
    AsyncDNSResolver,
    DestinationPolicy,
    DNSResolutionError,
    EgressSecurityError,
    ForbiddenDestinationError,
    InvalidURLError,
    PeerMismatchError,
    SafeAsyncHTTPTransport,
    SafeNetworkBackend,
    SystemDNSResolver,
    create_safe_async_client,
    is_address_allowed,
    normalize_and_validate_url,
    validate_outbound_url,
)

__all__ = [
    "AsyncDNSResolver",
    "DestinationPolicy",
    "DNSResolutionError",
    "EgressSecurityError",
    "ForbiddenDestinationError",
    "InvalidURLError",
    "PeerMismatchError",
    "SafeAsyncHTTPTransport",
    "SafeNetworkBackend",
    "SystemDNSResolver",
    "create_safe_async_client",
    "is_address_allowed",
    "normalize_and_validate_url",
    "validate_outbound_url",
]
