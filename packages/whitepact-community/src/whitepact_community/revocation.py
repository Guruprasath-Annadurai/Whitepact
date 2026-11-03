"""Local revocation epoch primitive (community-scoped)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class RevocationEpoch:
    organization_id: str
    scope: str
    epoch: int = 0


def bump_epoch(current: RevocationEpoch) -> RevocationEpoch:
    return RevocationEpoch(
        organization_id=current.organization_id,
        scope=current.scope,
        epoch=current.epoch + 1,
    )


class RevocationEpochCheckStatus(StrEnum):
    CURRENT = "CURRENT"
    REVOKED_SINCE_ISSUANCE = "REVOKED_SINCE_ISSUANCE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"


@dataclass(frozen=True)
class RevocationEpochCheckResult:
    status: RevocationEpochCheckStatus
    issued_at_epoch: int
    current_epoch: int


def check_revocation_epoch(
    issued: RevocationEpoch,
    current: RevocationEpoch,
) -> RevocationEpochCheckResult:
    if issued.organization_id != current.organization_id or issued.scope != current.scope:
        return RevocationEpochCheckResult(
            status=RevocationEpochCheckStatus.SCOPE_MISMATCH,
            issued_at_epoch=issued.epoch,
            current_epoch=current.epoch,
        )
    if current.epoch > issued.epoch:
        return RevocationEpochCheckResult(
            status=RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE,
            issued_at_epoch=issued.epoch,
            current_epoch=current.epoch,
        )
    return RevocationEpochCheckResult(
        status=RevocationEpochCheckStatus.CURRENT,
        issued_at_epoch=issued.epoch,
        current_epoch=current.epoch,
    )


class LocalRevocationRegistry:
    """In-memory per-(org, scope) epoch store for local tests."""

    def __init__(self) -> None:
        self._epochs: dict[tuple[str, str], int] = {}

    def current(self, organization_id: str, scope: str = "authority") -> RevocationEpoch:
        key = (organization_id, scope)
        return RevocationEpoch(
            organization_id=organization_id,
            scope=scope,
            epoch=self._epochs.get(key, 0),
        )

    def revoke(self, organization_id: str, scope: str = "authority") -> RevocationEpoch:
        key = (organization_id, scope)
        new_epoch = self._epochs.get(key, 0) + 1
        self._epochs[key] = new_epoch
        return RevocationEpoch(organization_id=organization_id, scope=scope, epoch=new_epoch)
