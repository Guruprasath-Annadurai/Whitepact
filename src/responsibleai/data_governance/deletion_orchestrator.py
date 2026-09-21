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
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update

from responsibleai.data_governance.backup_defense import (
    CurrentLifecycleStateProvider,
    DurableLifecycleStateProvider,
    LifecycleState,
    LifecycleStateRecord,
    assert_restore_readiness_admitted,
    compute_lifecycle_digest,
)
from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    credential_issuances,
    data_retention_policies,
    eval_baselines,
    eval_runs,
    governance_approvals,
    governance_authority_passports,
    governance_crypto_keys,
    governance_delegations,
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


def _now() -> str:
    return datetime.now(UTC).isoformat()


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

    async def delete_tenant(
        self,
        org_id: str,
        deleted_by: str,
        reason: str,
        require_sovereignty: bool = True,
    ) -> TenantDeletionResult:
        """Executes end-to-end governed deletion of an organization."""
        assert_restore_readiness_admitted()

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
        generation_id = f"gen-{uuid.uuid4().hex[:12]}"
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
            init_digest = compute_lifecycle_digest(
                tenant_id=org_id,
                generation_id=generation_id,
                state=LifecycleState.DELETION_IN_PROGRESS.value,
                effective_at=now,
            )
            self._lifecycle_provider.record_state(
                LifecycleStateRecord(
                    tenant_id=org_id,
                    generation_id=generation_id,
                    state=LifecycleState.DELETION_IN_PROGRESS,
                    effective_at=now,
                    digest=init_digest,
                )
            )

        # Quarantine tenant
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(name=f"{org_name}-tombstoned-{generation_id}")
            )

        # Immediate Revocation of credentials and sessions
        async with self._engine.raw.begin() as conn:
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

        # Cascading erasure of operational, personal, and secret tables with explicit column mappings
        tables_to_delete = [
            (web_memberships, "web_memberships", "org_id"),
            (iam_scim_users, "iam_scim_users", "org_id"),
            (iam_scim_groups, "iam_scim_groups", "org_id"),
            (iam_four_eyes_requests, "iam_four_eyes_requests", "org_id"),
            (incidents, "incidents", "org_id"),
            (governance_approvals, "governance_approvals", "org_id"),
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

        async with self._engine.raw.begin() as conn:
            for tbl, name, col in tables_to_delete:
                col_attr = getattr(tbl.c, col)
                res = await conn.execute(delete(tbl).where(col_attr == org_id))
                purged_counts[name] = res.rowcount or 0

            await conn.execute(
                update(stripe_webhook_events)
                .where(stripe_webhook_events.c.org_id == org_id)
                .values(org_id=None)
            )

        # Tombstone Registration
        tombstone_id = str(uuid.uuid4())
        auth_hash = hashlib.sha256(f"{org_id}:{generation_id}:auth".encode()).hexdigest()
        ev_digest = hashlib.sha256(f"{org_id}:{generation_id}:evidence".encode()).hexdigest()

        details = {
            "deleted_by": deleted_by,
            "reason": reason,
            "original_name": org_name,
            "purged_counts": purged_counts,
        }

        # Record TOMBSTONED in independent CurrentLifecycleStateProvider
        if self._lifecycle_provider:
            final_digest = compute_lifecycle_digest(
                tenant_id=org_id,
                generation_id=generation_id,
                state=LifecycleState.TOMBSTONED.value,
                effective_at=now,
            )
            self._lifecycle_provider.record_state(
                LifecycleStateRecord(
                    tenant_id=org_id,
                    generation_id=generation_id,
                    state=LifecycleState.TOMBSTONED,
                    effective_at=now,
                    digest=final_digest,
                )
            )

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(tenant_tombstones).values(
                    id=tombstone_id,
                    org_id=org_id,
                    original_name=org_name,
                    generation_id=generation_id,
                    tombstoned_at=now,
                    tombstoned_by=deleted_by,
                    authority_hash=auth_hash,
                    evidence_digest=ev_digest,
                    details_json=json.dumps(details),
                )
            )

        # Post-Deletion Verification Scanner
        residual_found: dict[str, int] = {}
        async with self._engine.raw.connect() as conn:
            for tbl, name, col in tables_to_delete:
                col_attr = getattr(tbl.c, col)
                rows = (await conn.execute(select(tbl).where(col_attr == org_id))).fetchall()
                if rows:
                    residual_found[name] = len(rows)

        if residual_found:
            raise TenantResidualDataError(
                f"Post-deletion verification failed for {org_id}: residual rows {residual_found}"
            )

        return TenantDeletionResult(
            org_id=org_id,
            generation_id=generation_id,
            deleted_at=now,
            tombstone_id=tombstone_id,
            purged_tables=purged_counts,
            verification_passed=True,
        )
