# NIST AI RMF 1.0 Support Mapping

Normative reference: NIST AI 100-1 and the official AI RMF Core
(`https://airc.nist.gov/airmf-resources/airmf/5-sec-core/`). NIST states that AI RMF 1.0
is voluntary and is being revised. This is a capability mapping, not NIST certification.

| Function | WhitePact control | Source evidence | Support level | Limitation | Organizational responsibility |
|---|---|---|---|---|---|
| GOVERN | Policies, risk tiers, authority ceilings, purpose/intent and decision evidence | `governance/policy.py`, `risk.py`, `org_authority_ceiling.py`, `GOVERNANCE.md` | SUPPORTED | Tool enforces configured policy; it does not choose an organization's risk appetite | assign owners, approve policy/risk tolerance, legal requirements and review cadence |
| GOVERN | Roles, disclosure, incident and vendor/dependency process | `MAINTAINERS.md`, `SECURITY.md`, incident runbook, vulnerability management | PARTIALLY SUPPORTED | Solo self-review and unexercised hosted controls | independent oversight, training, procurement and incident authority |
| GOVERN | Third-party AI/MCP boundaries | upstream registry/dispatch, vendor assessment, SBOM/dependency controls | PARTIALLY SUPPORTED | Cannot verify a provider's model/data/IP practices | due diligence, contracts, contingency and acceptable-use policy |
| MAP | Intended purpose and permitted/denied actions/targets | `intent.py`, `purpose_binding.py`, policy/authority models | SUPPORTED | Configuration quality depends on system owner and use case | document context, users, affected groups, intended/foreseeable misuse |
| MAP | Actor, identity, delegation and tenant context | identity bridge, root authority, delegation chain, org-scoped repositories | SUPPORTED | Live IdP claims and role assignment need deployment validation | authorize actors and map real business accountability |
| MAP | EU risk classification and compliance question generation | MCP compliance tools and `compliance/engine.py` | PARTIALLY SUPPORTED | Output is decision support, not a legal classification or impact assessment | counsel/qualified owner determines applicability and affected stakeholders |
| MAP | Threat and attack-surface analysis | `SECURITY_THREAT_MODEL.md` | PARTIALLY SUPPORTED | Repository boundary, internally reviewed | extend to each deployment/model/data flow and external stakeholders |
| MEASURE | Bias, hallucination, privacy, red-team, trust and drift evaluation | BiasBuster, Guardrails, evaluation/drift modules and tests | SUPPORTED | Metrics are context-dependent and do not establish acceptability alone | choose representative datasets, thresholds and independent TEVV |
| MEASURE | Repeatable tests, coverage and evidence records | CI gates, property tests, `EvidenceRecord`, offline bundle verifier | SUPPORTED | Hash evidence does not prove omitted events or outcome validity | operate monitoring, retain evidence and investigate anomalies |
| MEASURE | Outcome observation and risk signals | outcome records, Prometheus metrics, budget/quarantine | PARTIALLY SUPPORTED | Not all downstream impacts are observable by WhitePact | collect user/stakeholder feedback and real-world impact metrics |
| MANAGE | Five-way decision: allow/deny/modify/approval/quarantine | runtime gateway, Heart veto/approval/quarantine paths | SUPPORTED | Correct treatment depends on configured rules and integrations | approve risk treatment and ensure intervention authority |
| MANAGE | Revocation, expiry, replay protection and constrained execution | Heart kernels, approval digest/consume, execution authorization | SUPPORTED | Distributed production races/IdP revocation latency need validation | key/grant lifecycle and emergency-stop operations |
| MANAGE | Incident/vulnerability response and continuous improvement | incident runbook, advisories, Dependabot/SAST/SCA, quarterly governance review | PARTIALLY SUPPORTED | Internal process has no independent effectiveness audit | resource remediation, notify affected parties, update policies/models |

WhitePact supports technical portions of all four functions, but an organization must
operate the cross-functional governance, stakeholder engagement, legal analysis, risk
acceptance, independent TEVV, and lifecycle monitoring needed for AI RMF outcomes.
