# WhitePact Security Threat Model

Review boundary: source and repository controls on 2026-08-31. This model covers the MCP
HTTP/stdio entry points, dashboard/API authentication, organization-scoped persistence,
the Heart authority and approval path, upstream MCP dispatch, evidence chain, CI, and
release controls. Hosted network/cloud configuration is included only where repository
evidence exists. See `SPEC.md` and `docs/heart-production/00_CURRENT_RUNTIME_MAP.md` for
the implemented actor/data flow.

Trust boundaries are: external caller → authentication; identity → authority resolution;
MCP request → governance decision; approval → execution authorization; tenant context →
repositories; WhitePact → upstream MCP/LLM; source → GitHub Actions; builder → published
artifact; evidence export → offline verifier.

| Threat | Asset | Attacker | Precondition | Attack path | Preventive control | Detective control | Test evidence | Residual risk |
|---|---|---|---|---|---|---|---|---|
| Malicious autonomous agent | policy/tenant data | authenticated agent | valid credential | request high-impact tools beyond purpose | authority ceiling, purpose/intent, five-way decision, approval | evidence/reason codes | `test_whitepact_gauntlet.py`, `test_mcp_intent_contract.py` | policy misconfiguration |
| Compromised MCP server | credentials/results | upstream server operator | registered upstream | return malicious output or misuse forwarded auth | upstream allow/enable registry, URL/tenant binding, no raw org key in tool args | evidence and upstream logs | `test_upstream_gateway.py` | remote output remains untrusted |
| Malicious MCP tool | execution integrity | tool publisher/operator | tool is available | deceptive schema/name or dangerous side effect | tool allowlists, target constraints, risk/approval gate, execution binding | action/target evidence | `test_mcp_governance_dispatch.py` | semantic intent cannot be proven from schema alone |
| Forged identity | tenant authority | external caller | can craft token | fake OIDC/VC/SAML claims | signature, issuer/audience/time validation; conservative identity mapping | auth failures | `test_oidc.py`, `test_verifiable_credential.py`, `test_crypto_policy.py` | live provider configuration error |
| Stolen API credential | tenant data/actions | credential thief | obtains raw key | authenticate as victim | hashed storage, scoped role/org, rate limits, revocation/rotation process | last-use/audit/secret scanning | `test_org_api.py`, `test_rbac.py` | bearer token works until revoked |
| Authenticated unauthorized caller | privileged endpoints | low-role user | valid lower role | invoke admin action | RBAC dependency and org context | audit entries | `test_rbac.py`, dashboard API tests | endpoint missing an RBAC dependency |
| Privilege escalation | authority | agent/admin | lower privilege | widen grants/ceilings | attenuation validation, org ceiling, non-terminal roots | denial evidence | authority property suites | configuration owner can intentionally grant broad authority |
| Authority amplification | root/delegation | delegated agent | valid parent grant | malformed child exceeds parent | subset/value/target attenuation and Heart kernel | reason codes | `test_property_based.py`, `test_authority_lattice_properties.py` | novel constraint types need explicit comparison |
| Delegation-cycle abuse | authority chain | agent | can propose links | cycle obscures origin | cycle detection and terminal-root validation | invalid-chain result | `test_delegation_kernel_properties.py`, `test_root_authority.py` | distributed concurrent graph writes |
| Approval replay | high-impact execution | caller with approval ID | approved request | execute twice | atomic consume before execution | consumed status/evidence | `test_approval_execution_binding.py`, `test_resume_after_approval.py` | multi-database deployment needs transactional validation |
| Approval race | high-impact execution | concurrent callers | same approved ID | simultaneous resume | repository transition/consume boundary | duplicate failure logs | approval concurrency tests | production DB isolation/load not independently tested |
| Approval mutation | reviewed action | caller | valid approval | change target/arguments after approval | canonical action digest and execution authorization | mismatch error | `test_approval_execution_binding.py` | canonicalizer changes require migration care |
| Revocation bypass | authority | revoked principal | stale credential/grant | continue after revocation | revocation kernel and active checks | denial evidence | `test_revocation_kernel_properties.py`, root/passport tests | external IdP revocation latency |
| Expiration/stale authority | authority | old principal | expired grant | reuse cached state | UTC expiry checks at verification/execution | expired verdict | authority lifetime/passport/approval expiry tests | clock skew and distributed caches |
| Cross-tenant access | customer data | tenant A | valid A key | query/modify tenant B identifiers | org derived from credential, repository filters, 404-not-403 isolation | org-scoped audit | `test_tenant_isolation.py`, `test_upstream_gateway.py` | hosted DB row-policy defense is deployment-specific |
| Evidence tampering | audit integrity | operator/file recipient | access to DB/export | edit/reorder/remove records | per-org hash chain and bundle digest | offline verifier | `test_evidence_bundle.py` Hypothesis/tamper tests | hashes are tamper-evident, not external timestamp/notarization |
| Compromised dependency | runtime/build | package attacker | dependency update/resolution | malicious package/version | Dependabot, dependency review, pip-audit, SBOM, review; scanner hash lock | SCA/Scorecard | CI and policy workflows | ordinary runtime dependency ranges are not fully locked |
| Compromised GitHub Action | source/token/release | action maintainer | workflow uses action | tag retarget or malicious release | all Actions pinned to 40-char commits; least privilege | pinned-action guard/Scorecard | `scripts/check_pinned_actions.py` | pinned commit itself may be malicious |
| Compromised maintainer account | repository/release | account thief | steals maintainer session/factor | merge/configure/release | MFA criterion, branch protection, signed tag allow-list, OIDC | GitHub audit/attestations | release policy tests | sole admin and 2FA state require owner evidence |
| Malicious release | consumer systems | insider/pipeline attacker | release privilege | publish bytes not reviewed | signed intent, protected workflow, Trusted Publishing, SBOM/attestations | consumer verification | release regression/reproducibility tests | next hardened release verification pending; see SLSA branch |
| Secret leakage | credentials | contributor/attacker | secret committed/logged | exfiltrate from git/CI | Gitleaks, GitHub secret scanning and push protection, least privilege | alerts and scan reports | Gitleaks workflow | non-provider patterns/validity checks disabled |
| Prompt-injection tool misuse | data/actions | untrusted content | model consumes hostile prompt | model requests dangerous tool | governance evaluates structured action independent of prompt, ceilings/approval | reason/evidence record | MCP governance and gauntlet tests | model may encode harmful intent in apparently allowed arguments |
| Supply-chain metadata deception | consumer/reviewer | release attacker | can alter labels/SBOM/claim | mismatch identity/hash/evidence | immutable refs, exact artifacts, SBOM/digests, public claim policy | attestation/verification and trust regression guard | reproducible/release tests, `check_trust_regressions.py` | external claims can copy stale evidence |

## Highest residual risks

1. One maintainer controls code, repository administration, security triage, and release
   intent. Independent review is a **HUMAN MATURITY BLOCKER**.
2. No independent penetration test validates the hosted service, provider integrations,
   or cloud configuration: **EXTERNAL AUDIT REQUIRED**.
3. Production identity-provider revocation, OAuth tenants, database isolation, cookies,
   and origin-network controls need live-environment verification.
4. Hash-chain evidence detects alteration but cannot prove that omitted events were ever
   recorded; external anchoring and operational log retention are deployment controls.

Review this model for every new externally reachable interface, authority constraint,
identity provider, persistence backend, privileged workflow, or release architecture.
