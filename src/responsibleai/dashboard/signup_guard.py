# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Self-serve signup anti-abuse guard.

This deployment has no CAPTCHA provider and no outbound-email provider
configured (see `dashboard/config.py` — no SMTP/SendGrid/Resend/SES
settings exist), so `POST /api/signup` cannot lean on a challenge or an
email-confirmation loop the way a hardened production signup flow
normally would. Everything here is a deterministic, dependency-free
check that raises the bar against low-effort/scripted abuse without
needing an external service or credentials this session doesn't have:

- **Disposable-email blocklist**: a curated, non-exhaustive list of
  well-known throwaway-email domains. A determined abuser can always
  register a fresh disposable domain this list doesn't know about yet —
  this blocks the common, low-effort case, not a complete defense.
- **A global (not just per-IP) signup rate window**: `dashboard/app.py`
  already rate-limits `/api/signup` per source IP via `slowapi`, but
  that alone doesn't bound a low-and-slow attack spread across many
  IPs. `SignupRateWindow` adds a coarse, site-wide cap on top.

**Honestly scoped, same discipline as the rest of this codebase**:
`SignupRateWindow` is in-process, in-memory state — it resets on
restart and does not coordinate across multiple replicas of this
service. That matches this deployment's real, current topology (one
Render web service instance, not a horizontally-scaled fleet). If this
app is ever scaled to multiple replicas, this cap needs to move to the
same Redis-backed limiter `PlanRateLimiter` already uses elsewhere in
`dashboard/app.py`, not stay here.

What this module does **not** do, stated plainly rather than implied:
no CAPTCHA/Turnstile challenge, no email-ownership verification, no MX
record lookup (would need a DNS-resolution dependency and a live
network call this session can't validate against arbitrary domains
reliably), no IP reputation/VPN detection. These are the honest next
hardening steps if abuse becomes a real, observed problem — not
something silently claimed as covered here.
"""

from __future__ import annotations

import time
from collections import deque

# Well-known disposable/throwaway email providers. Not exhaustive by
# design — new disposable domains appear constantly; this catches the
# common, low-effort case (a bot or spammer reaching for the first
# throwaway-email service that comes up in a search), not every one
# that will ever exist.
DISPOSABLE_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "mailinator.com",
        "guerrillamail.com",
        "guerrillamail.info",
        "guerrillamail.biz",
        "guerrillamail.de",
        "guerrillamail.net",
        "guerrillamail.org",
        "grr.la",
        "10minutemail.com",
        "10minutemail.net",
        "tempmail.com",
        "temp-mail.org",
        "throwawaymail.com",
        "yopmail.com",
        "yopmail.net",
        "trashmail.com",
        "getnada.com",
        "fakeinbox.com",
        "sharklasers.com",
        "maildrop.cc",
        "dispostable.com",
        "mintemail.com",
        "mailnesia.com",
        "mohmal.com",
        "moakt.com",
        "spambog.com",
        "mytemp.email",
        "emailondeck.com",
        "33mail.com",
        "discard.email",
        "mailcatch.com",
    }
)


def dwell_time_ok(
    page_loaded_at_ms: int, *, minimum_ms: int = 2000, now_ms: int | None = None
) -> bool:
    """True if at least *minimum_ms* elapsed between the signup page
    rendering and this call. *page_loaded_at_ms* is client-reported and
    trivially spoofable — this is a cheap filter against unsophisticated
    bots that submit a form the instant it loads, not a security
    boundary. *now_ms* is injectable for deterministic testing; defaults
    to the real wall clock."""
    now = now_ms if now_ms is not None else int(time.time() * 1000)
    return (now - page_loaded_at_ms) >= minimum_ms


def is_disposable_email_domain(email: str) -> bool:
    """True if *email*'s domain matches a known throwaway-email
    provider. Case-insensitive; a malformed email with no ``@`` is
    treated as not-disposable (Pydantic's ``EmailStr`` validation
    already rejects malformed addresses before this is ever called)."""
    if "@" not in email:
        return False
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain in DISPOSABLE_EMAIL_DOMAINS


class SignupRateWindow:
    """A single-process, sliding-window cap on total signups across all
    callers, independent of per-source-IP rate limiting. See the module
    docstring for exactly what "single-process" means here and when
    that stops being sufficient.
    """

    def __init__(self, max_per_window: int, window_seconds: float) -> None:
        self._max = max_per_window
        self._window = window_seconds
        self._events: deque[float] = deque()

    def allow(self) -> bool:
        """Records and permits one signup, or returns False if the
        window is already at capacity. Not thread-safe against
        concurrent callers on separate OS threads — fine for this
        single-process asyncio deployment (all calls run on the same
        event loop), same assumption the rest of this in-process
        module makes."""
        now = time.monotonic()
        while self._events and now - self._events[0] > self._window:
            self._events.popleft()
        if len(self._events) >= self._max:
            return False
        self._events.append(now)
        return True
