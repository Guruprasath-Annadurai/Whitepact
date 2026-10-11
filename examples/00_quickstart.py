# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact quickstart: the five governance decisions plus tamper-evident evidence.

Install: pip install "rai-governance-platform[dashboard]"
Run:     python examples/00_quickstart.py
This exact code is embedded in README.md and executed by tests/test_readme_examples.py.
"""

import asyncio

from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.governance import ActionRequest, AuthorityContext, WhitePactRuntimeGateway
from responsibleai.governance.evidence import build_evidence_record
from responsibleai.governance.models import AgentContext, IdentityContext

TOOL = "mcp:tool:rai_scan"
gateway = WhitePactRuntimeGateway()
agent = AgentContext(
    identity=IdentityContext(identity_id="agent-1", kind="agent", org_id="acme"),
    organization_id="acme",
    agent_id="agent-1",
)


def evaluate(arguments, *, granted=(TOOL,), require_approval=(), violations=0):
    """Ask the gateway for a decision. Authority comes from a human (`delegated_by`)."""
    action = ActionRequest(agent=agent, action_type=TOOL, target="rai_scan", arguments=arguments)
    authority = AuthorityContext(
        delegated_by="alice@acme.com",
        granted_action_types=frozenset(granted),
        require_approval_for=frozenset(require_approval),
    )
    result = gateway.evaluate(action, authority, recent_violation_count=violations)
    return action, authority, result


cases = {
    "ALLOW": evaluate({"text": "hello"}),
    "DENY (no delegated authority)": evaluate({"text": "hello"}, granted=()),
    "REQUIRE_APPROVAL": evaluate({"text": "hello"}, require_approval=(TOOL,)),
    "ALLOW_WITH_REDACTION": evaluate({"text": "Contact jane@example.com, SSN 123-45-6789"}),
    "QUARANTINE (repeated denials)": evaluate({"text": "hello"}, violations=5),
}
for label, (_, _, result) in cases.items():
    print(f"{label:32} -> {result.decision.value}")


async def record_evidence() -> None:
    """Every decision becomes a per-organization, hash-chained evidence record."""
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(
                id="acme", name="Acme", slug="acme", created_at="2026-01-01T00:00:00Z"
            )
        )
    repo = EvidenceRepository(engine)
    for action, authority, result in cases.values():
        await repo.record(build_evidence_record(action, agent, authority, result))
    print("evidence chain intact:", await repo.verify_chain("acme"))
    await engine.close()


asyncio.run(record_evidence())
