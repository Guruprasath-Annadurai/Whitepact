# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tenant Deletion Orchestrator for WhitePact Phase 5.

Implements multi-step governed workflow:
1. Authority & Legal Hold Check.
2. Tenant Quarantine.
3. Immediate Credential, Session & Authority Revocation.
4. Topological Dependency-Ordered Data Erasure.
5. In-Memory / Redis Cache Invalidation.
6. Generational Tombstone Ledger Registration.
7. Post-Deletion Verification Scanner (Zero Residual Eligible Rows).
8. Canonical Lifecycle Evidence Recording.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update

from responsibleai.data_governance.backup_defense import (
    CurrentLifecycleStateProvider,
    DurableLifecycleStateProvider,
    LifecycleState,
    assert_current_restore_readiness_admitted,
)
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    credential_issuances,
    data_retention_policies,
    eval_baselines,
    eval_runs,
    governance_approval_votes,
    governance_approvals,
    governance_authority_passports,
    governance_crypto_keys,
    governance_delegations,
    governance_execution_authorizations,
    governance_execution_nonces,
    governance_intent_contracts,
    governance_neural_vault_index,
    governance_outcomes,
    governance_policies,
    governance_policy_versions,
    governance_workflow_rules,
    iam_api_key_lineage,
    iam_break_glass_sessions,
    iam_four_eyes_requests,
    iam_jit_grants,
    iam_recovery_challenges,
    iam_recovery_policies,
    iam_scim_groups,
    iam_scim_users,
    iam_sessions,
    iam_step_up_nonces,
    incidents,
    mcp_tool_calls,
    oauth_auth_events,
    oauth_authorization_codes,
    oauth_credentials,
    org_api_keys,
    org_authority_ceilings,
    org_autonomy_budgets,
    organizations,
    runtime_containment_records,
    runtime_execution_attempts,
    runtime_execution_dispatch_outbox,
    runtime_execution_requests,
    runtime_worker_leases,
    stripe_webhook_events,
    tenant_tombstones,
    token_usage,
    tool_trust_scores,
    trust_passports,
    trust_scores,
    upstream_mcp_servers,
    verified_principals,
    web_memberships,
    web_sessions,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _now_dt() -> datetime:
    return datetime.now(UTC)


_REVOCATION_NOTE = "Tenant deletion revoked referenced approval; execution authority withdrawn"
_ADMISSION_CLOSED = "Tenant deletion closed admission"
_TOMBSTONE_SUFFIX = "-tombstoned-"


def _eligible_erasure_tables() -> list[tuple]:
    """Tables with no restrictive reference from immutable execution requests."""
    return [
        (web_memberships, "web_memberships", "org_id"),
        (iam_scim_users, "iam_scim_users", "org_id"),
        (iam_scim_groups, "iam_scim_groups", "org_id"),
        (iam_four_eyes_requests, "iam_four_eyes_requests", "org_id"),
        (incidents, "incidents", "org_id"),
        (governance_policies, "governance_policies", "org_id"),
        (governance_policy_versions, "governance_policy_versions", "org_id"),
        (upstream_mcp_servers, "upstream_mcp_servers", "org_id"),
        (org_authority_ceilings, "org_authority_ceilings", "org_id"),
        (governance_workflow_rules, "governance_workflow_rules", "org_id"),
        (governance_delegations, "governance_delegations", "org_id"),
        (org_autonomy_budgets, "org_autonomy_budgets", "org_id"),
        (tool_trust_scores, "tool_trust_scores", "org_id"),
        (trust_scores, "trust_scores", "org_id"),
        (credential_issuances, "credential_issuances", "org_id"),
        (governance_outcomes, "governance_outcomes", "org_id"),
        (verified_principals, "verified_principals", "org_id"),
        (governance_intent_contracts, "governance_intent_contracts", "org_id"),
        (governance_authority_passports, "governance_authority_passports", "org_id"),
        (trust_passports, "trust_passports", "org_id"),
        (oauth_authorization_codes, "oauth_authorization_codes", "org_id"),
        (oauth_credentials, "oauth_credentials", "org_id"),
        (oauth_auth_events, "oauth_auth_events", "org_id"),
        (governance_crypto_keys, "governance_crypto_keys", "tenant_id"),
        (governance_neural_vault_index, "governance_neural_vault_index", "organization_id"),
        (governance_execution_nonces, "governance_execution_nonces", "organization_id"),
        (eval_runs, "eval_runs", "org_id"),
        (eval_baselines, "eval_baselines", "org_id"),
        (mcp_tool_calls, "mcp_tool_calls", "org_id"),
        (token_usage, "token_usage", "org_id"),
        (data_retention_policies, "data_retention_policies", "org_id"),
    ]


class TenantDeletionError(Exception):
    """Base exception for tenant deletion failures."""


class TenantResidualDataError(TenantDeletionError):
    """Raised when post-deletion verification detects residual eligible data."""


@dataclass(frozen=True)
class TenantDeletionResult:
    org_id: str
    generation_id: str
    deleted_at: str
    tombstone_id: str
    purged_tables: dict[str, int]
    verification_passed: bool


class TenantDeletionOrchestrator:
    """Executes full governed tenant deletion and tombstone lifecycle."""

    def __init__(
        self,
        engine: DatabaseEngine,
        lifecycle_provider: CurrentLifecycleStateProvider | None = None,
    ) -> None:
        self._engine = engine
        self._legal_hold = LegalHoldManager(engine)
        self._lifecycle_provider = lifecycle_provider

    async def _contain_inflight(self, org_id: str, revoked_epoch: int) -> None:
        """An erasure receipt requires actual containment, not a revoked DB lease.

        The organization is already durably DISABLED. Existing registry logic
        retains uncertain local/remote work and rejects stale late registration.
        Never manufacture a CONTAINED journal entry or infer absence from a PID.
        """
        from responsibleai.isolation.in_flight import InFlightExecutionRegistry

        try:
            registry = InFlightExecutionRegistry.get_instance()
            registry.record_revoked_epoch(org_id, revoked_epoch)
            await registry.retry_unresolved(org_id)
            await registry.terminate_in_flight(organization_id=org_id)
            if registry.count_active(org_id) or registry.count_unresolved(org_id):
                raise TenantDeletionError("Containment unconfirmed for deleting tenant")
            async with self._engine.raw.connect() as connection:
                unresolved = await connection.scalar(
                    select(runtime_containment_records.c.execution_id)
                    .where(
                        runtime_containment_records.c.organization_id == org_id,
                        runtime_containment_records.c.state != "CONTAINED",
                    )
                    .limit(1)
                )
                uncertain_effect = await connection.scalar(
                    select(runtime_execution_attempts.c.attempt_id)
                    .where(
                        runtime_execution_attempts.c.organization_id == org_id,
                        (
                            runtime_execution_attempts.c.state.in_(
                                ("ADMITTED", "BACKEND_STARTING", "RUNNING", "UNCERTAIN")
                            )
                            | runtime_execution_attempts.c.effect_state.in_(
                                ("EFFECT_STARTING", "EFFECT_TRANSMITTING", "EFFECT_UNCERTAIN")
                            )
                        ),
                    )
                    .limit(1)
                )
            if unresolved is not None:
                raise TenantDeletionError("Containment unconfirmed in durable execution journal")
            if uncertain_effect is not None:
                raise TenantDeletionError("Containment unconfirmed: execution outcome is uncertain")
        except TenantDeletionError:
            raise
        except Exception as exc:
            raise TenantDeletionError("Containment unconfirmed during tenant deletion") from exc

    async def _owned_approval_ids(self, conn, org_id: str) -> set[str]:
        rows = await conn.execute(
            select(governance_approvals.c.id).where(governance_approvals.c.org_id == org_id)
        )
        return {row[0] for row in rows}

    async def _referenced_approval_ids(self, conn, owned: set[str]) -> set[str]:
        """Approval ids held by restrictive foreign keys. Requests stay immutable."""
        if not owned:
            return set()
        referenced: set[str] = set()
        for column in (
            runtime_execution_requests.c.approval_id,
            governance_execution_authorizations.c.approval_id,
        ):
            rows = await conn.execute(select(column).where(column.in_(owned)))
            referenced.update(row[0] for row in rows if row[0])
        return referenced

    async def _revoke_referenced_authority(
        self, org_id: str, deleted_by: str, resolved_at: str
    ) -> int:
        """Commit revocation before any erasure that can roll back.

        Referenced approvals become REVOKED and are never returned to APPROVED.
        Issued authorizations are consumed and pre-effect admission is closed.
        Immutable execution requests and restrictive foreign keys are not modified.
        """
        stamp = _now_dt()
        async with self._engine.raw.begin() as conn:
            owned = await self._owned_approval_ids(conn, org_id)
            referenced = await self._referenced_approval_ids(conn, owned)
            if referenced:
                await conn.execute(
                    update(governance_approvals)
                    .where(
                        governance_approvals.c.id.in_(referenced),
                        governance_approvals.c.org_id == org_id,
                        governance_approvals.c.status != "REVOKED",
                    )
                    .values(
                        status="REVOKED",
                        resolved_by=deleted_by,
                        resolved_at=resolved_at,
                        resolution_notes=_REVOCATION_NOTE,
                    )
                )
            await conn.execute(
                update(governance_execution_authorizations)
                .where(
                    governance_execution_authorizations.c.organization_id == org_id,
                    governance_execution_authorizations.c.status == "ISSUED",
                )
                .values(status="CONSUMED", consumed_at=stamp)
            )
            await conn.execute(
                update(runtime_execution_attempts)
                .where(
                    runtime_execution_attempts.c.organization_id == org_id,
                    runtime_execution_attempts.c.state.in_(("PENDING", "LEASED")),
                )
                .values(
                    state="FAILED_PRE_EXECUTION",
                    pre_effect_decision="DENY_FAILED_PRE_EXECUTION",
                    failure_code="TENANT_DELETION",
                    failure_reason=_ADMISSION_CLOSED,
                    updated_at=stamp,
                )
            )
            await conn.execute(
                update(runtime_worker_leases)
                .where(
                    runtime_worker_leases.c.organization_id == org_id,
                    runtime_worker_leases.c.status == "ACTIVE",
                )
                .values(status="REVOKED", released_at=stamp)
            )
            await conn.execute(
                update(runtime_execution_dispatch_outbox)
                .where(
                    runtime_execution_dispatch_outbox.c.organization_id == org_id,
                    runtime_execution_dispatch_outbox.c.status.in_(("PENDING", "PUBLISHING")),
                )
                .values(status="CANCELLED", updated_at=stamp)
            )
            if not referenced:
                return 0
            remaining = await conn.execute(
                select(governance_approvals.c.id).where(
                    governance_approvals.c.id.in_(referenced),
                    governance_approvals.c.org_id == org_id,
                    governance_approvals.c.status == "REVOKED",
                )
            )
            return len(remaining.fetchall())

    async def _erase_operational_rows(self, org_id: str, purged_counts: dict[str, int]) -> None:
        """Delete eligible rows. Unreferenced approvals go only after their votes."""
        async with self._engine.raw.begin() as conn:
            await self._lock_unheld_tenant(conn, org_id)
            owned = await self._owned_approval_ids(conn, org_id)
            referenced = await self._referenced_approval_ids(conn, owned)
            unreferenced = owned - referenced
            if unreferenced:
                await conn.execute(
                    delete(governance_approval_votes).where(
                        governance_approval_votes.c.approval_id.in_(unreferenced)
                    )
                )
                deleted = await conn.execute(
                    delete(governance_approvals).where(
                        governance_approvals.c.id.in_(unreferenced),
                        governance_approvals.c.org_id == org_id,
                    )
                )
                purged_counts["governance_approvals"] = deleted.rowcount or 0
            else:
                purged_counts["governance_approvals"] = 0

            for tbl, name, col in _eligible_erasure_tables():
                col_attr = getattr(tbl.c, col)
                res = await conn.execute(delete(tbl).where(col_attr == org_id))
                purged_counts[name] = res.rowcount or 0

            await conn.execute(
                update(stripe_webhook_events)
                .where(stripe_webhook_events.c.org_id == org_id)
                .values(org_id=None)
            )

    async def _lock_unheld_tenant(self, conn, org_id: str) -> None:
        """Hold insertion and each destructive transaction share this row lock."""
        await conn.execute(
            select(organizations.c.id).where(organizations.c.id == org_id).with_for_update()
        )
        if await self._legal_hold.is_held(org_id, conn=conn):
            raise LegalHoldActiveError(f"Cannot delete tenant {org_id}: active legal hold exists")

    async def _register_tombstone(
        self,
        org_id: str,
        original_name: str,
        generation_id: str,
        deleted_by: str,
        now: str,
        details: dict,
    ) -> str:
        auth_hash = hashlib.sha256(f"{org_id}:{generation_id}:auth".encode()).hexdigest()
        ev_digest = hashlib.sha256(f"{org_id}:{generation_id}:evidence".encode()).hexdigest()
        async with self._engine.raw.begin() as conn:
            # Lock the stable parent, not an absent tombstone row. Concurrent
            # retries must observe and reuse the first committed tombstone.
            owner = await conn.scalar(
                select(organizations.c.id).where(organizations.c.id == org_id).with_for_update()
            )
            if owner is None:
                raise TenantDeletionError("Cannot publish tombstone without tenant identity")
            if await self._legal_hold.is_held(org_id, conn=conn):
                raise LegalHoldActiveError(
                    f"Cannot delete tenant {org_id}: active legal hold exists"
                )
            existing = (
                await conn.execute(
                    select(tenant_tombstones).where(tenant_tombstones.c.org_id == org_id)
                )
            ).fetchone()
            if existing is not None:
                if existing.generation_id != generation_id:
                    raise TenantDeletionError(
                        "Refusing to replace a protected tombstone generation"
                    )
                return str(existing.id)
            tombstone_id = str(uuid.uuid4())
            await conn.execute(
                insert(tenant_tombstones).values(
                    id=tombstone_id,
                    org_id=org_id,
                    original_name=original_name,
                    generation_id=generation_id,
                    tombstoned_at=now,
                    tombstoned_by=deleted_by,
                    authority_hash=auth_hash,
                    evidence_digest=ev_digest,
                    details_json=json.dumps(details),
                )
            )
            return tombstone_id

    async def _verify_no_eligible_residual(self, org_id: str) -> dict[str, int]:
        residual: dict[str, int] = {}
        async with self._engine.raw.connect() as conn:
            for tbl, name, col in _eligible_erasure_tables():
                col_attr = getattr(tbl.c, col)
                rows = (await conn.execute(select(tbl).where(col_attr == org_id))).fetchall()
                if rows:
                    residual[name] = len(rows)
            owned = await self._owned_approval_ids(conn, org_id)
            referenced = await self._referenced_approval_ids(conn, owned)
            approval_rows = (
                await conn.execute(
                    select(governance_approvals.c.id, governance_approvals.c.status).where(
                        governance_approvals.c.org_id == org_id
                    )
                )
            ).fetchall()
            ineligible = [
                row for row in approval_rows if row[0] not in referenced or row[1] != "REVOKED"
            ]
            if ineligible:
                residual["governance_approvals"] = len(ineligible)
        return residual

    async def delete_tenant(
        self,
        org_id: str,
        deleted_by: str,
        reason: str,
        require_sovereignty: bool = True,
    ) -> TenantDeletionResult:
        """Executes end-to-end governed deletion of an organization."""
        await assert_current_restore_readiness_admitted()

        if await self._legal_hold.is_held(org_id):
            raise LegalHoldActiveError(f"Cannot delete tenant {org_id}: active legal hold exists")

        if self._lifecycle_provider is None:
            store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH") or os.environ.get(
                "WHITEPACT_LIFECYCLE_STORE_PATH"
            )
            if store_b_path:
                try:
                    self._lifecycle_provider = DurableLifecycleStateProvider(store_b_path)
                except Exception:
                    pass

        now = _now()
        if self._lifecycle_provider is None:
            raise TenantDeletionError("Cannot delete an unestablished tenant without Store B")
        if not self._lifecycle_provider.verify_integrity():
            raise TenantDeletionError("Store B lifecycle integrity is unverified")
        established = self._lifecycle_provider.get_state(org_id)
        if established is None or established.tenant_id != org_id:
            raise TenantDeletionError("Cannot delete an unestablished tenant lifecycle")
        if established.state == LifecycleState.TOMBSTONED:
            raise TenantDeletionError("Tenant lifecycle is already tombstoned")
        generation_id = established.generation_id
        purged_counts: dict[str, int] = {}

        async with self._engine.raw.connect() as conn:
            org_row = (
                await conn.execute(select(organizations).where(organizations.c.id == org_id))
            ).fetchone()
            if not org_row:
                raise TenantDeletionError(f"Organization {org_id} does not exist")
            org_name = org_row.name

        # Forward security state recorded in independent CurrentLifecycleStateProvider BEFORE destructive actions
        if self._lifecycle_provider:
            self._lifecycle_provider.record_state(
                replace(
                    established,
                    state=LifecycleState.DELETION_IN_PROGRESS,
                    effective_at=now,
                    digest="",
                )
            )

        suffix = f"{_TOMBSTONE_SUFFIX}{generation_id}"
        if org_name.endswith(suffix):
            original_name = org_name[: -len(suffix)] or org_name
            quarantined_name = org_name
        else:
            original_name = org_name
            quarantined_name = f"{org_name}{suffix}"

        # Quarantine tenant and close admission. Never write governance_status back to ACTIVE.
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(name=quarantined_name, governance_status="DISABLED")
            )
            # Same org->epoch lock order as grant issuance/final effect CAS.
            # New authority either predates this quarantine and is revoked below,
            # or observes DISABLED; it cannot race in after the status commit.
            revoked_epoch = await bump_epoch_on_connection(conn, org_id)

        purged_counts["governance_approvals_revoked"] = await self._revoke_referenced_authority(
            org_id, deleted_by, now
        )
        await self._contain_inflight(org_id, revoked_epoch)

        # Immediate Revocation of credentials and sessions
        async with self._engine.raw.begin() as conn:
            await self._lock_unheld_tenant(conn, org_id)
            r_sess = await conn.execute(delete(web_sessions).where(web_sessions.c.org_id == org_id))
            purged_counts["web_sessions"] = r_sess.rowcount or 0

            r_iam_sess = await conn.execute(
                delete(iam_sessions).where(iam_sessions.c.org_id == org_id)
            )
            purged_counts["iam_sessions"] = r_iam_sess.rowcount or 0

            r_keys = await conn.execute(delete(org_api_keys).where(org_api_keys.c.org_id == org_id))
            purged_counts["org_api_keys"] = r_keys.rowcount or 0

            r_lineage = await conn.execute(
                delete(iam_api_key_lineage).where(iam_api_key_lineage.c.org_id == org_id)
            )
            purged_counts["iam_api_key_lineage"] = r_lineage.rowcount or 0

            r_jit = await conn.execute(
                delete(iam_jit_grants).where(iam_jit_grants.c.org_id == org_id)
            )
            purged_counts["iam_jit_grants"] = r_jit.rowcount or 0

            r_bg = await conn.execute(
                delete(iam_break_glass_sessions).where(iam_break_glass_sessions.c.org_id == org_id)
            )
            purged_counts["iam_break_glass_sessions"] = r_bg.rowcount or 0

            r_rec_p = await conn.execute(
                delete(iam_recovery_policies).where(iam_recovery_policies.c.org_id == org_id)
            )
            purged_counts["iam_recovery_policies"] = r_rec_p.rowcount or 0

            r_rec_c = await conn.execute(
                delete(iam_recovery_challenges).where(iam_recovery_challenges.c.org_id == org_id)
            )
            purged_counts["iam_recovery_challenges"] = r_rec_c.rowcount or 0

            r_nonces = await conn.execute(
                delete(iam_step_up_nonces).where(iam_step_up_nonces.c.org_id == org_id)
            )
            purged_counts["iam_step_up_nonces"] = r_nonces.rowcount or 0

        await self._erase_operational_rows(org_id, purged_counts)

        residual_found = await self._verify_no_eligible_residual(org_id)
        if residual_found:
            raise TenantResidualDataError(
                f"Post-deletion verification failed for {org_id}: residual rows {residual_found}"
            )

        # Recheck after erasure: late uncertainty must not become a success receipt.
        await self._contain_inflight(org_id, revoked_epoch)

        details = {
            "deleted_by": deleted_by,
            "reason": reason,
            "original_name": original_name,
            "purged_counts": purged_counts,
        }
        tombstone_id = await self._register_tombstone(
            org_id, original_name, generation_id, deleted_by, now, details
        )

        # Record TOMBSTONED only after erasure and verification, so a crash stays reconcilable.
        if self._lifecycle_provider:
            self._lifecycle_provider.record_state(
                replace(
                    established,
                    state=LifecycleState.TOMBSTONED,
                    effective_at=now,
                    digest="",
                )
            )

        return TenantDeletionResult(
            org_id=org_id,
            generation_id=generation_id,
            deleted_at=now,
            tombstone_id=tombstone_id,
            purged_tables=purged_counts,
            verification_passed=True,
        )
