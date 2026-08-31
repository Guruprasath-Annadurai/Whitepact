# Fuzzing and Property-Testing Readiness

Last reviewed: 2026-08-31. WhitePact uses deterministic pytest examples plus Hypothesis
properties for invariant-heavy Python code. This is not OSS-Fuzz enrollment.

| Target | Method | Invariant | Test file | Status | Remaining gap |
|---|---|---|---|---|---|
| Authority attenuation | Hypothesis sets/numeric boundaries | child authority never widens parent | `test_property_based.py`, `test_authority_lattice_properties.py` | VERIFIED | Persistence integration remains example-based |
| Identity types | Hypothesis arbitrary strings | unknown types remain non-terminal/fail safe | `test_identity_authority_adapter.py` | VERIFIED | Live IdP claim corpora |
| Delegation and roots | Hypothesis + examples | cycles, revoked/expired ancestors cannot authorize | `test_delegation_kernel_properties.py`, `test_root_authority.py` | VERIFIED | Stateful concurrent graph mutation |
| Approval state | Integration examples | pending/denied/expired cannot execute | `test_approval_expiry.py`, `test_resume_after_approval.py` | VERIFIED | Distributed database contention test |
| Replay/mutation | Examples + digest properties | one approval authorizes one exact action | `test_approval_execution_binding.py` | VERIFIED | Multi-node load test |
| Tenant boundary | API integration tests | org credential/query cannot cross org scope | `test_tenant_isolation.py`, `test_upstream_gateway.py` | VERIFIED | Hosted multi-tenant penetration test |
| Evidence chain | Hypothesis arbitrary JSON/mutations + integration | malformed input never raises/verifies; tampering is detected | `test_evidence_bundle.py` | VERIFIED | External verifier interoperability |
| MCP tool schemas/arguments | Schema and dispatch matrices | missing/wrong arguments produce errors, not privileged execution | `test_mcp_server.py`, `test_mcp_governance_dispatch.py` | VERIFIED | Coverage-guided wire-protocol fuzzer |
| Credential claims | Property/examples | malformed/unrecognized claims fail validation | `test_oidc.py`, `test_identity_bridge.py`, `test_crypto_policy.py` | VERIFIED | Provider-issued live token corpus |
| Policy parsing | Examples | malformed/empty policy cannot silently grant broader scope | `test_governance_policy.py`, `test_policy_repository.py` | VERIFIED | Arbitrary serialized DB-row property suite |
| Supply-chain metadata | Workflow policy scripts | movable Actions and unlicensed source fail CI | `check_pinned_actions.py`, `manage_license_headers.py` | TECHNICALLY READY | No general-purpose malformed SBOM parser in runtime |

OSS-Fuzz is **NOT APPLICABLE** as a truthful near-term integration: WhitePact is primarily
Python and has no native parser target or long-running coverage-guided harness accepted by
OSS-Fuzz. Hypothesis provides meaningful security value, but OpenSSF Scorecard may still
report Fuzzing 0 because it recognizes specific continuous fuzzing services. A future MCP
wire-protocol/JSON harness can use Atheris or CIFuzz if coverage and crash triage ownership
are established; an empty badge-oriented harness is prohibited.
