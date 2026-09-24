# Branch coverage gap report

Source: `coverage.json`

## Totals

- Pure branch coverage: **80.53%** (4745/5892)
- OpenSSF required: **80.00%**
- Gap: **0.00** percentage points
- Branches to cover (approx): **0** for 80.5% buffer target

## Production files (sorted by missing branches)

| File | Total | Covered | Missing | Branch % | Criticality | Sample missing lines |
|------|------:|--------:|--------:|---------:|:-----------:|----------------------|
| `src/responsibleai/dashboard/app.py` | 734 | 529 | 205 | 72.1% | P1 | 305, 637, 638, 639, 905, 1383, 1437, 1443, … |
| `src/responsibleai/enterprise/security/service.py` | 256 | 206 | 50 | 80.5% | P0 | 463, 646, 651, 795, 809, 864, 865, 868, … |
| `src/responsibleai/enterprise/service.py` | 192 | 153 | 39 | 79.7% | P2 | 303, 374, 527, 566, 567, 599, 620, 708, … |
| `src/responsibleai/mcp/server.py` | 158 | 138 | 20 | 87.3% | P1 | 326, 327, 334, 335, 336, 341, 342, 343, … |
| `src/responsibleai/data_governance/backup_defense.py` | 120 | 101 | 19 | 84.2% | P2 | 214, 232, 233, 238, 259, 297, 385, 404, … |
| `src/responsibleai/trust_fabric/passport.py` | 60 | 41 | 19 | 68.3% | P2 | 97, 187, 197, 198, 201, 202, 203, 266, … |
| `src/responsibleai/mcp/governance_integration.py` | 66 | 48 | 18 | 72.7% | P1 | 275, 276, 350, 352, 354, 386, 391, 449, … |
| `src/responsibleai/auth/mcp_oauth.py` | 78 | 61 | 17 | 78.2% | P0 | 156, 161, 199, 211, 233, 246, 247, 267, … |
| `src/responsibleai/enterprise/security/oauth.py` | 36 | 19 | 17 | 52.8% | P0 | 79, 81, 83, 84, 85, 86, 91, 121, … |
| `src/responsibleai/enterprise/security/oidc.py` | 54 | 37 | 17 | 68.5% | P0 | 72, 73, 74, 75, 76, 77, 78, 100, … |
| `src/responsibleai/enterprise/issuance.py` | 40 | 25 | 15 | 62.5% | P2 | 117, 121, 125, 127, 129, 134, 136, 140, … |
| `src/responsibleai/governance/authority_resolver.py` | 38 | 23 | 15 | 60.5% | P0 | 79, 80, 104, 119, 120, 121, 122, 124, … |
| `src/responsibleai/sovereign/cli_core.py` | 50 | 35 | 15 | 70.0% | P2 | 80, 81, 90, 92, 96, 97, 106, 140, … |
| `src/responsibleai/enterprise/security/policy.py` | 26 | 12 | 14 | 46.2% | P1 | 122, 151, 154, 155, 173, 174, 175, 182, … |
| `src/responsibleai/runtime/authority_kernel.py` | 116 | 102 | 14 | 87.9% | P0 | 174, 175, 423, 433, 456, 478, 481, 745, … |
| `src/responsibleai/trust_fabric/conflict.py` | 40 | 26 | 14 | 65.0% | P2 | 71, 73, 75, 77, 79, 81, 85, 89, … |
| `src/responsibleai/db/schema_preflight.py` | 36 | 23 | 13 | 63.9% | P2 | 21, 22, 23, 24, 33, 116, 120, 131, … |
| `src/responsibleai/enterprise/security/four_eyes.py` | 38 | 25 | 13 | 65.8% | P0 | 99, 103, 125, 126, 155, 171, 186, 232, … |
| `src/responsibleai/enterprise/verification.py` | 44 | 31 | 13 | 70.5% | P2 | 102, 103, 151, 152, 153, 154, 155, 166, … |
| `src/responsibleai/isolation/filesystem.py` | 46 | 33 | 13 | 71.7% | P2 | 46, 87, 88, 89, 111, 112, 121, 124, … |
| `src/responsibleai/sovereign/authority_engine.py` | 30 | 17 | 13 | 56.7% | P0 | 122, 145, 153, 161, 171, 182, 197, 198, … |
| `src/responsibleai/trust_fabric/models.py` | 14 | 1 | 13 | 7.1% | P2 | 77, 108, 139, 172, 209, 210, 211, 212, … |
| `src/responsibleai/db/org_repository.py` | 72 | 60 | 12 | 83.3% | P2 | 111, 112, 113, 301, 381, 382, 383, 441, … |
| `src/responsibleai/net/egress.py` | 78 | 66 | 12 | 84.6% | P2 | 125, 151, 152, 166, 179, 180, 255, 256, … |
| `src/responsibleai/sovereign/policy_lab.py` | 18 | 6 | 12 | 33.3% | P1 | 84, 85, 86, 87, 88, 129, 130, 138, … |
| `src/responsibleai/db/web_identity_repository.py` | 90 | 79 | 11 | 87.8% | P2 | 729, 843, 888, 924, 938, 1043, 1056, 1057, … |
| `src/responsibleai/enterprise/security/router.py` | 12 | 1 | 11 | 8.3% | P0 | 94, 101, 102, 103, 106, 107, 108, 115, … |
| `src/responsibleai/iam/step_up.py` | 58 | 47 | 11 | 81.0% | P2 | 102, 172, 177, 212, 217 |
| `src/responsibleai/sovereign/xray_builder.py` | 44 | 33 | 11 | 75.0% | P2 | 52, 131, 132, 133, 135, 136, 137, 261, … |
| `src/responsibleai/trust_fabric/federation.py` | 48 | 37 | 11 | 77.1% | P2 | 164, 294, 299, 315, 321, 352, 353 |
| `src/responsibleai/enterprise/security/assurance.py` | 32 | 22 | 10 | 68.8% | P0 | 95, 97, 122, 124, 127, 128, 129, 130, … |
| `src/responsibleai/iam/recovery.py` | 28 | 18 | 10 | 64.3% | P2 | 47, 49, 120, 173, 177, 188, 196, 247, … |
| `src/responsibleai/sovereign/debugger.py` | 20 | 10 | 10 | 50.0% | P2 | 62, 71, 103, 104, 105, 113, 115, 118, … |
| `src/responsibleai/sovereign/trace_builder.py` | 30 | 20 | 10 | 66.7% | P2 | 56, 59, 161, 164, 210, 242, 303, 306, … |
| `src/responsibleai/trust_fabric/bootstrap.py` | 38 | 28 | 10 | 73.7% | P2 | 78, 94, 105, 106, 107, 109, 110, 111, … |
| `src/responsibleai/trust_fabric/proofs.py` | 70 | 60 | 10 | 85.7% | P2 | 135, 164, 166, 189, 191, 253, 281, 288, … |
| `src/responsibleai/isolation/container_backend.py` | 50 | 41 | 9 | 82.0% | P2 | 130, 147, 148, 160, 161, 279, 280, 283, … |
| `src/responsibleai/sovereign/simulation.py` | 50 | 41 | 9 | 82.0% | P2 | 99, 148, 149, 159, 160, 284 |
| `src/responsibleai/trust_fabric/provenance.py` | 22 | 13 | 9 | 59.1% | P2 | 106, 116, 254, 257, 260, 262, 300, 302, … |
| `src/responsibleai/dashboard/middleware.py` | 38 | 30 | 8 | 78.9% | P2 | 65, 66, 67, 83, 87, 88, 89, 104, … |
| `src/responsibleai/db/delegation_repository.py` | 42 | 34 | 8 | 81.0% | P2 | 198, 224, 234, 235, 242, 284, 361, 377, … |
| `src/responsibleai/iam/guard.py` | 66 | 58 | 8 | 87.9% | P2 | 203, 209, 251, 283, 307 |
| `src/responsibleai/sovereign/flight_recorder.py` | 8 | 0 | 8 | 0.0% | P2 | 48, 49, 50, 51, 52, 53, 54, 55, … |
| `src/responsibleai/trust_fabric/authority_graph.py` | 32 | 24 | 8 | 75.0% | P0 | 72, 81, 129, 162, 238, 293, 295, 297 |
| `src/responsibleai/billing/paddle_service.py` | 30 | 23 | 7 | 76.7% | P1 | 78, 92, 99, 125, 136 |
| `src/responsibleai/enterprise/security/rate_limit.py` | 16 | 9 | 7 | 56.2% | P0 | 51, 52, 67, 77, 79, 108, 109, 110, … |
| `src/responsibleai/governance/authority_lattice.py` | 66 | 59 | 7 | 89.4% | P0 | 218, 234, 276, 410, 412, 414 |
| `src/responsibleai/governance/policy_lifecycle.py` | 44 | 37 | 7 | 84.1% | P1 | 90, 92, 94, 336, 356, 383 |
| `src/responsibleai/mcp/upstream_dispatch.py` | 16 | 9 | 7 | 56.2% | P1 | 112, 113, 119, 346, 360, 371, 385, 395, … |
| `src/responsibleai/runtime/gate.py` | 20 | 13 | 7 | 65.0% | P2 | 36, 42, 50, 65 |
| `src/responsibleai/sovereign/gauntlet_orchestrator.py` | 20 | 13 | 7 | 65.0% | P2 | 52, 54, 59, 60, 64, 65, 103, 104, … |
| `src/responsibleai/auth/oidc.py` | 38 | 32 | 6 | 84.2% | P0 | 108, 110, 153, 200, 202, 203, 227 |
| `src/responsibleai/enterprise/security/preflight.py` | 30 | 24 | 6 | 80.0% | P0 | 109, 114, 131 |
| `src/responsibleai/enterprise/security/webauthn.py` | 44 | 38 | 6 | 86.4% | P0 | 80, 94, 95, 104, 106, 179, 183, 187 |
| `src/responsibleai/runtime/capacity_reservation.py` | 16 | 10 | 6 | 62.5% | P2 | 111, 133, 134, 135, 141, 174, 175, 176, … |
| `src/responsibleai/sovereign/router.py` | 6 | 0 | 6 | 0.0% | P2 | 35, 43, 44, 45, 46, 47, 48, 49, … |
| `src/responsibleai/webhooks/manager.py` | 76 | 70 | 6 | 92.1% | P2 | 68, 69, 122, 326 |
| `src/responsibleai/auth/verifiable_credential.py` | 24 | 19 | 5 | 79.2% | P0 | 78, 79, 85, 86, 120, 121, 144, 156, … |
| `src/responsibleai/enterprise/router.py` | 16 | 11 | 5 | 68.8% | P2 | 98, 123, 125, 126, 142, 143, 144, 156, … |
| `src/responsibleai/eval/regression.py` | 18 | 13 | 5 | 72.2% | P2 | 52, 72, 78, 97 |
| `src/responsibleai/governance/approval.py` | 14 | 9 | 5 | 64.3% | P1 | 308, 310, 312, 314, 318, 319 |
| `src/responsibleai/governance/authority_passport.py` | 28 | 23 | 5 | 82.1% | P0 | 110, 112, 114, 293 |
| `src/responsibleai/isolation/broker.py` | 20 | 15 | 5 | 75.0% | P2 | 52, 53, 54, 82, 83, 85, 108 |
| `src/responsibleai/isolation/subprocess_backend.py` | 12 | 7 | 5 | 58.3% | P2 | 42, 90, 91, 93, 94, 95, 96, 98, … |
| `src/responsibleai/mcp/resources.py` | 24 | 19 | 5 | 79.2% | P1 | 285, 351, 390, 442, 574 |
| `src/responsibleai/sovereign/evidence_correlation.py` | 6 | 1 | 5 | 16.7% | P1 | 40, 41, 42, 49, 50, 57, 58, 59, … |
| `src/responsibleai/sovereign/web_routes.py` | 12 | 7 | 5 | 58.3% | P2 | 69, 70, 90, 91, 94, 145, 146, 168, … |
| `src/responsibleai/dashboard/plan_rate_limiter.py` | 14 | 10 | 4 | 71.4% | P2 | 60, 61, 62, 64, 65, 79, 102, 103, … |
| `src/responsibleai/data_governance/deletion_orchestrator.py` | 20 | 16 | 4 | 80.0% | P2 | 137, 138, 139, 140, 151, 323, 326 |
| `src/responsibleai/db/evidence_repository.py` | 34 | 30 | 4 | 88.2% | P1 | 124, 232, 431, 450, 477, 478 |
| `src/responsibleai/db/migrate.py` | 16 | 12 | 4 | 75.0% | P2 | 64, 88 |
| `src/responsibleai/iam/jit.py` | 12 | 8 | 4 | 66.7% | P2 | 41, 52, 109, 118, 149, 150, 151, 161 |
| `src/responsibleai/iam/scim.py` | 12 | 8 | 4 | 66.7% | P2 | 47, 74, 157, 221, 222, 223, 225, 226, … |
| `src/responsibleai/sovereign/devconfig.py` | 4 | 0 | 4 | 0.0% | P2 | 5, 7, 8, 9, 11, 12, 13, 16, … |
| `src/responsibleai/sovereign/manifest.py` | 8 | 4 | 4 | 50.0% | P2 | 63, 67, 78, 81, 82 |
| `src/responsibleai/sovereign/redaction.py` | 32 | 28 | 4 | 87.5% | P1 | 44, 47, 76, 83 |
| `src/responsibleai/cost/analyzer.py` | 20 | 17 | 3 | 85.0% | P2 | 287 |
| `src/responsibleai/data_governance/classification.py` | 4 | 1 | 3 | 25.0% | P2 | 992, 993, 996 |
| `src/responsibleai/data_governance/erasure.py` | 10 | 7 | 3 | 70.0% | P2 | 134, 219, 224, 225, 226, 235 |
| `src/responsibleai/data_governance/retention.py` | 10 | 7 | 3 | 70.0% | P2 | 73, 81, 82, 108, 109, 116 |
| `src/responsibleai/db/encryption.py` | 26 | 23 | 3 | 88.5% | P2 | 99, 201, 218 |
| `src/responsibleai/db/paddle_billing_repository.py` | 12 | 9 | 3 | 75.0% | P1 | 73 |
| `src/responsibleai/db/public_incident_repository.py` | 26 | 23 | 3 | 88.5% | P2 | 184, 186, 192, 193 |
| `src/responsibleai/db/repositories.py` | 40 | 37 | 3 | 92.5% | P2 | 259 |
| `src/responsibleai/db/revocation_epoch_repository.py` | 6 | 3 | 3 | 50.0% | P0 | 25, 28, 75 |
| `src/responsibleai/db/root_authority_repository.py` | 6 | 3 | 3 | 50.0% | P0 | 57, 59, 125 |
| `src/responsibleai/db/upstream_repository.py` | 8 | 5 | 3 | 62.5% | P2 | 23, 131 |
| `src/responsibleai/enterprise/security/providers.py` | 6 | 3 | 3 | 50.0% | P0 | 51, 55, 56, 57, 58, 66 |
| `src/responsibleai/eval/models.py` | 24 | 21 | 3 | 87.5% | P2 | 102, 104, 303 |
| `src/responsibleai/governance/ceiling.py` | 8 | 5 | 3 | 62.5% | P2 | 61, 63, 65 |
| `src/responsibleai/iam/four_eyes.py` | 8 | 5 | 3 | 62.5% | P2 | 108, 119, 122 |
| `src/responsibleai/iam/session.py` | 10 | 7 | 3 | 70.0% | P0 | 78, 80, 82, 121, 122, 124, 125, 135 |
| `src/responsibleai/mcp/tools.py` | 110 | 107 | 3 | 97.3% | P1 | 1496, 1864, 1865, 1866, 1867, 1869, 1870, 1871, … |
| `src/responsibleai/sovereign/authority_bom.py` | 4 | 1 | 3 | 25.0% | P0 | 38, 39, 40, 43 |
| `src/responsibleai/sovereign/service.py` | 14 | 11 | 3 | 78.6% | P2 | 116, 117, 121, 131, 229, 230, 242, 292, … |
| `src/responsibleai/sovereign/web_auth.py` | 14 | 11 | 3 | 78.6% | P0 | 37, 39, 53 |
| `src/responsibleai/trust_fabric/monitor.py` | 12 | 9 | 3 | 75.0% | P2 | 113, 393, 394 |
| `src/responsibleai/compliance/engine.py` | 32 | 30 | 2 | 93.8% | P2 | 217, 222 |
| `src/responsibleai/cost/tracker.py` | 12 | 10 | 2 | 83.3% | P2 | 81, 82, 83, 156, 268, 277 |
| `src/responsibleai/dashboard/paddle_csp.py` | 12 | 10 | 2 | 83.3% | P1 | 49 |
| `src/responsibleai/dashboard/transactional_email.py` | 10 | 8 | 2 | 80.0% | P2 | 77, 78, 114 |
| `src/responsibleai/dashboard/websocket_manager.py` | 22 | 20 | 2 | 90.9% | P2 | — |
| `src/responsibleai/db/approval_repository.py` | 30 | 28 | 2 | 93.3% | P1 | 366, 367, 447 |
| `src/responsibleai/db/consent_proof_repository.py` | 4 | 2 | 2 | 50.0% | P2 | 62, 139 |
| `src/responsibleai/db/execution_nonce_repository.py` | 10 | 8 | 2 | 80.0% | P1 | 40, 71 |
| `src/responsibleai/db/incident_repository.py` | 6 | 4 | 2 | 66.7% | P2 | 91, 95, 102, 103, 104, 105 |
| `src/responsibleai/enterprise/eligibility.py` | 2 | 0 | 2 | 0.0% | P2 | 69, 77, 78, 79 |
| `src/responsibleai/eval/benchmarks.py` | 24 | 22 | 2 | 91.7% | P2 | 404, 434 |
| `src/responsibleai/governance/context.py` | 8 | 6 | 2 | 75.0% | P2 | 48, 77 |
| `src/responsibleai/governance/evidence_bundle.py` | 14 | 12 | 2 | 85.7% | P1 | 53, 64, 190 |
| `src/responsibleai/hallucination/detector.py` | 16 | 14 | 2 | 87.5% | P2 | 57, 153, 159, 160 |
| `src/responsibleai/iam/api_key.py` | 4 | 2 | 2 | 50.0% | P2 | 50, 116, 151, 152, 153, 163, 173 |
| `src/responsibleai/iam/break_glass.py` | 10 | 8 | 2 | 80.0% | P2 | 47, 51 |
| `src/responsibleai/integrations/langgraph_gate.py` | 8 | 6 | 2 | 75.0% | P2 | 71, 80 |
| `src/responsibleai/leaderboard/runner.py` | 22 | 20 | 2 | 90.9% | P2 | 166, 204, 205, 206 |
| `src/responsibleai/sovereign/api_deps.py` | 4 | 2 | 2 | 50.0% | P2 | 21, 31, 40, 41, 42 |
| `src/responsibleai/sovereign/effective.py` | 10 | 8 | 2 | 80.0% | P2 | 43, 44, 45, 46 |
| `src/responsibleai/sovereign/observation.py` | 2 | 0 | 2 | 0.0% | P2 | 27, 35, 45, 48, 49, 50, 51, 52 |
| `src/responsibleai/sovereign/protocol.py` | 16 | 14 | 2 | 87.5% | P2 | 118, 145 |
| `src/responsibleai/sovereign/shadow_store.py` | 2 | 0 | 2 | 0.0% | P2 | 34, 35, 41, 42, 45, 46, 47, 48, … |
| `src/responsibleai/trust_fabric/directory.py` | 28 | 26 | 2 | 92.9% | P2 | 76 |
| `src/responsibleai/billing/stripe_service.py` | 28 | 27 | 1 | 96.4% | P1 | 213 |
| `src/responsibleai/cost/models.py` | 8 | 7 | 1 | 87.5% | P2 | 80, 173 |
| `src/responsibleai/dashboard/web_governance_contracts.py` | 4 | 3 | 1 | 75.0% | P2 | — |
| `src/responsibleai/data_governance/export.py` | 20 | 19 | 1 | 95.0% | P2 | 75, 105 |
| `src/responsibleai/data_governance/inventory.py` | 4 | 3 | 1 | 75.0% | P2 | 40 |
| `src/responsibleai/data_governance/legal_hold.py` | 6 | 5 | 1 | 83.3% | P2 | 112, 155, 156, 163 |
| `src/responsibleai/db/audit_repository.py` | 16 | 15 | 1 | 93.8% | P1 | — |
| `src/responsibleai/db/shadow_observation_repository.py` | 4 | 3 | 1 | 75.0% | P2 | 111 |
| `src/responsibleai/drift/monitor.py` | 20 | 19 | 1 | 95.0% | P2 | 87, 122, 123, 124, 307 |
| `src/responsibleai/enterprise/preflight.py` | 16 | 15 | 1 | 93.8% | P2 | — |
| `src/responsibleai/enterprise/runtime.py` | 2 | 1 | 1 | 50.0% | P2 | 30, 35, 36 |
| `src/responsibleai/eval/__init__.py` | 2 | 1 | 1 | 50.0% | P2 | 49 |
| `src/responsibleai/eval/comparator.py` | 8 | 7 | 1 | 87.5% | P2 | 67 |
| `src/responsibleai/governance/causal_influence.py` | 20 | 19 | 1 | 95.0% | P2 | 166 |
| `src/responsibleai/governance/evidence.py` | 12 | 11 | 1 | 91.7% | P1 | 114 |
| `src/responsibleai/governance/execution.py` | 32 | 31 | 1 | 96.9% | P1 | 326, 328 |
| `src/responsibleai/governance/reason_codes.py` | 2 | 1 | 1 | 50.0% | P2 | 154 |
| `src/responsibleai/governance/upstream_discovery.py` | 10 | 9 | 1 | 90.0% | P2 | 128, 130 |
| `src/responsibleai/governance/upstream_executor.py` | 12 | 11 | 1 | 91.7% | P2 | — |
| `src/responsibleai/iam/transfer.py` | 8 | 7 | 1 | 87.5% | P2 | 73 |
| `src/responsibleai/integrations/a2a_adapter.py` | 20 | 19 | 1 | 95.0% | P2 | 68 |
| `src/responsibleai/integrations/adk_toolset.py` | 2 | 1 | 1 | 50.0% | P2 | 65 |
| `src/responsibleai/integrations/langchain_middleware.py` | 6 | 5 | 1 | 83.3% | P2 | 54 |
| `src/responsibleai/redteam/simulator.py` | 8 | 7 | 1 | 87.5% | P2 | 64 |
| `src/responsibleai/sovereign/capsule.py` | 2 | 1 | 1 | 50.0% | P2 | 89 |
| `src/responsibleai/sovereign/gauntlet.py` | 2 | 1 | 1 | 50.0% | P2 | 38 |
| `src/responsibleai/sovereign/graph.py` | 4 | 3 | 1 | 75.0% | P2 | 93, 115 |
| `src/responsibleai/sovereign/tenant.py` | 4 | 3 | 1 | 75.0% | P0 | 22, 33 |
| `src/responsibleai/sovereign/time_machine.py` | 2 | 1 | 1 | 50.0% | P2 | 53, 54 |
| `src/responsibleai/streaming/scanner.py` | 10 | 9 | 1 | 90.0% | P2 | 132, 133, 134 |
| `src/responsibleai/trust/passport.py` | 2 | 1 | 1 | 50.0% | P2 | 165, 168 |
| `src/responsibleai/trust_fabric/decision.py` | 10 | 9 | 1 | 90.0% | P2 | 53 |
| `src/responsibleai/trust_fabric/provider.py` | 4 | 3 | 1 | 75.0% | P2 | 138 |
| `src/responsibleai/__init__.py` | 2 | 2 | 0 | 100.0% | P2 | 93 |
| `src/responsibleai/auth/crypto_policy.py` | 4 | 4 | 0 | 100.0% | P0 | — |
| `src/responsibleai/auth/mfa.py` | 6 | 6 | 0 | 100.0% | P0 | — |
| `src/responsibleai/auth/saml.py` | 50 | 50 | 0 | 100.0% | P0 | 204, 205, 245, 246, 418, 419 |
| `src/responsibleai/cost/router.py` | 6 | 6 | 0 | 100.0% | P2 | — |
| `src/responsibleai/dashboard/config.py` | 62 | 62 | 0 | 100.0% | P2 | — |
| `src/responsibleai/dashboard/logging_config.py` | 6 | 6 | 0 | 100.0% | P2 | 18, 26, 27, 28 |
| `src/responsibleai/dashboard/signup_guard.py` | 6 | 6 | 0 | 100.0% | P2 | — |
| `src/responsibleai/dashboard/telemetry.py` | 8 | 8 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/authority_passport_repository.py` | 4 | 4 | 0 | 100.0% | P0 | — |
| `src/responsibleai/db/engine.py` | 12 | 12 | 0 | 100.0% | P2 | 2758, 2769, 2770 |
| `src/responsibleai/db/eval_repository.py` | 10 | 10 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/intent_repository.py` | 2 | 2 | 0 | 100.0% | P2 | 31 |
| `src/responsibleai/db/leaderboard_repository.py` | 10 | 10 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/mcp_usage_repository.py` | 2 | 2 | 0 | 100.0% | P1 | — |
| `src/responsibleai/db/org_authority_ceiling_repository.py` | 2 | 2 | 0 | 100.0% | P0 | — |
| `src/responsibleai/db/org_autonomy_budget_repository.py` | 2 | 2 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/outcome_repository.py` | 4 | 4 | 0 | 100.0% | P2 | 23 |
| `src/responsibleai/db/passport_repository.py` | 2 | 2 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/policy_repository.py` | 8 | 8 | 0 | 100.0% | P1 | — |
| `src/responsibleai/db/tool_trust_repository.py` | 2 | 2 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/webhook_repository.py` | 8 | 8 | 0 | 100.0% | P2 | — |
| `src/responsibleai/db/workflow_rule_repository.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/enterprise/audit.py` | 2 | 2 | 0 | 100.0% | P1 | — |
| `src/responsibleai/enterprise/roles.py` | 2 | 2 | 0 | 100.0% | P2 | 197, 198 |
| `src/responsibleai/eval/dataset_scanner.py` | 24 | 24 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/authority_conflict_resolver.py` | 16 | 16 | 0 | 100.0% | P0 | — |
| `src/responsibleai/governance/authority_lifetime.py` | 4 | 4 | 0 | 100.0% | P0 | — |
| `src/responsibleai/governance/consent_proof.py` | 16 | 16 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/delegation.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/delegation_graph.py` | 14 | 14 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/delegation_kernel.py` | 12 | 12 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/gateway.py` | 68 | 68 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/heart_veto.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/intent.py` | 18 | 18 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/jit_credential.py` | 6 | 6 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/models.py` | 50 | 50 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/non_delegable_authority.py` | 8 | 8 | 0 | 100.0% | P0 | — |
| `src/responsibleai/governance/policy.py` | 10 | 10 | 0 | 100.0% | P1 | — |
| `src/responsibleai/governance/purpose_binding.py` | 10 | 10 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/reconciliation.py` | 6 | 6 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/revocation_kernel.py` | 4 | 4 | 0 | 100.0% | P0 | — |
| `src/responsibleai/governance/risk.py` | 4 | 4 | 0 | 100.0% | P1 | — |
| `src/responsibleai/governance/root_authority.py` | 30 | 30 | 0 | 100.0% | P0 | — |
| `src/responsibleai/governance/synthetic_counter.py` | 14 | 14 | 0 | 100.0% | P2 | 97, 98 |
| `src/responsibleai/governance/tool_trust.py` | 12 | 12 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/trust_integration.py` | 2 | 2 | 0 | 100.0% | P2 | — |
| `src/responsibleai/governance/workflow.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/guardrails/engine.py` | 28 | 28 | 0 | 100.0% | P2 | — |
| `src/responsibleai/integrations/client.py` | 14 | 14 | 0 | 100.0% | P2 | — |
| `src/responsibleai/integrations/identity_bridge.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/isolation/environment.py` | 14 | 14 | 0 | 100.0% | P2 | — |
| `src/responsibleai/leaderboard/providers.py` | 16 | 16 | 0 | 100.0% | P2 | 57, 58, 65, 71, 72, 85, 86, 93, … |
| `src/responsibleai/mcp/licensing.py` | 4 | 4 | 0 | 100.0% | P1 | — |
| `src/responsibleai/rbac/models.py` | 8 | 8 | 0 | 100.0% | P2 | — |
| `src/responsibleai/runtime/dispatcher.py` | 2 | 2 | 0 | 100.0% | P2 | — |
| `src/responsibleai/sovereign/zero_effect.py` | 4 | 4 | 0 | 100.0% | P2 | — |
| `src/responsibleai/supplychain/scanner.py` | 18 | 18 | 0 | 100.0% | P2 | — |
| `src/responsibleai/trust/score.py` | 22 | 22 | 0 | 100.0% | P2 | — |
| `src/responsibleai/trust_fabric/challenge.py` | 12 | 12 | 0 | 100.0% | P2 | — |

## Recommended test areas (priority order)

1. Authority / grant / revocation / fail-closed paths
2. Tenant isolation and session/auth boundaries
3. Policy / risk / approvals
4. MCP malformed upstream and execution errors
5. Audit / evidence integrity
6. Billing failure paths (no entitlement grant)
7. Enterprise security service deny paths
8. Dashboard API error handling (batch after security core)
