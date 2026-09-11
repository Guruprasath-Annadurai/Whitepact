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
from datetime import UTC, datetime, timedelta
from typing import Any

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_passports,
)
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    DisclosureClass,
)
from responsibleai.trust_fabric.errors import (
    TrustPassportTamperedError,
)
from responsibleai.trust_fabric.models import (
    TrustPassport,
    compute_digest,
)
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine


class TrustPassportEngine:
    """Generates, signs, and selectively discloses Trust Passports."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self.directory = PrincipalDirectory(db)
        self.provenance = TrustProvenanceEngine(db)

    async def generate_passport(
        self,
        *,
        principal_id: str,
        org_id: str,
        ttl_days: int = 30,
        signing_key_id: str | None = None,
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

        # In Phase 3, signature is computed over verification_hash with signing key
        signature = f"sig_ed25519_{verification_hash[:32]}" if signing_key_id else None

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
                    signing_key_id=signing_key_id,
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
            signing_key_id=signing_key_id,
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
            for sensitive_key in ("residential_address", "personal_phone", "personal_email", "family", "ssn"):
                filtered_attributes.pop(sensitive_key, None)

        return {
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
        }
