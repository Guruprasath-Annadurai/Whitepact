# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Step-Up Reauthentication Engine & Nonce Manager."""

from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, insert, or_, select, update

from responsibleai.auth import mfa
from responsibleai.db.engine import (
    DatabaseEngine,
    human_totp_factors,
    iam_sessions,
    iam_step_up_nonces,
    org_api_keys,
    web_sessions,
)
from responsibleai.iam.enums import PrivilegeRiskTier, StepUpMethod
from responsibleai.iam.errors import (
    StepUpRequiredError,
    StepUpVerificationFailedError,
)
from responsibleai.iam.models import StepUpProof

# Step-up methods whose proof this module can really verify. Anything else is refused: a method name
# in a request is not evidence, and no string pattern in a token is a signature check.
SUPPORTED_STEP_UP_METHODS = frozenset({StepUpMethod.MFA_TOTP})

# Failed or repeated code guesses allowed per principal per window (durable, shared across replicas).
TOTP_ATTEMPTS_PER_WINDOW = 8
TOTP_ATTEMPT_WINDOW_SECONDS = 60


def _epoch_now() -> float:
    """Wall clock used to evaluate TOTP codes. A single seam so tests can move time forward."""
    return time.time()


class StepUpVerifier:
    """Issues and verifies single-use action-bound nonces and step-up proofs."""

    def __init__(self, db: DatabaseEngine, *, limiter: Any | None = None) -> None:
        self.db = db
        if limiter is None:
            from responsibleai.enterprise.security.rate_limit import DurableIdentityRateLimiter

            limiter = DurableIdentityRateLimiter(db)
        self.limiter = limiter

    async def issue_step_up_nonce(
        self,
        *,
        org_id: str,
        principal_id: str,
        action: str,
        target_resource_id: str | None = None,
        session_id: str | None = None,
        ttl_seconds: int = 900,
    ) -> str:
        """Issue a cryptographically secure, single-use action-bound nonce."""
        nonce = f"wp_nonce_{secrets.token_urlsafe(32)}"
        nonce_hash = hashlib.sha256(nonce.encode("utf-8")).hexdigest()
        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

        async with self.db.raw.begin() as conn:
            values: dict[str, Any] = {
                "id": f"stn_{uuid.uuid4().hex}",
                "org_id": org_id,
                "principal_id": principal_id,
                "nonce_hash": nonce_hash,
                "action": action,
                "target_resource_id": target_resource_id,
                "created_at": now.isoformat(),
                "expires_at": expires_at,
                "consumed_at": None,
            }
            if "session_id" in iam_step_up_nonces.c:
                values["session_id"] = session_id
            await conn.execute(insert(iam_step_up_nonces).values(**values))

        return nonce

    async def verify_and_consume_step_up(
        self,
        *,
        org_id: str,
        principal_id: str,
        action: str,
        risk_tier: PrivilegeRiskTier,
        proof: StepUpProof | None,
        target_resource_id: str | None = None,
        session_id: str | None = None,
    ) -> bool:
        """Verify the presented proof meets freshness and method requirements, consuming the nonce."""
        if proof is None:
            nonce = await self.issue_step_up_nonce(
                org_id=org_id,
                principal_id=principal_id,
                action=action,
                target_resource_id=target_resource_id,
                session_id=session_id,
            )
            raise StepUpRequiredError(
                f"Action {action} requires step-up reauthentication.",
                required_nonce=nonce,
                max_age_seconds=300 if risk_tier == PrivilegeRiskTier.PRIVILEGED_CRITICAL else 900,
            )

        # 1. Method gate and freshness. A client-supplied auth_time proves nothing, so it is ignored:
        # the proof is a one-time code checked by this server, now, against an enrolled factor, which
        # is as fresh as step-up can be. Unsupported methods are refused before any state is touched.
        if str(proof.method) == "RECOVERY_CEREMONY":
            raise StepUpVerificationFailedError(
                "Recovery ceremony cannot be used for routine admin step-up."
            )
        try:
            method = StepUpMethod(str(proof.method))
        except ValueError:
            method = None
        if method is None or method not in SUPPORTED_STEP_UP_METHODS:
            raise StepUpVerificationFailedError(
                f"Step-up method {proof.method} is not supported: no verifier is implemented "
                "for it, and unverified proofs are never accepted. Use MFA_TOTP."
            )
        now = datetime.now(UTC)

        # Guess limit, before any factor is evaluated (durable, shared by replicas).
        try:
            await self.limiter.check(
                f"stepup-totp:{org_id}:{principal_id}",
                limit=TOTP_ATTEMPTS_PER_WINDOW,
                window_seconds=TOTP_ATTEMPT_WINDOW_SECONDS,
            )
        except Exception as exc:
            raise StepUpVerificationFailedError(
                "Too many step-up attempts. Try again later."
            ) from exc

        # 2. Verify and consume the nonce atomically
        nonce_hash = hashlib.sha256(proof.nonce.encode("utf-8")).hexdigest()

        async with self.db.raw.begin() as conn:
            stmt = select(iam_step_up_nonces).where(
                and_(
                    iam_step_up_nonces.c.org_id == org_id,
                    iam_step_up_nonces.c.principal_id == principal_id,
                    iam_step_up_nonces.c.nonce_hash == nonce_hash,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise StepUpVerificationFailedError(
                    "Step-up nonce not found or tenant/principal mismatch."
                )

            rec = dict(row._mapping)

            # Replay defense
            if rec["consumed_at"] is not None:
                raise StepUpVerificationFailedError("Step-up nonce has already been consumed.")

            # Expiration
            if now.isoformat() >= rec["expires_at"]:
                raise StepUpVerificationFailedError("Step-up nonce has expired.")

            # Freshness is the age of the server-issued challenge (5 min for CRITICAL, 15 min for HIGH),
            # not a client-supplied auth_time.
            max_age_seconds = 300 if risk_tier == PrivilegeRiskTier.PRIVILEGED_CRITICAL else 900
            issued = datetime.fromisoformat(rec["created_at"])
            if issued.tzinfo is None:
                issued = issued.replace(tzinfo=UTC)
            if (now - issued).total_seconds() > max_age_seconds:
                raise StepUpVerificationFailedError(
                    f"Step-up challenge is older than {max_age_seconds}s; request a new one."
                )

            # Action & resource binding
            if rec["action"] != action:
                raise StepUpVerificationFailedError(
                    f"Step-up nonce action mismatch: issued for {rec['action']}, presented for {action}."
                )
            if rec["target_resource_id"] and rec["target_resource_id"] != target_resource_id:
                raise StepUpVerificationFailedError("Step-up nonce target resource mismatch.")

            # Session binding verification
            bound_session = rec.get("session_id")
            if bound_session is not None:
                if session_id is None or session_id != bound_session:
                    raise StepUpVerificationFailedError(
                        f"Step-up nonce session mismatch: issued for session {bound_session}, presented under {session_id}."
                    )

            # Check if session is revoked
            if session_id is not None:
                iam_sess = (
                    await conn.execute(
                        select(
                            iam_sessions.c.status,
                            iam_sessions.c.revoked_at,
                            iam_sessions.c.expires_at,
                        ).where(
                            and_(iam_sessions.c.id == session_id, iam_sessions.c.org_id == org_id)
                        )
                    )
                ).first()
                if iam_sess is not None:
                    if (
                        iam_sess[0] != "ACTIVE"
                        or iam_sess[1] is not None
                        or now.isoformat() >= iam_sess[2]
                    ):
                        raise StepUpVerificationFailedError(
                            "Step-up session has been revoked or expired."
                        )

                web_sess = (
                    await conn.execute(
                        select(web_sessions.c.revoked, web_sessions.c.expires_at).where(
                            web_sessions.c.token_hash == session_id
                        )
                    )
                ).first()
                if web_sess is not None:
                    if web_sess[0] != 0 or now.isoformat() >= web_sess[1]:
                        raise StepUpVerificationFailedError(
                            "Step-up web session has been revoked or expired."
                        )

            # 3. Verify the factor, for real. Browser users have a human TOTP factor
            # (human_totp_factors, enrolled through /mfa/totp/start + /confirm); API-key principals
            # have the key's own enrolled secret. There is no fallback code and no unenrolled path.
            await self._verify_totp_factor(conn, org_id, principal_id, proof.token_or_code)

            # Atomically mark nonce consumed
            await conn.execute(
                update(iam_step_up_nonces)
                .where(iam_step_up_nonces.c.id == rec["id"])
                .values(consumed_at=now.isoformat())
            )

        return True

    async def _verify_totp_factor(
        self, conn: Any, org_id: str, principal_id: str, code: str
    ) -> None:
        """Check *code* against the principal's ACTIVE enrolled TOTP factor and spend its time step.

        The time step is advanced with a compare-and-set, so the same code (or an older one) cannot be
        used twice, including by two concurrent requests.
        """
        now = _epoch_now()
        human = (
            await conn.execute(
                select(human_totp_factors).where(human_totp_factors.c.user_id == principal_id)
            )
        ).first()
        if human is not None:
            if human.status != "ACTIVE" or not human.secret_encrypted:
                raise StepUpVerificationFailedError("Principal has no active enrolled TOTP factor.")
            matched = mfa.verify_code_with_counter(human.secret_encrypted, code, now=now)
            if matched is None:
                raise StepUpVerificationFailedError("Invalid TOTP verification code.")
            spent = await conn.execute(
                update(human_totp_factors)
                .where(
                    human_totp_factors.c.user_id == principal_id,
                    human_totp_factors.c.status == "ACTIVE",
                    or_(
                        human_totp_factors.c.last_timestep.is_(None),
                        human_totp_factors.c.last_timestep < matched,
                    ),
                )
                .values(last_timestep=matched, failed_attempts=0)
            )
            if (spent.rowcount or 0) != 1:
                raise StepUpVerificationFailedError("TOTP code already used.")
            return

        key = (
            await conn.execute(
                select(
                    org_api_keys.c.mfa_secret,
                    org_api_keys.c.mfa_enrolled,
                    org_api_keys.c.mfa_last_timestep,
                ).where(and_(org_api_keys.c.org_id == org_id, org_api_keys.c.id == principal_id))
            )
        ).first()
        if key is None or not key[1] or not key[0]:
            raise StepUpVerificationFailedError("Principal is not enrolled in MFA.")
        matched = mfa.verify_code_with_counter(key[0], code, now=now)
        if matched is None:
            raise StepUpVerificationFailedError("Invalid TOTP verification code.")
        spent = await conn.execute(
            update(org_api_keys)
            .where(
                org_api_keys.c.id == principal_id,
                org_api_keys.c.org_id == org_id,
                org_api_keys.c.mfa_enrolled == 1,
                or_(
                    org_api_keys.c.mfa_last_timestep.is_(None),
                    org_api_keys.c.mfa_last_timestep < matched,
                ),
            )
            .values(mfa_last_timestep=matched)
        )
        if (spent.rowcount or 0) != 1:
            raise StepUpVerificationFailedError("TOTP code already used.")
