# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Append-only publication of signed evidence heads.

The database hash chain and an in-process signature are not an
independent witness. This module publishes the signed head outside the
evidence tables. A second process can verify the publication with the
public key alone.

``LIVE_OBJECT_STORE_STATUS`` stays ``NOT_PROVISIONED`` until an owner
completes a retention-locked object-store put and an auditor reads that
object back. A local directory is outside the database. It is not a
separate administrative domain, and it is not a live witness.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import stat
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from responsibleai.governance.evidence_witness import (
    EvidenceHeadWitness,
    EvidenceWitnessError,
    sign_evidence_head,
    verify_evidence_head,
)

LIVE_OBJECT_STORE_STATUS = "NOT_PROVISIONED"
_ORG_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_GENESIS = "0" * 64


class WitnessPublicationError(RuntimeError):
    """The publication does not match the claimed head or cannot be written."""


class WitnessRequiredUnavailableError(WitnessPublicationError):
    """Witnessing is required and the independent publication is unavailable."""


class WitnessKeyError(WitnessPublicationError):
    """The signing key is missing, exposed, or not the key that signed."""


def witness_required(environ: dict[str, str] | None = None) -> bool:
    source = os.environ if environ is None else environ
    return source.get("WHITEPACT_EVIDENCE_WITNESS_REQUIRED", "").strip() in {"1", "true", "TRUE"}


def live_object_store_status(environ: dict[str, str] | None = None) -> str:
    """Configuration presence is not a live witness.

    A complete endpoint, bucket, and key pair means the publisher can be
    pointed at an object store. It does not mean a retention-locked object
    was written or read back by an independent auditor.
    """
    source = os.environ if environ is None else environ
    names = (
        "WHITEPACT_EVIDENCE_S3_ENDPOINT",
        "WHITEPACT_EVIDENCE_S3_BUCKET",
        "WHITEPACT_EVIDENCE_S3_ACCESS_KEY_ID",
        "WHITEPACT_EVIDENCE_S3_SECRET_ACCESS_KEY",
    )
    if all(source.get(name, "").strip() for name in names):
        return "CONFIGURED_UNVERIFIED"
    return LIVE_OBJECT_STORE_STATUS


@dataclass(frozen=True)
class PublishedWitness:
    organization_id: str
    chain_sequence: int
    head_hash: str
    witnessed_at: str
    key_id: str
    public_key_hex: str
    signature_hex: str
    previous_publication_hash: str
    publication_hash: str

    def to_dict(self) -> dict[str, object]:
        return {
            "organization_id": self.organization_id,
            "chain_sequence": self.chain_sequence,
            "head_hash": self.head_hash,
            "witnessed_at": self.witnessed_at,
            "key_id": self.key_id,
            "public_key_hex": self.public_key_hex,
            "signature_hex": self.signature_hex,
            "previous_publication_hash": self.previous_publication_hash,
            "publication_hash": self.publication_hash,
            "live_object_store_status": live_object_store_status(),
        }


def _publication_material(fields: dict[str, object]) -> bytes:
    payload = {key: fields[key] for key in sorted(fields) if key != "publication_hash"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _hash_material(fields: dict[str, object]) -> str:
    return hashlib.sha256(_publication_material(fields)).hexdigest()


def _check_org(organization_id: str) -> None:
    if not _ORG_ID.fullmatch(organization_id):
        raise WitnessPublicationError("organization id is not a safe publication key")


def _make_private_dir(path: Path) -> None:
    """A directory only the owner can enter, whatever the process umask."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)


def _make_public_dir(path: Path, *, enforce: bool = True) -> None:
    """A directory others may read but never write, whatever the process umask.

    Publication authority is the ability to write into the witness directories, so they must not
    be group- or world-writable because a service started with ``umask 0`` said so. The mode is
    only ever narrowed (group/other write cleared), never widened.
    """
    path.mkdir(parents=True, exist_ok=True, mode=0o755)
    if enforce:
        os.chmod(path, stat.S_IMODE(path.stat().st_mode) & ~0o022)


def _check_private_mode(path: Path) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise WitnessKeyError(f"private witness key {path} is group or world accessible")


class FileWitnessKeyStore:
    """Ed25519 key directory. The private key is not exported to callers as text."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.private_dir = directory / "private"
        self.public_dir = directory / "public"

    @classmethod
    def create(
        cls, directory: Path, private_key: Ed25519PrivateKey | None = None
    ) -> FileWitnessKeyStore:
        store = cls(directory)
        _make_public_dir(directory, enforce=False)  # a root the operator may already own
        _make_private_dir(store.private_dir)
        _make_public_dir(store.public_dir)
        key = private_key or Ed25519PrivateKey.generate()
        store._install(key)
        return store

    def _install(self, key: Ed25519PrivateKey) -> str:
        raw_private = key.private_bytes_raw()
        public = key.public_key().public_bytes_raw()
        key_id = hashlib.sha256(public).hexdigest()[:16]
        target = self.private_dir / "current.key"
        temporary = self.private_dir / f".{key_id}.key"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, raw_private)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        (self.private_dir / "key_id").write_text(key_id + "\n", encoding="utf-8")
        os.chmod(self.private_dir / "key_id", 0o600)
        public_path = self.public_dir / f"{key_id}.pub"
        public_path.write_bytes(public)
        os.chmod(public_path, 0o644)
        return key_id

    def current_key_id(self) -> str:
        return (self.private_dir / "key_id").read_text(encoding="utf-8").strip()

    def current_private(self) -> tuple[str, Ed25519PrivateKey]:
        path = self.private_dir / "current.key"
        if not path.is_file():
            raise WitnessKeyError("witness private key is not installed")
        _check_private_mode(path)
        raw = path.read_bytes()
        if len(raw) != 32:
            raise WitnessKeyError("witness private key has the wrong length")
        return self.current_key_id(), Ed25519PrivateKey.from_private_bytes(raw)

    def rotate(self) -> str:
        _key_id, _old = self.current_private()
        return self._install(Ed25519PrivateKey.generate())

    def public_key(self, key_id: str) -> Ed25519PublicKey:
        path = self.public_dir / f"{key_id}.pub"
        if not path.is_file():
            raise WitnessKeyError(f"public witness key {key_id} is not retained")
        raw = path.read_bytes()
        if len(raw) != 32:
            raise WitnessKeyError("public witness key has the wrong length")
        return Ed25519PublicKey.from_public_bytes(raw)


class AppendOnlyWitnessLog:
    """One JSON object per organization sequence. Existing names are not replaced."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory
        _make_public_dir(self.directory, enforce=False)

    def _org_dir(self, organization_id: str) -> Path:
        _check_org(organization_id)
        return self.directory / organization_id

    def publish(
        self,
        witness: EvidenceHeadWitness,
        *,
        key_id: str,
    ) -> PublishedWitness:
        _check_org(witness.organization_id)
        if witness.chain_sequence < 1:
            raise WitnessPublicationError("chain sequence must be positive")
        org_dir = self._org_dir(witness.organization_id)
        _make_public_dir(org_dir)
        prior = self.latest(witness.organization_id)
        if prior is not None and witness.chain_sequence <= prior.chain_sequence:
            raise WitnessPublicationError(
                "publication refuses a sequence that is not strictly newer"
            )
        previous_hash = prior.publication_hash if prior is not None else _GENESIS
        fields: dict[str, object] = {
            "organization_id": witness.organization_id,
            "chain_sequence": witness.chain_sequence,
            "head_hash": witness.head_hash,
            "witnessed_at": witness.witnessed_at,
            "key_id": key_id,
            "public_key_hex": witness.public_key_hex,
            "signature_hex": witness.signature_hex,
            "previous_publication_hash": previous_hash,
        }
        fields["publication_hash"] = _hash_material(fields)
        destination = org_dir / f"{witness.chain_sequence}.json"
        payload = (json.dumps(fields, sort_keys=True) + "\n").encode("utf-8")
        try:
            fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError as exc:
            raise WitnessPublicationError("publication object already exists") from exc
        try:
            os.write(fd, payload)
            os.fsync(fd)
        finally:
            os.close(fd)
        return PublishedWitness(
            organization_id=witness.organization_id,
            chain_sequence=witness.chain_sequence,
            head_hash=witness.head_hash,
            witnessed_at=witness.witnessed_at,
            key_id=key_id,
            public_key_hex=witness.public_key_hex,
            signature_hex=witness.signature_hex,
            previous_publication_hash=previous_hash,
            publication_hash=str(fields["publication_hash"]),
        )

    def read(self, organization_id: str, chain_sequence: int) -> PublishedWitness | None:
        path = self._org_dir(organization_id) / f"{chain_sequence}.json"
        if not path.is_file():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return PublishedWitness(
            organization_id=data["organization_id"],
            chain_sequence=int(data["chain_sequence"]),
            head_hash=data["head_hash"],
            witnessed_at=data["witnessed_at"],
            key_id=data["key_id"],
            public_key_hex=data["public_key_hex"],
            signature_hex=data["signature_hex"],
            previous_publication_hash=data["previous_publication_hash"],
            publication_hash=data["publication_hash"],
        )

    def history(self, organization_id: str) -> list[PublishedWitness]:
        org_dir = self._org_dir(organization_id)
        if not org_dir.is_dir():
            return []
        records: list[PublishedWitness] = []
        for path in sorted(org_dir.glob("*.json"), key=lambda item: int(item.stem)):
            loaded = self.read(organization_id, int(path.stem))
            if loaded is not None:
                records.append(loaded)
        return records

    def latest(self, organization_id: str) -> PublishedWitness | None:
        records = self.history(organization_id)
        if not records:
            return None
        return records[-1]


def verify_publication_chain(records: list[PublishedWitness]) -> None:
    previous = _GENESIS
    expected_sequence = 1
    for record in records:
        if record.chain_sequence != expected_sequence:
            raise WitnessPublicationError(
                f"publication sequence gap at {record.chain_sequence}, expected {expected_sequence}"
            )
        if record.previous_publication_hash != previous:
            raise WitnessPublicationError("publication history was rewritten")
        fields: dict[str, object] = {
            "organization_id": record.organization_id,
            "chain_sequence": record.chain_sequence,
            "head_hash": record.head_hash,
            "witnessed_at": record.witnessed_at,
            "key_id": record.key_id,
            "public_key_hex": record.public_key_hex,
            "signature_hex": record.signature_hex,
            "previous_publication_hash": record.previous_publication_hash,
        }
        if _hash_material(fields) != record.publication_hash:
            raise WitnessPublicationError("publication hash does not match its body")
        witness = EvidenceHeadWitness(
            organization_id=record.organization_id,
            chain_sequence=record.chain_sequence,
            head_hash=record.head_hash,
            witnessed_at=record.witnessed_at,
            public_key_hex=record.public_key_hex,
            signature_hex=record.signature_hex,
        )
        try:
            verify_evidence_head(
                witness,
                organization_id=record.organization_id,
                chain_sequence=record.chain_sequence,
                head_hash=record.head_hash,
            )
        except EvidenceWitnessError as exc:
            raise WitnessPublicationError("published signature is not valid") from exc
        previous = record.publication_hash
        expected_sequence += 1


def verify_published_head(
    log: AppendOnlyWitnessLog,
    *,
    organization_id: str,
    chain_sequence: int,
    head_hash: str,
) -> PublishedWitness:
    """Verify a claimed database head against the publication only.

    A lower claimed sequence than the published tip is a rollback.
    A different hash at the same sequence is a rewrite. A missing file
    is a missing publication.
    """
    records = log.history(organization_id)
    if not records:
        raise WitnessPublicationError("witness publication is missing")
    verify_publication_chain(records)
    latest = records[-1]
    if chain_sequence != latest.chain_sequence or head_hash != latest.head_hash:
        if chain_sequence < latest.chain_sequence:
            raise WitnessPublicationError("database head rolled back behind the publication")
        raise WitnessPublicationError("database head does not match the published witness")
    matched = log.read(organization_id, chain_sequence)
    if matched is None or matched.head_hash != head_hash:
        raise WitnessPublicationError("published witness is missing or inconsistent")
    return matched


def publish_evidence_head(
    store: FileWitnessKeyStore,
    log: AppendOnlyWitnessLog,
    *,
    organization_id: str,
    chain_sequence: int,
    head_hash: str,
    witnessed_at: str,
    required: bool | None = None,
) -> PublishedWitness:
    """Sign with the key store and append the witness. Fail closed when required."""
    try:
        key_id, private_key = store.current_private()
        witness = sign_evidence_head(
            private_key,
            organization_id=organization_id,
            chain_sequence=chain_sequence,
            head_hash=head_hash,
            witnessed_at=witnessed_at,
        )
        return log.publish(witness, key_id=key_id)
    except (WitnessPublicationError, OSError) as exc:
        if required if required is not None else witness_required():
            raise WitnessRequiredUnavailableError(
                "required evidence witness is unavailable"
            ) from exc
        raise


class ObjectStoreTransport(Protocol):
    def __call__(self, request: urllib.request.Request) -> tuple[int, bytes]: ...


def object_lock_headers(*, retain_until: datetime) -> dict[str, str]:
    if retain_until.tzinfo is None:
        raise WitnessPublicationError("object-lock retention must be timezone-aware")
    return {
        "x-amz-object-lock-mode": "COMPLIANCE",
        "x-amz-object-lock-retain-until-date": retain_until.astimezone(UTC).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "If-None-Match": "*",
    }


def put_object_lock(
    *,
    endpoint: str,
    bucket: str,
    key: str,
    body: bytes,
    access_key_id: str,
    secret_access_key: str,
    region: str = "auto",
    retain_until: datetime | None = None,
    transport: ObjectStoreTransport | None = None,
) -> int:
    """PUT one object with retention headers. The transport is injectable for tests.

    A successful status from a fake transport is not a live Cloudflare R2
    witness. ``live_object_store_status`` does not become live here.
    """
    if not endpoint or not bucket or not access_key_id or not secret_access_key:
        raise WitnessRequiredUnavailableError("object store witness is not configured")
    _require_https_endpoint(endpoint)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    day = stamp[:8]
    payload_hash = hashlib.sha256(body).hexdigest()
    host = endpoint.removeprefix("https://").removeprefix("http://").rstrip("/")
    retain = retain_until or (datetime.now(UTC) + timedelta(days=3650))
    extra = object_lock_headers(retain_until=retain)
    canonical_headers = {
        "host": host,
        "x-amz-content-sha256": payload_hash,
        "x-amz-date": stamp,
    }
    for name, value in extra.items():
        canonical_headers[name.lower()] = value
    signed_header_names = ";".join(sorted(canonical_headers))
    canonical_header_text = "".join(
        f"{name}:{canonical_headers[name].strip()}\n" for name in sorted(canonical_headers)
    )
    canonical_uri = "/" + bucket.strip("/") + "/" + key.lstrip("/")
    canonical_request = "\n".join(
        [
            "PUT",
            canonical_uri,
            "",
            canonical_header_text,
            signed_header_names,
            payload_hash,
        ]
    )
    scope = f"{day}/{region}/s3/aws4_request"
    string_to_sign = "\n".join(
        [
            "AWS4-HMAC-SHA256",
            stamp,
            scope,
            hashlib.sha256(canonical_request.encode()).hexdigest(),
        ]
    )

    def _hmac(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode(), hashlib.sha256).digest()

    signing_key = _hmac(
        _hmac(_hmac(_hmac(("AWS4" + secret_access_key).encode(), day), region), "s3"),
        "aws4_request",
    )
    signature = _hmac(signing_key, string_to_sign).hex()
    authorization = (
        "AWS4-HMAC-SHA256 "
        f"Credential={access_key_id}/{scope}, "
        f"SignedHeaders={signed_header_names}, "
        f"Signature={signature}"
    )
    url = endpoint.rstrip("/") + canonical_uri
    request = urllib.request.Request(url, data=body, method="PUT")
    request.add_header("Authorization", authorization)
    request.add_header("x-amz-date", stamp)
    request.add_header("x-amz-content-sha256", payload_hash)
    for name, value in extra.items():
        request.add_header(name, value)
    sender = transport or _urllib_transport
    try:
        status, _response = sender(request)
    except (OSError, urllib.error.URLError) as exc:
        raise WitnessRequiredUnavailableError("object store witness is unreachable") from exc
    if status not in {200, 201}:
        raise WitnessRequiredUnavailableError(
            f"object store rejected the witness with status {status}"
        )
    return status


def _require_https_endpoint(endpoint: str) -> None:
    """Refuse any endpoint that is not a plain https origin.

    The request carries a SigV4 Authorization header. A ``file:``, ``ftp:`` or ``http:``
    endpoint, one with embedded credentials, or one with no host must never be handed to
    the HTTP client. Bandit B310 flagged the unrestricted ``urlopen`` that followed.
    """
    parsed = urllib.parse.urlsplit(endpoint)
    if parsed.scheme != "https" or not parsed.hostname:
        raise WitnessRequiredUnavailableError("object store endpoint must be an https URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WitnessRequiredUnavailableError(
            "object store endpoint must not embed credentials, a query or a fragment"
        )


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """A signed request must go to the configured host and nowhere else."""

    def redirect_request(self, *args: object, **kwargs: object) -> None:  # type: ignore[override]
        return None


def _urllib_transport(request: urllib.request.Request) -> tuple[int, bytes]:
    # Re-check at the point of use so a Request built elsewhere cannot reach the network
    # over another scheme.
    _require_https_endpoint(request.full_url)
    opener = urllib.request.build_opener(_NoRedirect)
    with opener.open(request, timeout=10) as response:
        return int(response.status), response.read()
