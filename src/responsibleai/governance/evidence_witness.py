# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline-verifiable evidence head witness.

The database hash chain detects an edit that leaves a stored hash
inconsistent with its neighbors. It does not detect an attacker who
rewrites the rows and recomputes every hash. This module is the
smallest check that does: a signature over the chain head, made by a
key that is not stored in the evidence database.

``governance.evidence_publication`` can append a signed head to a
directory outside the database and can build an object-lock PUT.
``LIVE_ANCHOR_STATUS`` stays ``EXTERNAL_BLOCKER``. A local directory is
not a separate administrative domain, and object-store configuration is
not a live witness until an auditor reads a retention-locked object.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

LIVE_ANCHOR_STATUS = "EXTERNAL_BLOCKER"
_WITNESS_VERSION = 1


class EvidenceWitnessError(ValueError):
    """The witness does not match the claimed chain head or key."""


@dataclass(frozen=True)
class EvidenceHeadWitness:
    organization_id: str
    chain_sequence: int
    head_hash: str
    witnessed_at: str
    public_key_hex: str
    signature_hex: str

    def to_dict(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "chain_sequence": self.chain_sequence,
            "head_hash": self.head_hash,
            "witnessed_at": self.witnessed_at,
            "public_key_hex": self.public_key_hex,
            "signature_hex": self.signature_hex,
            "live_anchor_status": LIVE_ANCHOR_STATUS,
        }


def canonical_witness_bytes(
    *,
    organization_id: str,
    chain_sequence: int,
    head_hash: str,
    witnessed_at: str,
) -> bytes:
    payload = {
        "v": _WITNESS_VERSION,
        "organization_id": organization_id,
        "chain_sequence": chain_sequence,
        "head_hash": head_hash,
        "witnessed_at": witnessed_at,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_evidence_head(
    private_key: Ed25519PrivateKey,
    *,
    organization_id: str,
    chain_sequence: int,
    head_hash: str,
    witnessed_at: str,
) -> EvidenceHeadWitness:
    message = canonical_witness_bytes(
        organization_id=organization_id,
        chain_sequence=chain_sequence,
        head_hash=head_hash,
        witnessed_at=witnessed_at,
    )
    public = private_key.public_key().public_bytes_raw()
    signature = private_key.sign(message)
    return EvidenceHeadWitness(
        organization_id=organization_id,
        chain_sequence=chain_sequence,
        head_hash=head_hash,
        witnessed_at=witnessed_at,
        public_key_hex=public.hex(),
        signature_hex=signature.hex(),
    )


def verify_evidence_head(
    witness: EvidenceHeadWitness,
    *,
    organization_id: str,
    chain_sequence: int,
    head_hash: str,
) -> bool:
    """Return True only when the witness binds this exact head.

    Raises ``EvidenceWitnessError`` when the signature, organization,
    sequence, or head hash does not match. A database rewrite that
    produces a new head hash cannot satisfy a witness signed over the
    previous head unless the attacker also holds the witness key.
    """
    if witness.organization_id != organization_id:
        raise EvidenceWitnessError("witness organization does not match")
    if witness.chain_sequence != chain_sequence:
        raise EvidenceWitnessError("witness sequence does not match")
    if witness.head_hash != head_hash:
        raise EvidenceWitnessError("witness head hash does not match")
    message = canonical_witness_bytes(
        organization_id=witness.organization_id,
        chain_sequence=witness.chain_sequence,
        head_hash=witness.head_hash,
        witnessed_at=witness.witnessed_at,
    )
    try:
        public = Ed25519PublicKey.from_public_bytes(bytes.fromhex(witness.public_key_hex))
        public.verify(bytes.fromhex(witness.signature_hex), message)
    except (ValueError, InvalidSignature) as exc:
        raise EvidenceWitnessError("witness signature is not valid") from exc
    return True
