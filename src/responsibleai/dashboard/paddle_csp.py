# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Minimum Content-Security-Policy allowances for Paddle Billing v2 overlay checkout.

Authority: Paddle overlay checkout docs and published Paddle.js CSP examples
(https://developer.paddle.com/build/checkout/build-overlay-checkout,
PaddleHQ/paddle-js-wrapper CSP discussions). Hostnames are explicit — no wildcards.
"""

from __future__ import annotations

# Paddle.js loader (@paddle/paddle-js → https://cdn.paddle.com/paddle/v2/paddle.js)
PADDLE_SCRIPT_ORIGINS: tuple[str, ...] = ("https://cdn.paddle.com",)

# Overlay checkout iframe targets (sandbox + production)
PADDLE_FRAME_ORIGINS: tuple[str, ...] = (
    "https://buy.paddle.com",
    "https://sandbox-buy.paddle.com",
)

# Browser-side checkout API calls observed/documented for Paddle Billing v2 overlay
PADDLE_CONNECT_ORIGINS: tuple[str, ...] = (
    "https://sandbox-create-checkout.paddle.com",
    "https://sandbox-checkout-service.paddle.com",
    "https://create-checkout.paddle.com",
    "https://checkout-service.paddle.com",
)

# Checkout overlay styles served from Paddle CDNs
PADDLE_STYLE_ORIGINS: tuple[str, ...] = (
    "https://cdn.paddle.com",
    "https://sandbox-cdn.paddle.com",
)

PADDLE_IMG_ORIGINS: tuple[str, ...] = (
    "https://cdn.paddle.com",
    "https://sandbox-cdn.paddle.com",
)


def _join_directive(name: str, values: tuple[str, ...]) -> str:
    return f"{name} {' '.join(values)}"


def extend_directive(existing: str, directive_name: str, extra_origins: tuple[str, ...]) -> str:
    """Append space-separated origins to a semicolon-delimited CSP directive value."""
    if not extra_origins:
        return existing
    parts = [p.strip() for p in existing.split(";") if p.strip()]
    out: list[str] = []
    merged = False
    for part in parts:
        if part.startswith(directive_name + " "):
            merged = True
            tokens = part.split()
            for origin in extra_origins:
                if origin not in tokens:
                    tokens.append(origin)
            out.append(" ".join(tokens))
        else:
            out.append(part)
    if not merged:
        out.append(_join_directive(directive_name, extra_origins))
    return "; ".join(out)


def whitepact_csp_with_paddle(base_policy: str) -> str:
    """Return WhitePact SPA CSP with minimum Paddle Billing allowances."""
    policy = base_policy
    policy = extend_directive(policy, "script-src", PADDLE_SCRIPT_ORIGINS)
    policy = extend_directive(policy, "connect-src", PADDLE_CONNECT_ORIGINS)
    policy = extend_directive(policy, "frame-src", ("'self'",) + PADDLE_FRAME_ORIGINS)
    policy = extend_directive(policy, "style-src", PADDLE_STYLE_ORIGINS)
    policy = extend_directive(policy, "img-src", PADDLE_IMG_ORIGINS)
    return policy


# Exported for tests (base policy without Paddle).
_WHITEPACT_CONTENT_SECURITY_POLICY_BASE = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data:",
        "font-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    ]
)


def contains_broad_csp_wildcards(policy: str) -> bool:
    lowered = policy.casefold()
    forbidden = (
        "script-src *",
        "connect-src *",
        "frame-src *",
        "default-src *",
        "unsafe-eval",
    )
    return any(token in lowered for token in forbidden)
