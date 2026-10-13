# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""B4 adversarial security-state fixtures and post-restore verification."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from responsibleai.dashboard import app as app_module
from responsibleai.dashboard.app import app
from responsibleai.db.approval_repository import (
    ApprovalAlreadyResolvedError,
    ApprovalNotApprovedError,
    ApprovalRepository,
)
from responsibleai.db.engine import create_engine
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance.approval import ApprovalStatus, build_approval_request
from responsibleai.governance.execution import (
    AuthorizationExpiredError,
    _validate_authorization,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.rbac.models import Role


@dataclass
class SecuritySnapshot:
    org_a: str
    org_b: str
    raw_key_a: str
    raw_key_b: str
    consumed_nonce: str
    authorization_id: str
    epoch_after_bump: int
    denied_approval_id: str
    expired_auth_id: str

    def to_dict(self, *, redact_secrets: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if redact_secrets:
            for field in ("raw_key_a", "raw_key_b"):
                raw = data.get(field) or ""
                data[field] = (
                    f"redacted:sha256:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"
                    if raw
                    else "redacted"
                )
            for field in (
                "consumed_nonce",
                "authorization_id",
                "denied_approval_id",
                "expired_auth_id",
            ):
                val = data.get(field) or ""
                data[field] = (
                    f"redacted:sha256:{hashlib.sha256(val.encode()).hexdigest()[:16]}"
                    if val
                    else "redacted"
                )
        return data


def _sample_action(org_id: str, identity_id: str = "security-fixture") -> ActionRequest:
    return ActionRequest(
        AgentContext(
            IdentityContext(identity_id, "agent", org_id=org_id),
            organization_id=org_id,
        ),
        "EXECUTE",
        "/protected/resource",
    )


async def install_security_fixtures(db_url: str) -> SecuritySnapshot:
    engine = create_engine(db_url)
    org_repo = OrgRepository(engine)
    org_a = await org_repo.create_org("Tenant Alpha", f"tenant-alpha-{uuid.uuid4().hex[:8]}")
    org_b = await org_repo.create_org("Tenant Beta", f"tenant-beta-{uuid.uuid4().hex[:8]}")
    _, raw_a = await org_repo.create_key(org_a.id, "alpha-admin", Role.OWNER)
    _, raw_b = await org_repo.create_key(org_b.id, "beta-admin", Role.OWNER)

    nonce_repo = ExecutionNonceRepository(engine)
    auth_id = str(uuid.uuid4())
    nonce_value = uuid.uuid4().hex
    epoch_repo = RevocationEpochRepository(engine)
    epoch_before = (await epoch_repo.current(org_a.id)).epoch
    await nonce_repo.consume(
        nonce_value,
        authorization_id=auth_id,
        organization_id=org_a.id,
        expected_epoch=epoch_before,
    )
    bumped = await epoch_repo.bump(org_a.id)

    action = _sample_action(org_a.id)
    decision = DecisionResult(
        decision=GovernanceDecision.REQUIRE_APPROVAL,
        action_id=action.action_id,
        reason_codes=["test_denied"],
    )
    approval_repo = ApprovalRepository(engine)
    denied = await approval_repo.create(build_approval_request(action, decision))
    await approval_repo.resolve(
        denied.approval_id,
        resolved_by="security-reviewer",
        outcome=ApprovalStatus.DENIED,
        notes="fixture",
    )

    expired_auth_id = str(uuid.uuid4())

    await engine.close()
    return SecuritySnapshot(
        org_a=org_a.id,
        org_b=org_b.id,
        raw_key_a=raw_a,
        raw_key_b=raw_b,
        consumed_nonce=nonce_value,
        authorization_id=auth_id,
        epoch_after_bump=bumped.epoch,
        denied_approval_id=denied.approval_id,
        expired_auth_id=expired_auth_id,
    )


async def verify_security_state(db_url: str, snapshot: SecuritySnapshot) -> dict[str, Any]:
    engine = create_engine(db_url)
    results: dict[str, Any] = {}

    nonce_repo = ExecutionNonceRepository(engine)
    try:
        await nonce_repo.consume(
            snapshot.consumed_nonce,
            authorization_id=snapshot.authorization_id,
            organization_id=snapshot.org_a,
            expected_epoch=snapshot.epoch_after_bump,
        )
        results["consumed_nonce_replay_blocked"] = False
    except NonceAlreadyConsumedError:
        results["consumed_nonce_replay_blocked"] = True

    try:
        await nonce_repo.consume(
            uuid.uuid4().hex,
            authorization_id=str(uuid.uuid4()),
            organization_id=snapshot.org_a,
            expected_epoch=0,
        )
        results["stale_epoch_rejected"] = False
    except StaleRevocationEpochError:
        results["stale_epoch_rejected"] = True

    from responsibleai.governance.execution import ExecutionAuthorization

    expired = ExecutionAuthorization(
        authorization_id=snapshot.expired_auth_id,
        action_digest="deadbeef",
        organization_id=snapshot.org_a,
        decision=GovernanceDecision.ALLOW,
        principal_id="security-fixture",
        expires_at=datetime.now(UTC) - timedelta(minutes=5),
    )
    try:
        _validate_authorization(expired, _sample_action(snapshot.org_a))
        results["expired_execution_grant_rejected"] = False
    except AuthorizationExpiredError:
        results["expired_execution_grant_rejected"] = True

    approval_repo = ApprovalRepository(engine)
    denied = await approval_repo.get(snapshot.denied_approval_id)
    results["denied_approval_status"] = denied.status.value if denied else None
    try:
        await approval_repo.resolve(
            snapshot.denied_approval_id,
            resolved_by="attacker",
            outcome=ApprovalStatus.APPROVED,
        )
        results["denied_approval_immutable"] = False
    except ApprovalAlreadyResolvedError:
        results["denied_approval_immutable"] = True

    try:
        await approval_repo.consume(
            snapshot.denied_approval_id,
            action=_sample_action(snapshot.org_a),
        )
        results["denied_approval_consume_blocked"] = False
    except ApprovalNotApprovedError:
        results["denied_approval_consume_blocked"] = True

    evidence_repo = EvidenceRepository(engine)
    results["governance_evidence_chain_valid"] = await evidence_repo.verify_chain(
        snapshot.org_a
    )

    from responsibleai.db.audit_repository import AuditRepository

    audit_repo = AuditRepository(engine)
    audit_chain = await audit_repo.verify_chain(days=3650)
    results["audit_log_chain"] = audit_chain

    app_module.settings.database_url = db_url
    app_module.settings.auth_enabled = True
    app_module.settings.api_keys = []
    app_module.settings.auto_migrate = False
    async with LifespanManager(app, startup_timeout=120):
        headers_a = {"Authorization": f"Bearer {snapshot.raw_key_a}"}
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            cross = await client.get(f"/api/orgs/{snapshot.org_b}/keys", headers=headers_a)
            results["cross_tenant_list_keys_status"] = cross.status_code
            results["cross_tenant_access_denied"] = cross.status_code in {403, 404, 401}
            own = await client.get(f"/api/orgs/{snapshot.org_a}/keys", headers=headers_a)
            results["same_tenant_list_keys_status"] = own.status_code
            results["same_tenant_access_allowed"] = own.status_code == 200

    await engine.close()
    results["passed"] = all(
        [
            results.get("consumed_nonce_replay_blocked"),
            results.get("stale_epoch_rejected"),
            results.get("expired_execution_grant_rejected"),
            results.get("denied_approval_immutable"),
            results.get("denied_approval_consume_blocked"),
            results.get("denied_approval_status") == "DENIED",
            results.get("cross_tenant_access_denied"),
            results.get("same_tenant_access_allowed"),
            results.get("governance_evidence_chain_valid"),
            audit_chain.get("intact"),
        ]
    )
    return results
