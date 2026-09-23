# Submission evidence manifest — AI-CAIQ v1.1

Feature SHA: `9e924f111acefa79bcb29b6255d0100bb35198e1`

Every YES below must be backed by repository or labeled exercise evidence.

| Question ID | Answer | Strength | Evidence type | References |
|-------------|--------|----------|---------------|------------|
| AIS-02.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/dashboard/app.py |
| AIS-03.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/dashboard/prometheus.py, BENCHMARKS.md |
| AIS-07.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | .github/workflows/dependency-review.yml, .github/workflows/security-scan.yml, CHANGELOG.md |
| AIS-08.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/dashboard/app.py, tests/test_mcp_oauth.py, tests/test_mcp_oauth_authorization_server.py |
| AIS-09.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/guardrails/engine.py, tests/test_streaming.py, tests/test_v1_api.py |
| AIS-10.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/guardrails/engine.py, tests/test_streaming.py |
| AIS-11.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/runtime/authority_kernel.py, tests/test_phase7a_authority_kernel.py |
| AIS-12.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_whitepact_alias.py |
| CEK-04.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/db/engine.py |
| CEK-10.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/db/encryption.py, compliance/KEY_MANAGEMENT.md |
| DSP-20.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_data_inventory.py |
| GRC-11.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_v1_api.py |
| GRC-15.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/governance/approval.py, src/responsibleai/runtime/authority_kernel.py, tests/test_resume_after_approval.py |
| IAM-05.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/dashboard/app.py |
| IAM-17.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_rbac.py |
| IAM-18.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_mcp_production_tool_registry.py |
| I&S-06.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | tests/test_tenant_isolation.py, tests/test_phase5_tenant_isolation.py |
| SEF-06.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/governance/quarantine.py |
| TVM-01.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | THREAT_MODEL.md, .github/workflows/dependency-review.yml |
| TVM-03.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | .github/workflows/dependency-review.yml, CHANGELOG.md |
| TVM-11.1 | YES | MODERATE | REPOSITORY_EVIDENCE_REVIEW | .github/workflows/security-scan.yml |
| TVM-13.1 | YES | STRONG | REPOSITORY_EVIDENCE_REVIEW | src/responsibleai/guardrails/engine.py, tests/test_phase7a_authority_kernel.py, tests/test_streaming.py |

Total YES rows: 22