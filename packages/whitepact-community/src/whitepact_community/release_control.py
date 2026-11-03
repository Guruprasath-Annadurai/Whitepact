"""Default-deny community release exporter (synthetic authorization only).

Preserves Track A release-control invariants for local qualification:
- empty approved public allowlist by default
- exact source/tree binding
- independent reviewer authority slot
- trusted CI provenance requirement
- durable replay protection
- fail-closed export behavior

Does NOT configure live Founder identity or real release approval.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


class ExportDenied(Exception):
    """Fail-closed export refusal."""


@dataclass(frozen=True)
class TrustRoot:
    """Synthetic trust root for local tests — not a production Founder key."""

    root_id: str
    public_key_pem: str
    purpose: str = "synthetic-community-qualification-only"


@dataclass
class ExportAuthorization:
    authorization_id: str
    source_tree_sha256: str
    reviewer_id: str
    ci_provenance_id: str
    approved_paths: frozenset[str] = field(default_factory=frozenset)
    nonce: str = ""
    expires_at: datetime | None = None
    consumed: bool = False


@dataclass
class ReplayLedger:
    """Durable replay protection for export authorizations."""

    path: Path
    _seen: set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    self._seen.add(line.strip())

    def observe(self, authorization_id: str, nonce: str) -> None:
        key = f"{authorization_id}:{nonce}"
        if key in self._seen:
            raise ExportDenied(f"Replay detected for authorization {authorization_id}")
        self._seen.add(key)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(key + "\n")


def compute_tree_digest(root: Path) -> str:
    paths = sorted(p for p in root.rglob("*") if p.is_file())
    h = hashlib.sha256()
    for path in paths:
        rel = path.relative_to(root).as_posix().encode("utf-8")
        h.update(rel)
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


class DefaultDenyExporter:
    """Exports nothing unless every gate passes — allowlist starts empty."""

    def __init__(
        self,
        *,
        approved_public_allowlist: frozenset[str] | None = None,
        trust_roots: list[TrustRoot] | None = None,
        replay: ReplayLedger | None = None,
        require_ci_provenance: bool = True,
    ) -> None:
        self.approved_public_allowlist = approved_public_allowlist or frozenset()
        self.trust_roots = trust_roots or []
        self.replay = replay
        self.require_ci_provenance = require_ci_provenance

    def verify_authorization(
        self,
        auth: ExportAuthorization,
        *,
        source_root: Path,
        now: datetime | None = None,
    ) -> None:
        clock = now or datetime.now(UTC)
        if auth.expires_at is not None and clock >= auth.expires_at:
            raise ExportDenied("Export authorization expired")
        if auth.consumed:
            raise ExportDenied("Export authorization already consumed")
        if self.require_ci_provenance and not auth.ci_provenance_id:
            raise ExportDenied("Trusted CI provenance required")
        if not auth.reviewer_id:
            raise ExportDenied("Independent reviewer authority required")
        if not self.trust_roots:
            raise ExportDenied("No synthetic trust roots configured for verification")
        actual = compute_tree_digest(source_root)
        if actual != auth.source_tree_sha256:
            raise ExportDenied("Source tree digest mismatch — exact binding failed")
        # Allowlist must remain empty unless Founder/steward authorization expands it.
        if auth.approved_paths - self.approved_public_allowlist:
            raise ExportDenied(
                "Authorization requests paths outside the approved public allowlist"
            )
        if self.replay is not None:
            self.replay.observe(auth.authorization_id, auth.nonce or auth.authorization_id)

    def export(
        self,
        auth: ExportAuthorization,
        *,
        source_root: Path,
        destination: Path,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        self.verify_authorization(auth, source_root=source_root, now=now)
        if not auth.approved_paths:
            raise ExportDenied(
                "Default-deny: approved public allowlist is empty; refusing export"
            )
        # Unreachable for default empty allowlist; kept for future steward-approved paths.
        destination.mkdir(parents=True, exist_ok=True)
        auth.consumed = True
        receipt = {
            "exported": sorted(auth.approved_paths),
            "source_tree_sha256": auth.source_tree_sha256,
            "reviewer_id": auth.reviewer_id,
            "ci_provenance_id": auth.ci_provenance_id,
            "exported_at": (now or datetime.now(UTC)).isoformat(),
        }
        (destination / "export_receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return receipt


__all__ = [
    "DefaultDenyExporter",
    "ExportAuthorization",
    "ExportDenied",
    "ReplayLedger",
    "TrustRoot",
    "compute_tree_digest",
]
