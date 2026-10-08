# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M4 revocation semantics under epoch advancement (fail-closed authority)."""

from __future__ import annotations

from responsibleai.governance.revocation_kernel import (
    RevocationEpoch,
    RevocationEpochCheckStatus,
    bump_epoch,
    check_revocation_epoch,
)


def test_revocation_after_bump_rejects_stale_grant_epoch() -> None:
    issued = RevocationEpoch(organization_id="org-1", scope="delegation", epoch=2)
    current = bump_epoch(issued)
    result = check_revocation_epoch(issued, current)
    assert result.status == RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE
    assert not result.is_current


def test_revocation_scope_mismatch_fails_closed() -> None:
    issued = RevocationEpoch(organization_id="org-1", scope="delegation", epoch=1)
    current = RevocationEpoch(organization_id="org-1", scope="execution", epoch=1)
    result = check_revocation_epoch(issued, current)
    assert result.status == RevocationEpochCheckStatus.SCOPE_MISMATCH
