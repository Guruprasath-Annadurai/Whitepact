"""External Audit Anchor (Security Remediation Gap 5, Phase 1) --
closes the gap `tests/test_evidence_chain_anchoring.py` (Enterprise
Neural Phase 13) already proved by construction: an attacker with full
database write access can tamper a `governance_evidence` row and
regenerate the hash chain forward from that point, and
`EvidenceRepository.verify_chain()` -- which only re-walks rows already
sitting in the same compromised database -- reports it as intact
regardless. Phase 13 built the artifact an external anchor would need
(`EvidenceBundle.bundle_digest`, `governance/evidence_bundle.py`) but
explicitly did not build the anchor itself
(`docs/enterprise-neural/13_PHASE13_DESIGN.md`). This module is that
anchor: **Event -> Canonical Serialization -> Hash [already built,
`evidence_bundle.py`] -> Signature -> Publication -> External
Destination -> Verification**.

**Signature**: HMAC-SHA256 over the bundle digest, via the existing
`governance/crypto/signing.py` primitive under a dedicated
`KeyPurpose.AUDIT_ANCHOR` key -- that enum member has existed since
Enterprise Neural Phase 2 (`governance/crypto/types.py`) but was never
referenced anywhere until this module. HMAC, not an asymmetric
signature: per `signing.py`'s own docstring, this is the correct
primitive for something WhitePact both produces and verifies itself
with no external party depending on the exact key -- the same
reasoning that already justified reusing it for SAML session tokens.
Honestly scoped: this proves the anchored digest hasn't been forged or
altered *after* anchoring by anyone without the `AUDIT_ANCHOR` key; it
does not provide non-repudiation toward a third party the way an
asymmetric signature with a published public key would. A future
`AUDIT_ANCHOR`-purpose asymmetric signing scheme is a real, separate
upgrade this module's `AnchorRecord.signature`/`key_id` fields leave
room for without a format change (both are already opaque strings).

**Destination**: `AuditAnchorProvider` (Protocol, TCB-minimized like
`RootResolver`/`KeyProvider` -- no crypto or DB coupling baked in) is
the extension seam; `LocalFileAnchorProvider` is the one real,
production-*capable* implementation this phase ships, using
create-exclusive file writes (`os.O_CREAT | os.O_EXCL`) so a published
anchor file can never be silently overwritten by a second publish
under the same id -- the honest analogue a local filesystem can
actually provide, **not** real hardware WORM/S3 Object Lock/RFC 3161
timestamping. Naming it "LocalFileAnchorProvider" rather than
"WORMAnchorProvider" is deliberate, matching this codebase's own
`LocalEnvelopeKeyProvider` precedent (Gap 1): one correct, testable,
production-capable seam, not a fabricated capability. A future
`S3ObjectLockAnchorProvider`/`Rfc3161TimestampAnchorProvider` implements
the same Protocol without any call site changing.

**What this phase does not do**, named honestly (see
`docs/enterprise-neural/REMEDIATION_GAP5_AUDIT_ANCHOR.md` for the full
accounting): does not fix multi-instance evidence-chain sequencing
safety (`db/evidence_repository.py`'s per-process `asyncio.Lock` is
unchanged); does not strengthen the underlying per-entry hash's
pipe-joined canonicalization; does not wire periodic/scheduled
publication into any live request path -- `publish_anchor()` is a
callable a scheduler/admin action can invoke, not itself a background
job.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from responsibleai.governance.crypto.signing import sign, verify
from responsibleai.governance.crypto.types import KeyId

if TYPE_CHECKING:
    from responsibleai.governance.crypto.provider import KeyProvider
    from responsibleai.governance.evidence_bundle import EvidenceBundle


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline `constitution.py`/`root_authority.py`/
    `consent_proof.py` already use."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class AnchorRecord:
    """A signed, (once published) externally-stored claim: "as of
    `anchored_at`, org `org_id`'s evidence bundle `bundle_id` had
    digest `bundle_digest`." Nothing here is a new hash-chain entry --
    it is a periodic checkpoint over the *existing* chain, exactly the
    "Global Sequence -> Primary Evidence Store -> External Periodic
    Anchor" legs the remediation directive names, evaluated against an
    already-built primary store rather than replacing it."""

    anchor_id: str
    org_id: str | None
    bundle_id: str
    bundle_digest: str
    record_count: int
    key_id: str  # KeyId.to_string() -- identifies, never contains, key material
    signature: str  # hex HMAC-SHA256 digest, sign()'s output
    anchored_at: datetime
    destination_ref: str | None = None  # set once publish_anchor() succeeds

    def to_dict(self) -> dict[str, Any]:
        return {
            "anchor_id": self.anchor_id,
            "org_id": self.org_id,
            "bundle_id": self.bundle_id,
            "bundle_digest": self.bundle_digest,
            "record_count": self.record_count,
            "key_id": self.key_id,
            "signature": self.signature,
            "anchored_at": self.anchored_at.isoformat(),
            "destination_ref": self.destination_ref,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnchorRecord:
        return cls(
            anchor_id=data["anchor_id"],
            org_id=data.get("org_id"),
            bundle_id=data["bundle_id"],
            bundle_digest=data["bundle_digest"],
            record_count=data["record_count"],
            key_id=data["key_id"],
            signature=data["signature"],
            anchored_at=datetime.fromisoformat(data["anchored_at"]),
            destination_ref=data.get("destination_ref"),
        )


class AnchorAlreadyPublishedError(Exception):
    """Raised by an `AuditAnchorProvider` when `publish()` is called
    twice for the same `anchor_id` -- the append-only guarantee working
    as designed, never silently overwriting a prior publication."""

    def __init__(self, anchor_id: str) -> None:
        self.anchor_id = anchor_id
        super().__init__(f"Anchor {anchor_id!r} has already been published")


class AuditAnchorProvider(Protocol):
    """The external-destination seam. Deliberately minimal -- two
    methods, no crypto/DB dependency baked in -- so this stays testable
    with a plain local implementation and usable against a real
    S3-Object-Lock/RFC-3161/notary backend without this module changing
    at all."""

    async def publish(self, anchor_id: str, payload: bytes) -> str:
        """Publish *payload* under *anchor_id*, returning an opaque
        `destination_ref` a later `fetch()` can use to retrieve it.
        Must raise `AnchorAlreadyPublishedError` if `anchor_id` was
        already published -- append-only, never a silent overwrite."""
        ...

    async def fetch(self, destination_ref: str) -> bytes:
        """Retrieve a previously published payload. Raises
        `FileNotFoundError` (or the provider's own analogous error) if
        `destination_ref` doesn't resolve to anything -- never returns
        `None`/empty silently, since a missing anchor is itself
        security-relevant (it could mean deletion, not just absence)."""
        ...


class LocalFileAnchorProvider:
    """The one real, production-*capable* `AuditAnchorProvider` this
    phase ships -- see module docstring for exactly what "capable"
    does and doesn't mean here (create-exclusive local files, not
    hardware WORM). `directory` should be a path outside the
    application's own writable deploy artifact, ideally on
    write-once-configured storage (a cloud-mounted volume with
    versioning/retention enabled) for this to carry real weight in
    production -- this class enforces only the one property a plain
    local filesystem actually can: an existing anchor file can never be
    silently overwritten by a second `publish()` call."""

    def __init__(self, directory: str | Path) -> None:
        self._directory = Path(directory)
        self._directory.mkdir(parents=True, exist_ok=True)

    def _path_for(self, anchor_id: str) -> Path:
        return self._directory / f"{anchor_id}.anchor.json"

    async def publish(self, anchor_id: str, payload: bytes) -> str:
        path = self._path_for(anchor_id)
        try:
            # 0o400: owner read-only, no group/other access -- an
            # anchor file carries org_id/bundle_id/signature (not key
            # material), but still has no reason to be world-readable.
            # The already-open fd retains write access from O_WRONLY
            # regardless of this mode (permission bits govern future
            # opens, not the current one), so the write below still
            # succeeds.
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
        except FileExistsError as exc:
            raise AnchorAlreadyPublishedError(anchor_id) from exc
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(payload)
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return str(path)

    async def fetch(self, destination_ref: str) -> bytes:
        return Path(destination_ref).read_bytes()


def build_and_sign_anchor(
    bundle: EvidenceBundle,
    key_id: KeyId,
    dek: bytes,
    *,
    anchor_id: str | None = None,
) -> AnchorRecord:
    """Builds an unpublished, signed `AnchorRecord` from an already-built
    `EvidenceBundle` -- *key_id*/*dek* are the caller's own already-resolved
    `KeyPurpose.AUDIT_ANCHOR` key (from a `KeyProvider.get_encryption_key()`
    call), not resolved here, matching this codebase's established
    "abstract input, not a live resolution" discipline for every
    Heart/crypto seam (`root_authority.py`'s `RootResolver`, etc.) --
    keeps this function synchronous and independently testable."""
    signature = sign(dek, key_id, bundle.bundle_digest.encode("utf-8"))
    return AnchorRecord(
        anchor_id=anchor_id or str(uuid.uuid4()),
        org_id=bundle.org_id,
        bundle_id=bundle.bundle_id,
        bundle_digest=bundle.bundle_digest,
        record_count=len(bundle.records),
        key_id=key_id.to_string(),
        signature=signature,
        anchored_at=datetime.now(UTC),
    )


async def publish_anchor(record: AnchorRecord, provider: AuditAnchorProvider) -> AnchorRecord:
    """Publishes *record* (sans `destination_ref`) to *provider*,
    returning a new `AnchorRecord` with `destination_ref` populated.
    Raises `AnchorAlreadyPublishedError` if `record.anchor_id` was
    already published -- callers must generate a fresh `anchor_id` per
    publication, never reuse one."""
    payload = _canonical_json(record.to_dict()).encode("utf-8")
    destination_ref = await provider.publish(record.anchor_id, payload)
    return AnchorRecord(
        anchor_id=record.anchor_id,
        org_id=record.org_id,
        bundle_id=record.bundle_id,
        bundle_digest=record.bundle_digest,
        record_count=record.record_count,
        key_id=record.key_id,
        signature=record.signature,
        anchored_at=record.anchored_at,
        destination_ref=destination_ref,
    )


class AnchorVerificationStatus:
    """String constants, not a StrEnum -- kept intentionally simple
    since this is a 4-way outcome consumed only by tests and operator
    tooling in this phase, not persisted or gated on elsewhere yet."""

    VALID = "VALID"
    DESTINATION_UNREACHABLE = "DESTINATION_UNREACHABLE"
    SIGNATURE_INVALID = "SIGNATURE_INVALID"
    DIGEST_MISMATCH = "DIGEST_MISMATCH"


@dataclass(frozen=True)
class AnchorVerificationResult:
    status: str
    detail: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == AnchorVerificationStatus.VALID


async def verify_anchor_from_provider(
    *,
    current_bundle_digest: str,
    destination_ref: str,
    provider: AuditAnchorProvider,
    key_provider: KeyProvider,
) -> AnchorVerificationResult:
    """The actual compromise-detection check: fetches the anchor record
    from *provider* (an external destination, never the primary DB the
    evidence chain itself lives in), verifies its HMAC signature under
    the `AUDIT_ANCHOR` key it claims, and compares its `bundle_digest`
    against *current_bundle_digest* -- a digest the caller computed
    *fresh*, from the live evidence store's current state, right
    before calling this.

    This is what `verify_chain()` alone cannot do (see module
    docstring and `tests/test_evidence_chain_anchoring.py`): an
    attacker with full database write access can tamper a row and
    regenerate every downstream hash so the chain looks internally
    consistent, but they cannot also silently rewrite what was already
    published to `provider` before the tamper -- so the freshly
    recomputed digest will no longer match the anchored one, and this
    function reports `DIGEST_MISMATCH` rather than `VALID`.
    """
    try:
        payload = await provider.fetch(destination_ref)
    except FileNotFoundError as exc:
        return AnchorVerificationResult(
            AnchorVerificationStatus.DESTINATION_UNREACHABLE,
            detail=f"could not fetch anchor from {destination_ref!r}: {exc}",
        )

    record = AnchorRecord.from_dict(json.loads(payload.decode("utf-8")))

    key_id = KeyId.from_string(record.key_id)
    dek = await key_provider.get_decryption_key(key_id)
    if not verify(dek, key_id, record.bundle_digest.encode("utf-8"), record.signature):
        return AnchorVerificationResult(
            AnchorVerificationStatus.SIGNATURE_INVALID,
            detail=f"anchor {record.anchor_id!r} signature does not verify under {key_id.to_string()!r}",
        )

    if record.bundle_digest != current_bundle_digest:
        return AnchorVerificationResult(
            AnchorVerificationStatus.DIGEST_MISMATCH,
            detail=(
                f"anchored digest {record.bundle_digest!r} does not match "
                f"the current, freshly-recomputed digest {current_bundle_digest!r} -- "
                "the primary evidence store has diverged from what was anchored"
            ),
        )

    return AnchorVerificationResult(AnchorVerificationStatus.VALID)
