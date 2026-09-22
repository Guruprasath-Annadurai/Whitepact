# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Mapping from Sovereign facts to canonical WhitePact persistence.

SOVEREIGN SOURCE MAP (RC 683d1c3 — authoritative unless noted)

| Sovereign fact              | Canonical source                         | Repository/service              | Persisted | Tenant key   |
|-----------------------------|------------------------------------------|---------------------------------|-----------|--------------|
| Organization                | organizations table                      | OrgRepository                   | yes       | org_id       |
| API key / human identity    | org_api_keys                             | OrgRepository.list_keys         | yes       | org_id       |
| Verified principal          | verified_principals                      | PrincipalRepository             | yes       | org_id       |
| Delegation / authority chain| governance_delegations                   | DelegationRepository            | yes       | org_id       |
| Org authority ceiling       | org_authority_ceilings                   | OrgAuthorityCeilingRepository   | yes       | org_id       |
| Policy rules                | governance_policies                      | PolicyRepository                | yes       | org_id       |
| Approval requests           | governance_approvals                     | ApprovalRepository              | yes       | org_id       |
| Approval votes              | governance_approval_votes                | ApprovalRepository.list_votes   | yes       | via approval |
| Governance evidence         | governance_evidence                      | EvidenceRepository              | yes       | org_id       |
| Outcomes                    | governance_outcomes                      | OutcomeRepository               | yes       | org_id       |
| Revocation epoch            | governance_revocation_epochs             | RevocationEpochRepository       | yes       | org_id       |
| Execution grants (durable)  | governance_execution_authorizations      | runtime/authority_kernel (SQL)  | yes       | org_id       |
| Runtime effects/attempts    | runtime_execution_* tables               | runtime/authority_kernel        | yes       | org_id       |
| Web humans / SSO            | web identity tables                      | WebIdentityRepository           | yes       | org_id       |
| Intent contracts            | intent_contracts                         | IntentContractRepository        | yes       | org_id       |
| Tool/MCP upstream trust     | upstream + tool_trust tables             | Upstream/ToolTrust repos        | yes       | org_id       |
| Judgment (in-memory)        | DecisionResult at evaluate time          | WhitePactRuntimeGateway         | derived   | org_id       |
| Transitive reachability     | Delegation graph walk                    | DelegationRepository.get_org_graph | derived | org_id    |
| Historical policy at T      | Not snapshotted per evidence row alone   | —                               | partial   | UNKNOWN      |
| Reconciliation state        | outcome + runtime attempt state          | OutcomeRepository + runtime     | partial   | org_id       |

Limitations: Sovereign does not invent facts missing from persistence. Historical
policy version may be referenced on evidence rows (`policy_version`) but full
rule bodies at time T are not always reconstructable — mark MISSING/UNKNOWN.
"""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.db import (
    ApprovalRepository,
    DatabaseEngine,
    DelegationRepository,
    EvidenceRepository,
    OrgAuthorityCeilingRepository,
    OrgRepository,
    OutcomeRepository,
    PolicyRepository,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.shadow_observation_repository import ShadowObservationRepository


@dataclass
class SovereignCanonicalStore:
    """Read-only bundle of canonical repositories for Sovereign Phase B."""

    engine: DatabaseEngine
    orgs: OrgRepository
    delegations: DelegationRepository
    policies: PolicyRepository
    approvals: ApprovalRepository
    evidence: EvidenceRepository
    outcomes: OutcomeRepository
    ceilings: OrgAuthorityCeilingRepository
    revocation_epochs: RevocationEpochRepository
    shadow_observations: ShadowObservationRepository

    @classmethod
    def from_engine(cls, engine: DatabaseEngine) -> SovereignCanonicalStore:
        return cls(
            engine=engine,
            orgs=OrgRepository(engine),
            delegations=DelegationRepository(engine),
            policies=PolicyRepository(engine),
            approvals=ApprovalRepository(engine),
            evidence=EvidenceRepository(engine),
            outcomes=OutcomeRepository(engine),
            ceilings=OrgAuthorityCeilingRepository(engine),
            revocation_epochs=RevocationEpochRepository(engine),
            shadow_observations=ShadowObservationRepository(engine),
        )
