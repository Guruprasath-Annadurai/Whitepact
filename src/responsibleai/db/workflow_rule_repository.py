"""Async repository for persisted ``WorkflowSequenceRule``s (v3
authority-layer work, Workflow Authority Engine) -- per-org forbidden
action-sequence rules ``mcp/governance_integration.py`` fetches on every
hosted MCP tool call and passes to ``WhitePactRuntimeGateway.evaluate()``
as ``workflow_rules``.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select

from responsibleai.db.engine import DatabaseEngine, governance_workflow_rules
from responsibleai.governance.workflow import WorkflowSequenceRule


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_rule(row: Any) -> WorkflowSequenceRule:
    return WorkflowSequenceRule(
        rule_id=row.rule_id,
        action_types=tuple(json.loads(row.action_types)),
        window_minutes=row.window_minutes,
    )


class WorkflowRuleNotFoundError(Exception):
    pass


class WorkflowRuleAlreadyExistsError(Exception):
    pass


class WorkflowRuleRepository:
    """CRUD over an org's forbidden-sequence rules. Unlike
    ``PolicyRepository``'s ordered rule set, evaluation order doesn't
    matter here -- every rule is checked independently
    (``check_composition_violation()`` loops all of them) -- so there's
    no ``position``/``reorder`` concept, just add/list/remove."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get_rules(self, org_id: str) -> list[WorkflowSequenceRule]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(governance_workflow_rules)
                    .where(governance_workflow_rules.c.org_id == org_id)
                    .order_by(governance_workflow_rules.c.created_at.asc())
                )
            ).fetchall()
        return [_row_to_rule(r) for r in rows]

    async def add_rule(self, org_id: str, rule: WorkflowSequenceRule) -> None:
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(governance_workflow_rules.c.id)
                    .where(governance_workflow_rules.c.org_id == org_id)
                    .where(governance_workflow_rules.c.rule_id == rule.rule_id)
                )
            ).scalar()
            if existing is not None:
                raise WorkflowRuleAlreadyExistsError(
                    f"Rule {rule.rule_id!r} already exists for org {org_id!r}"
                )
            await conn.execute(
                insert(governance_workflow_rules).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    rule_id=rule.rule_id,
                    action_types=json.dumps(list(rule.action_types)),
                    window_minutes=rule.window_minutes,
                    created_at=_now(),
                )
            )

    async def remove_rule(self, org_id: str, rule_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(governance_workflow_rules)
                .where(governance_workflow_rules.c.org_id == org_id)
                .where(governance_workflow_rules.c.rule_id == rule_id)
            )
            if result.rowcount == 0:
                raise WorkflowRuleNotFoundError(f"No rule {rule_id!r} for org {org_id!r}")
