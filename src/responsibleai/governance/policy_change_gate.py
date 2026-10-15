# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tiered policy governance (decision paper REC-25, option C).

Mode ``single_admin`` (the default and today's behaviour) leaves this module inert: an OWNER/ADMIN may
change policy alone, every change attributed in ``governance_policy_history``.

Mode ``tiered`` changes the rule for edits that could permit something the policy forbade (see
``policy_change.classify_change``):

* tightening or neutral edits: one administrator, as before;
* loosening edits: the caller must have passed a verified step-up AND hold an APPROVED four-eyes request
  that (a) names exactly this organization, policy version and before/after rule sets by digest,
  (b) was requested by the caller (an approval cannot be handed to someone else),
  (c) was approved by a different principal, (d) has not expired and (e) has not been used. The approval
  is consumed with a compare-and-set before the edit is applied, and the edit itself is applied only if
  the policy is still at the approved version.

Nothing here activates by itself: the mode is read from configuration and defaults to ``single_admin``.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import and_, select, update

from responsibleai.db.engine import DatabaseEngine, iam_four_eyes_requests
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_change import ChangeKind, classify_change, rules_digest
from responsibleai.iam.enums import FourEyesStatus, PrivilegedAction


class PolicyGovernanceMode(StrEnum):
    SINGLE_ADMIN = "single_admin"
    TIERED = "tiered"


class PolicyChangeNotAuthorizedError(Exception):
    """A loosening edit lacks the approval the tiered model requires."""

    def __init__(self, message: str, *, change_digest: str, policy_version: int) -> None:
        super().__init__(message)
        self.change_digest = change_digest
        self.policy_version = policy_version


@dataclass(frozen=True)
class ProposedChange:
    organization_id: str
    operation: str  # "rule_added" | "rule_removed" | "reordered"
    policy_version: int
    before: Sequence[PolicyRule]
    after: Sequence[PolicyRule]

    @property
    def kind(self) -> ChangeKind:
        return classify_change(self.before, self.after)

    @property
    def digest(self) -> str:
        material = "|".join(
            [
                self.organization_id,
                self.operation,
                str(self.policy_version),
                rules_digest(self.before),
                rules_digest(self.after),
            ]
        )
        return hashlib.sha256(material.encode("utf-8")).hexdigest()


def requires_second_approver(mode: PolicyGovernanceMode, change: ProposedChange) -> bool:
    return mode is PolicyGovernanceMode.TIERED and change.kind is ChangeKind.LOOSENING


async def consume_approval(
    db: DatabaseEngine,
    *,
    change: ProposedChange,
    actor_principal_id: str,
    four_eyes_request_id: str | None,
) -> None:
    """Spend the approval for ``change`` or raise. Call only after step-up has been verified."""
    refuse = PolicyChangeNotAuthorizedError

    def deny(reason: str) -> PolicyChangeNotAuthorizedError:
        return refuse(reason, change_digest=change.digest, policy_version=change.policy_version)

    if not four_eyes_request_id:
        raise deny("This edit loosens policy and needs a second approver.")
    now = datetime.now(UTC).isoformat()
    async with db.raw.begin() as conn:
        row = (
            await conn.execute(
                select(iam_four_eyes_requests).where(
                    and_(
                        iam_four_eyes_requests.c.id == four_eyes_request_id,
                        iam_four_eyes_requests.c.org_id == change.organization_id,
                    )
                )
            )
        ).first()
        if row is None:
            raise deny("Approval not found for this organization.")
        rec = dict(row._mapping)
        if rec["action"] != PrivilegedAction.MODIFY_POLICY_RULE.value:
            raise deny("Approval is for a different action.")
        if rec["status"] != FourEyesStatus.APPROVED.value:
            raise deny(f"Approval is {rec['status']}, not APPROVED.")
        if rec.get("executed_at") is not None:
            raise deny("Approval has already been used.")
        if now >= rec["expires_at"]:
            raise deny("Approval has expired.")
        if rec["requester_principal_id"] != actor_principal_id:
            raise deny("Approval was requested by a different principal.")
        if not rec["approver_principal_id"] or rec["approver_principal_id"] == actor_principal_id:
            raise deny("Approval has no independent approver.")
        import json

        params = json.loads(rec["parameters_json"] or "{}")
        if params.get("change_digest") != change.digest:
            raise deny("Approval was granted for a different change or policy version.")
        spent = await conn.execute(
            update(iam_four_eyes_requests)
            .where(
                iam_four_eyes_requests.c.id == four_eyes_request_id,
                iam_four_eyes_requests.c.executed_at.is_(None),
                iam_four_eyes_requests.c.status == FourEyesStatus.APPROVED.value,
            )
            .values(executed_at=now)
        )
        if (spent.rowcount or 0) != 1:
            raise deny("Approval has already been used.")
