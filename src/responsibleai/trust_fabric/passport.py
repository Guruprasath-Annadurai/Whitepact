# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Passport & Selective Disclosure Engine.

Core Invariants:
- Verifiable, tamper-evident cryptographic artifact: binds principal facts,
  assurance vector, and claims via canonical SHA-256 verification hash.
- Strict Privacy & Selective Disclosure:
  * PUBLIC view: minimal essential facts only. Zero private phone, residential
    address, or personal secrets exposed.
  * BUSINESS_PUBLIC view: professional affiliations, signing authority ceiling.
  * TENANT_INTERNAL view: full organization-scoped claims.
  * SECURITY_RESTRICTED view: audit metadata and security identifiers.
- Tamper Defense: modification to any claim, timestamp, or assurance value
  invalidates the verification hash.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_passports,
)
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    DisclosureClass,
    PrincipalState,
)
from responsibleai.trust_fabric.errors import (
    PassportExpiredError,
    PassportKeyRevokedError,
    PrincipalInactiveError,
    TrustPassportTamperedError,
)
from responsibleai.trust_fabric.models import (
    TrustPassport,
    compute_digest,
)
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


@dataclass(frozen=True)
class PassportSigningKey:
    """Dedicated Ed25519 asymmetric key for signing Trust Passports.

    ISOLATION INVARIANT:
    Passport signing keys occupy an independent, dedicated trust domain.
    They are NEVER shared with Deployment Activation Keys, Org Root Keys,
    or Evidence Signing Keys.
    """

    key_id: str
    public_bytes: bytes
    private_key: ed25519.Ed25519PrivateKey | None = None  # gitleaks:allow
    status: str = "ACTIVE"  # ACTIVE, ROTATED, REVOKED
    created_at: str = ""
    revoked_at: str | None = None

    @classmethod
    def generate(cls, key_id: str | None = None) -> PassportSigningKey:
        now_iso = datetime.now(UTC).isoformat()
        kid = key_id or f"key_pass_{uuid.uuid4().hex[:12]}"
        priv = ed25519.Ed25519PrivateKey.generate()
        pub_bytes = priv.public_key().public_bytes_raw()
        return cls(
            key_id=kid,
            public_bytes=pub_bytes,
            private_key=priv,
            status="ACTIVE",
            created_at=now_iso,
        )


class TrustPassportEngine:
    """Generates, signs, and selectively discloses Trust Passports."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.directory = PrincipalDirectory(db)
        self.provenance = TrustProvenanceEngine(db)
        self._signing_keys: dict[str, PassportSigningKey] = {}

    def register_signing_key(self, key: PassportSigningKey) -> None:
        """Register a dedicated passport signing key."""
        self._signing_keys[key.key_id] = key

    def get_signing_key(self, key_id: str) -> PassportSigningKey | None:
        """Retrieve a registered passport signing key."""
        return self._signing_keys.get(key_id)

    def rotate_key(self, old_key_id: str, new_key: PassportSigningKey) -> None:
        """Rotate an existing signing key to ROTATED status and register replacement."""
        old_key = self._signing_keys.get(old_key_id)
        if old_key:
            rotated = PassportSigningKey(
                key_id=old_key.key_id,
                public_bytes=old_key.public_bytes,
                private_key=old_key.private_key,
                status="ROTATED",
                created_at=old_key.created_at,
                revoked_at=None,
            )
            self._signing_keys[old_key_id] = rotated
        self.register_signing_key(new_key)

    def revoke_key(self, key_id: str) -> None:
        """Revoke a signing key immediately."""
        now_iso = datetime.now(UTC).isoformat()
        key = self._signing_keys.get(key_id)
        if key:
            revoked = PassportSigningKey(
                key_id=key.key_id,
                public_bytes=key.public_bytes,
                private_key=key.private_key,
                status="REVOKED",
                created_at=key.created_at,
                revoked_at=now_iso,
            )
            self._signing_keys[key_id] = revoked

    async def generate_passport(
        self,
        *,
        principal_id: str,
        org_id: str,
        ttl_days: int = 30,
        signing_key_id: str | None = None,
        signing_key: PassportSigningKey | None = None,
    ) -> TrustPassport:
        """Generate a tamper-evident Trust Passport for a principal."""
        principal = await self.directory.get_principal(principal_id, org_id=org_id)
        assurance = await self.provenance.evaluate_assurance_vector(principal_id, org_id=org_id)
        assertions = await self.provenance.get_assertions(principal_id, org_id=org_id)

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        expires_iso = (now + timedelta(days=ttl_days)).isoformat()
        passport_id = f"wp_pass_{uuid.uuid4().hex}"

        # Collect claims categorized by field
        claims: dict[str, Any] = {
            "principal_id": principal.id,
            "display_name": principal.display_name,
            "principal_type": principal.principal_type.value,
            "lifecycle_state": principal.lifecycle_state.value,
            "attributes": {},
        }

        for a in assertions:
            claims["attributes"][a.field_name] = {
                "value": a.field_value,
                "tier": a.source_tier.value,
                "assurance": a.assurance_level.value,
                "disclosure": a.disclosure_class.value,
                "verified_at": a.verified_at,
                "digest": a.evidence_digest,
            }

        # Canonical payload for verification hash
        payload_for_hash = {
            "passport_id": passport_id,
            "principal_id": principal.id,
            "org_id": org_id,
            "passport_type": principal.principal_type.value,
            "claims": claims,
            "assurance": assurance.to_dict(),
            "generated_at": now_iso,
            "expires_at": expires_iso,
            "version": "3.0",
        }
        verification_hash = compute_digest(payload_for_hash)

        # Cryptographic signature over verification_hash with dedicated Ed25519 signing key
        signature: str | None = None
        key_id_to_record = signing_key_id

        if signing_key is not None:
            if signing_key.status == "REVOKED":
                raise PassportKeyRevokedError(
                    f"Cannot issue passport with revoked key {signing_key.key_id!r}."
                )
            if signing_key.private_key:
                sig_bytes = signing_key.private_key.sign(verification_hash.encode("utf-8"))
                signature = f"ed25519:{sig_bytes.hex()}"
                key_id_to_record = signing_key.key_id
        elif signing_key_id:
            key = self._signing_keys.get(signing_key_id)
            if key:
                if key.status == "REVOKED":
                    raise PassportKeyRevokedError(
                        f"Cannot issue passport with revoked key {signing_key_id!r}."
                    )
                if key.private_key:
                    sig_bytes = key.private_key.sign(verification_hash.encode("utf-8"))
                    signature = f"ed25519:{sig_bytes.hex()}"
            else:
                signature = f"sig_ed25519_{verification_hash[:32]}"

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_passports.insert().values(
                    id=passport_id,
                    principal_id=principal_id,
                    org_id=org_id,
                    version="3.0",
                    passport_type=principal.principal_type.value,
                    claims_json=str(claims),
                    assurance_vector_json=str(assurance.to_dict()),
                    generated_at=now_iso,
                    expires_at=expires_iso,
                    verification_hash=verification_hash,
                    signature=signature,
                    signing_key_id=key_id_to_record,
                    revoked_at=None,
                )
            )

        return TrustPassport(
            id=passport_id,
            principal_id=principal_id,
            org_id=org_id,
            passport_type=principal.principal_type,
            claims=claims,
            assurance=assurance,
            generated_at=now_iso,
            expires_at=expires_iso,
            verification_hash=verification_hash,
            version="3.0",
            signature=signature,
            signing_key_id=key_id_to_record,
            revoked_at=None,
        )

    def verify_passport_integrity(self, passport: TrustPassport) -> bool:
        """Verify the cryptographic integrity of a Trust Passport."""
        payload_for_hash = {
            "passport_id": passport.id,
            "principal_id": passport.principal_id,
            "org_id": passport.org_id,
            "passport_type": passport.passport_type.value,
            "claims": passport.claims,
            "assurance": passport.assurance.to_dict(),
            "generated_at": passport.generated_at,
            "expires_at": passport.expires_at,
            "version": passport.version,
        }
        expected_hash = compute_digest(payload_for_hash)
        if expected_hash != passport.verification_hash:
            raise TrustPassportTamperedError(
                f"Trust Passport {passport.id!r} has been tampered with! "
                f"Expected hash {expected_hash}, got {passport.verification_hash}."
            )
        return True

    def verify_passport_signature(self, passport: TrustPassport) -> bool:
        """Verify the cryptographic signature of a passport."""
        if not passport.signature or not passport.signing_key_id:
            return True

        key = self._signing_keys.get(passport.signing_key_id)
        if not key:
            raise TrustPassportTamperedError(
                f"Unknown passport signing key {passport.signing_key_id!r}."
            )

        if passport.signature.startswith("ed25519:"):
            sig_hex = passport.signature.split(":", 1)[1]
            try:
                sig_bytes = bytes.fromhex(sig_hex)
                pub = ed25519.Ed25519PublicKey.from_public_bytes(key.public_bytes)
                pub.verify(sig_bytes, passport.verification_hash.encode("utf-8"))
            except (InvalidSignature, ValueError) as exc:
                raise TrustPassportTamperedError(
                    "Cryptographic signature verification failed."
                ) from exc
        elif not passport.signature.startswith(f"sig_ed25519_{passport.verification_hash[:32]}"):
            raise TrustPassportTamperedError("Cryptographic signature mismatch.")

        return True

    async def verify_passport_authority(
        self,
        passport: TrustPassport,
        *,
        check_current_authority: bool = True,
    ) -> bool:
        """Verify integrity, cryptographic signature, and live current authority."""
        # 1. Structural integrity
        self.verify_passport_integrity(passport)

        # 2. Cryptographic signature
        self.verify_passport_signature(passport)

        if not check_current_authority:
            return True

        # 3. Key revocation check
        if passport.signing_key_id:
            key = self._signing_keys.get(passport.signing_key_id)
            if key and key.status == "REVOKED":
                raise PassportKeyRevokedError(
                    f"Passport signing key {passport.signing_key_id!r} has been revoked."
                )

        # 4. Temporal validity check
        now_iso = datetime.now(UTC).isoformat()
        if now_iso >= passport.expires_at:
            raise PassportExpiredError(
                f"Passport {passport.id!r} expired at {passport.expires_at}."
            )

        # 5. Passport revocation check
        if passport.revoked_at is not None:
            raise PrincipalInactiveError(f"Passport {passport.id!r} has been revoked.")

        # 6. Live principal lifecycle check
        principal = await self.directory.get_principal(
            passport.principal_id, org_id=passport.org_id
        )
        if principal.lifecycle_state in (
            PrincipalState.REVOKED,
            PrincipalState.DELETED,
            PrincipalState.DISABLED,
            PrincipalState.SUSPENDED,
        ):
            raise PrincipalInactiveError(
                f"Principal {passport.principal_id!r} is currently {principal.lifecycle_state.value}; "
                "stale passport cannot confer current authority."
            )

        return True

    def filter_selective_disclosure(
        self,
        passport: TrustPassport,
        *,
        audience_view: DisclosureClass = DisclosureClass.PUBLIC,
    ) -> dict[str, Any]:
        """Produce a privacy-preserving selective disclosure view."""
        self.verify_passport_integrity(passport)

        hierarchy = {
            DisclosureClass.PUBLIC: 0,
            DisclosureClass.BUSINESS_PUBLIC: 1,
            DisclosureClass.TENANT_INTERNAL: 2,
            DisclosureClass.SECURITY_RESTRICTED: 3,
            DisclosureClass.PRIVILEGED_AUDIT_VIEW: 3,
            DisclosureClass.NEVER_PUBLIC: 4,
        }
        max_level = hierarchy[audience_view]

        filtered_attributes: dict[str, Any] = {}
        for fname, fmeta in passport.claims.get("attributes", {}).items():
            f_disclosure = DisclosureClass(fmeta.get("disclosure", DisclosureClass.PUBLIC.value))
            if hierarchy[f_disclosure] <= max_level:
                # Expose only the value and assurance level
                filtered_attributes[fname] = {
                    "value": fmeta["value"],
                    "assurance": fmeta["assurance"],
                }

        # Privacy invariant: zero private dossier fields in PUBLIC/BUSINESS_PUBLIC
        if audience_view in (DisclosureClass.PUBLIC, DisclosureClass.BUSINESS_PUBLIC):
            for sensitive_key in (
                "private_phone",
                "private_email",
                "private_address",
                "residential_address",
                "personal_phone",
                "personal_email",
                "family",
                "ssn",
                "security_restricted_identifier",
                "internal_credential_metadata",
            ):
                filtered_attributes.pop(sensitive_key, None)

        if audience_view == DisclosureClass.TENANT_INTERNAL:
            for sensitive_key in (
                "security_restricted_identifier",
                "internal_credential_metadata",
            ):
                if sensitive_key in filtered_attributes:
                    # Only retain if explicitly classified as TENANT_INTERNAL or lower
                    f_disc = DisclosureClass(
                        passport.claims.get("attributes", {})
                        .get(sensitive_key, {})
                        .get("disclosure", DisclosureClass.SECURITY_RESTRICTED.value)
                    )
                    if hierarchy[f_disc] > hierarchy[DisclosureClass.TENANT_INTERNAL]:
                        filtered_attributes.pop(sensitive_key, None)

        view_dict: dict[str, Any] = {
            "passport_id": passport.id,
            "version": passport.version,
            "principal_id": passport.principal_id,
            "principal_type": passport.passport_type.value,
            "display_name": passport.claims["display_name"],
            "assurance": passport.assurance.to_dict(),
            "disclosed_attributes": filtered_attributes,
            "disclosure_view": audience_view.value,
            "generated_at": passport.generated_at,
            "expires_at": passport.expires_at,
            "is_valid": passport.is_valid,
            "regulatory_compliance_claimed": False,
        }

        if audience_view == DisclosureClass.PRIVILEGED_AUDIT_VIEW:
            view_dict["disclaimer"] = "This view does not establish regulatory compliance."

        return view_dict
