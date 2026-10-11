# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Client IP for rate limits.

Direct clients are the socket peer. Forwarding headers are ignored unless
that peer is inside an explicit trusted-proxy CIDR. Cloudflare's
CF-Connecting-IP is read only when the peer is inside the configured
Cloudflare proxy ranges. A Hetzner load balancer in TCP passthrough without
Proxy Protocol is not a trusted client-IP source unless an operator adds
its address on purpose.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping, Sequence

_IGNORED_UNTRUSTED = (
    "x-forwarded-for",
    "x-real-ip",
    "forwarded",
    "cf-connecting-ip",
)


def normalize_ip(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip().strip('"').strip("[]")
    if not text or text.lower() == "unknown":
        return None
    try:
        parsed = ipaddress.ip_address(text)
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        parsed = parsed.ipv4_mapped
    return parsed.compressed


def _networks(cidrs: Sequence[str]) -> list[ipaddress.IPv4Network | ipaddress.IPv6Network]:
    nets: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for raw in cidrs:
        item = raw.strip()
        if not item:
            continue
        try:
            nets.append(ipaddress.ip_network(item, strict=False))
        except ValueError:
            continue
    return nets


def _in_any(
    ip: ipaddress.IPv4Address | ipaddress.IPv6Address,
    nets: Sequence[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    return any(ip in net for net in nets)


def resolve_client_ip(
    *,
    peer: str | None,
    headers: Mapping[str, str],
    trusted_proxy_cidrs: Sequence[str] = (),
    cloudflare_cidrs: Sequence[str] = (),
    legacy_trust_forwarded: bool = False,
) -> str:
    """Return the rate-limit IP.

    ``legacy_trust_forwarded`` is the old environment flag. It does not
    authorize forwarding headers by itself.
    """
    del legacy_trust_forwarded  # intentional: the flag is not a trust boundary
    lowered = {key.lower(): value for key, value in headers.items()}
    peer_text = normalize_ip(peer)
    if peer_text is None:
        return "unknown"
    peer_addr = ipaddress.ip_address(peer_text)
    trusted = _networks(trusted_proxy_cidrs)
    cloudflare = _networks(cloudflare_cidrs)
    peer_is_cf = _in_any(peer_addr, cloudflare)
    peer_is_trusted = peer_is_cf or _in_any(peer_addr, trusted)
    if not peer_is_trusted:
        return peer_text
    if peer_is_cf:
        cf_ip = normalize_ip(lowered.get("cf-connecting-ip"))
        if cf_ip is not None:
            return cf_ip
    forwarded = lowered.get("x-forwarded-for", "")
    parts = [normalize_ip(part) for part in forwarded.split(",")]
    usable = [part for part in parts if part is not None]
    if usable:
        return usable[-1]
    return peer_text


def forwarding_headers_ignored(headers: Mapping[str, str]) -> bool:
    """True when any spoofable forwarding header is present."""
    lowered = {key.lower() for key in headers}
    return any(name in lowered for name in _IGNORED_UNTRUSTED)
