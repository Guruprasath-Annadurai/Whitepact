"""Phase 2 (Enterprise Neural directive) — canonical HMAC signing over
a `KeyProvider`-resolved key. See
`docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 3.11.

**Deliberately not used for webhook payload signing**
(`webhooks/manager.py`) — see
`docs/enterprise-neural/02_PHASE2_STEP4_REPORT.md` for the full
reasoning. Short version: a webhook's HMAC secret is a *two-party*
secret shared with an external receiver (Slack, PagerDuty, a
customer's own endpoint) — both sides must hold the same secret for
verification to work. Rotating it via this codebase's internal
`KeyProvider` without the receiver rotating in lockstep would silently
break every future delivery's signature verification on their end.
This generalization is a correct fit only for signatures WhitePact both
produces and verifies itself, with no external party depending on the
exact secret value — a SAML session token (`auth/saml.py`) is exactly
that; a webhook payload is not.
"""

from __future__ import annotations

import hashlib
import hmac

from responsibleai.governance.crypto.types import KeyId


def sign(dek: bytes, key_id: KeyId, message: bytes) -> str:
    """HMAC-SHA256 sign *message* under *dek*, returning a hex digest.

    *key_id* is bound into the signed material (prefixed, `|`-separated
    from *message*) the same way `envelope.py`'s AEAD associated data
    binds a `KeyId` into ciphertext — a signature produced under one
    purpose/tenant/version can't be replayed as if it came from
    another, even if the same *message* bytes were signed under both.
    """
    material = key_id.to_aad() + b"|" + message
    return hmac.new(dek, material, hashlib.sha256).hexdigest()


def verify(dek: bytes, key_id: KeyId, message: bytes, signature: str) -> bool:
    """Constant-time comparison against `sign()`'s output."""
    expected = sign(dek, key_id, message)
    return hmac.compare_digest(expected, signature)
