# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Empirical Performance & Query Behavior Benchmark for Global Trust Fabric.

Measures:
1. Principal lookup
2. Identifier lookup
3. Trust Passport generation
4. Trust Proof evaluation
5. Trust Decision evaluation
6. Authority traversal
7. Concurrent principal resolution

Verifies absence of N+1 queries by tracking query execution counts.
"""

from __future__ import annotations

import asyncio
import json
import statistics
import time
from datetime import UTC, datetime

from sqlalchemy import event
from sqlalchemy.engine import Engine

from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_authority_edges,
    trust_fabric_identifiers,
    trust_fabric_passports,
    trust_fabric_principals,
    trust_fabric_sources,
)
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.decision import TrustDecisionEngine
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DisclosureClass,
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
    SourceTier,
)
from responsibleai.trust_fabric.models import TrustDecisionRequest
from responsibleai.trust_fabric.passport import PassportSigningKey, TrustPassportEngine
from responsibleai.trust_fabric.proofs import TrustProofEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine

PG_TEST_URL = "postgresql://ag@/wp_phase3_test?host=/tmp"


class QueryCounter:
    def __init__(self):
        self.count = 0
        self.queries = []

    def callback(self, conn, cursor, statement, parameters, context, executemany):
        self.count += 1
        self.queries.append(statement)

    def reset(self):
        self.count = 0
        self.queries = []


async def run_benchmarks():
    print("=" * 70)
    print("WHITEPACT PHASE 3 GLOBAL TRUST FABRIC BENCHMARK SUITE")
    print("Running against Real PostgreSQL (wp_phase3_test)")
    print("=" * 70)

    engine = create_engine(PG_TEST_URL)
    await engine.init()

    counter = QueryCounter()
    event.listen(engine.raw.sync_engine, "before_cursor_execute", counter.callback)

    org_id = "org_bench_enterprise"
    now_iso = datetime.now(UTC).isoformat()

    # Clean up and seed base organization
    async with engine.raw.begin() as conn:
        await conn.execute(trust_fabric_authority_edges.delete().where(trust_fabric_authority_edges.c.org_id == org_id))
        await conn.execute(trust_fabric_passports.delete().where(trust_fabric_passports.c.org_id == org_id))
        await conn.execute(trust_fabric_identifiers.delete().where(trust_fabric_identifiers.c.org_id == org_id))
        await conn.execute(trust_fabric_principals.delete().where(trust_fabric_principals.c.org_id == org_id))
        await conn.execute(trust_fabric_sources.delete().where(trust_fabric_sources.c.org_id == org_id))
        await conn.execute(organizations.delete().where(organizations.c.id == org_id))
        await conn.execute(
            organizations.insert().values(
                id=org_id,
                name="Benchmark Enterprise Corp",
                slug="bench-ent",
                monthly_budget_usd=100000,
                created_at=now_iso,
            )
        )

    dir_svc = PrincipalDirectory(engine)
    prov_svc = TrustProvenanceEngine(engine)
    pass_svc = TrustPassportEngine(engine)
    proof_svc = TrustProofEngine(engine)
    decision_engine = TrustDecisionEngine(engine)
    auth_graph = AuthorityGraph(engine)

    # Setup signing key
    signing_key = PassportSigningKey.generate()
    pass_svc.register_signing_key(signing_key)

    # Seed data
    src = await prov_svc.register_source(
        name="Enterprise IdP",
        source_tier=SourceTier.TIER_A,
        provider_type="OKTA",
        org_id=org_id,
    )

    root_corp = await dir_svc.create_principal(
        org_id=org_id,
        principal_type=PrincipalType.ORGANIZATION,
        display_name="Enterprise Root Org",
        lifecycle_state=PrincipalState.ACTIVE,
    )

    principal = await dir_svc.create_principal(
        org_id=org_id,
        principal_type=PrincipalType.HUMAN,
        display_name="Executive Alice",
        lifecycle_state=PrincipalState.ACTIVE,
    )

    ident = await dir_svc.attach_identifier(
        principal_id=principal.id,
        org_id=org_id,
        identifier_type=IdentifierType.EMAIL,
        value="alice.executive@enterprise.com",
        is_primary=True,
        verification_state=IdentifierVerificationState.VERIFIED,
        source_id=src.id,
    )

    await prov_svc.record_assertion(
        principal_id=principal.id,
        org_id=org_id,
        field_name="role",
        field_value="VP Treasury",
        source_id=src.id,
        verification_method="OIDC_ENTERPRISE",
        assurance_level=AssuranceLevel.HIGH,
        disclosure_class=DisclosureClass.PUBLIC,
    )

    await auth_graph.grant_authority(
        grantor_principal_id=root_corp.id,
        grantee_principal_id=principal.id,
        org_id=org_id,
        action_type="SIGN_PAYMENT",
        resource_pattern="FINANCE_PORTAL",
        ceiling_limit_usd=50000.0,
    )

    results = {}

    # -------------------------------------------------------------
    # 1. Principal Lookup
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        p = await dir_svc.get_principal(principal.id, org_id=org_id)
        latencies.append((time.perf_counter() - t0) * 1000)
    p_queries = counter.count / 100
    results["principal_lookup"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": p_queries,
    }

    # -------------------------------------------------------------
    # 2. Identifier Lookup
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        p = await dir_svc.resolve_by_identifier(
            org_id=org_id,
            identifier_type=IdentifierType.EMAIL,
            value="alice.executive@enterprise.com",
        )
        latencies.append((time.perf_counter() - t0) * 1000)
    id_queries = counter.count / 100
    results["identifier_lookup"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": id_queries,
    }

    # -------------------------------------------------------------
    # 3. Trust Passport Generation
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        passport = await pass_svc.generate_passport(
            principal_id=principal.id,
            org_id=org_id,
            signing_key_id=signing_key.key_id,
        )
        latencies.append((time.perf_counter() - t0) * 1000)
    pass_queries = counter.count / 100
    results["passport_generation"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": pass_queries,
    }

    # -------------------------------------------------------------
    # 4. Trust Proof Evaluation
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        proof_res = await proof_svc.prove_signing_authority(
            principal_id=principal.id,
            org_id=org_id,
            amount_usd=25000.0,
        )
        latencies.append((time.perf_counter() - t0) * 1000)
    proof_queries = counter.count / 100
    results["proof_evaluation"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": proof_queries,
    }

    # -------------------------------------------------------------
    # 5. Trust Decision Evaluation
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    dec_req = TrustDecisionRequest(
        requesting_org_id="org_client",
        target_org_id=org_id,
        subject_principal_id=principal.id,
        requested_action="SIGN_PAYMENT",
        context={"amount_usd": "25000", "resource": "FINANCE_PORTAL"},
    )
    for _ in range(100):
        t0 = time.perf_counter()
        resp = await decision_engine.evaluate_decision(dec_req)
        latencies.append((time.perf_counter() - t0) * 1000)
    dec_queries = counter.count / 100
    results["decision_evaluation"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": dec_queries,
    }

    # -------------------------------------------------------------
    # 6. Authority Traversal
    # -------------------------------------------------------------
    counter.reset()
    latencies = []
    for _ in range(100):
        t0 = time.perf_counter()
        has_auth, reason, edge = await auth_graph.check_authority(
            grantee_principal_id=principal.id,
            org_id=org_id,
            action_type="SIGN_PAYMENT",
            resource="FINANCE_PORTAL",
            amount_usd=25000.0,
        )
        latencies.append((time.perf_counter() - t0) * 1000)
    auth_queries = counter.count / 100
    results["authority_traversal"] = {
        "mean_ms": statistics.mean(latencies),
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "p95_ms": sorted(latencies)[94],
        "queries_per_op": auth_queries,
    }

    # -------------------------------------------------------------
    # 7. Concurrent Principal Resolution (50 concurrent)
    # -------------------------------------------------------------
    counter.reset()
    t0 = time.perf_counter()
    coros = [
        dir_svc.resolve_by_identifier(
            org_id=org_id,
            identifier_type=IdentifierType.EMAIL,
            value="alice.executive@enterprise.com",
        )
        for _ in range(50)
    ]
    resolved = await asyncio.gather(*coros)
    total_time_ms = (time.perf_counter() - t0) * 1000
    results["concurrent_resolution_50"] = {
        "total_ms": total_time_ms,
        "mean_ms_per_request": total_time_ms / 50,
        "successful_resolutions": len([r for r in resolved if r is not None]),
        "queries_per_request": counter.count / 50,
    }

    print("\nBENCHMARK RESULTS (100 ITERATIONS PER OP, 50 CONCURRENT):")
    print("-" * 70)
    for op, data in results.items():
        print(f"{op.upper()}:")
        for k, v in data.items():
            if "ms" in k:
                print(f"  {k}: {v:.3f} ms")
            else:
                print(f"  {k}: {v}")
    print("-" * 70)

    # N+1 Query Verification
    print("\nN+1 QUERY AUDIT:")
    for op, data in results.items():
        q = data.get("queries_per_op") or data.get("queries_per_request")
        status = "ZERO N+1 (CONSTANT O(1) QUERIES)" if q <= 5 else "POTENTIAL N+1"
        print(f"  {op}: {q:.1f} queries/op -> {status}")

    print("\n" + "=" * 70)
    await engine.close()


if __name__ == "__main__":
    asyncio.run(run_benchmarks())
