# EU AI Act Technical Support Mapping

Reference: Regulation (EU) 2024/1689 (`https://eur-lex.europa.eu/eli/reg/2024/1689/oj`).
This mapping highlights technical support for possible provider/deployer obligations. It
is not legal advice, conformity assessment, CE marking, certification, or a determination
that WhitePact or a customer's system is compliant. Role, territory, system category,
high-risk status, dates and sector rules require counsel.

| Area | Relevant provision/context | WhitePact evidence | Classification | Limitation / organizational responsibility |
|---|---|---|---|---|
| Risk management | Article 9 lifecycle risk system | policies, risk tiers, threat model, evaluation and decision controls | PARTIAL TECHNICAL SUPPORT | provider must establish the continuous system, tests, acceptance criteria and records |
| Data governance | Article 10 | dataset/bias/privacy evaluators | PARTIAL TECHNICAL SUPPORT | WhitePact does not establish origin, representativeness, lawful basis, annotation quality or full dataset governance |
| Technical documentation | Article 11 and Annex IV context | SPEC, model/evidence/compliance exports, SBOM | PARTIAL TECHNICAL SUPPORT | provider authors and maintains system-specific required documentation |
| Logging/traceability | Articles 12, 19 and deployer log duties | identity/action/decision/reason/policy/delegation timestamps; hash chain and export | TECHNICAL SUPPORT | deployment must enable, retain (including applicable six-month minimum), secure and make logs available lawfully |
| Transparency/instructions | Article 13 and Article 50 contexts | structured reason codes, risk tiers, reports and tool schemas | PARTIAL TECHNICAL SUPPORT | not a complete instruction-for-use, notice, explanation or AI-interaction disclosure package |
| Human oversight | Article 14 | approval requirements, quorum/self-approval/replay controls, deny/quarantine | TECHNICAL SUPPORT | organization assigns competent humans with authority, training and workable intervention procedures |
| Accuracy/robustness/cybersecurity | Article 15 | tests, guardrails, drift/red-team checks, authority and tenant isolation | PARTIAL TECHNICAL SUPPORT | metrics and thresholds must match intended purpose; independent validation and deployment security remain required |
| Quality/lifecycle governance | Article 17 context | PR/CI/release/vulnerability/incident processes | PARTIAL TECHNICAL SUPPORT | a complete organizational quality-management system is not established by this repository |
| Post-market monitoring | Articles 72–73 context | Prometheus signals, outcomes, evidence, incident records/webhooks | PARTIAL TECHNICAL SUPPORT | operator must create monitoring plan, collect real-world performance and report serious incidents |
| Access control | cybersecurity and governance support | RBAC, org-scoped auth, authority ceilings, revocation/expiry | TECHNICAL SUPPORT | live OAuth/SSO, IAM and administrator access must be configured and tested |
| Data protection | GDPR preserved by Article 2/other provisions | PII detection/redaction and optional field encryption | PARTIAL TECHNICAL SUPPORT | lawful basis, DPIA, rights, retention, transfers and DPA are organizational/legal duties |
| Fundamental-rights impact | Article 27 where applicable | evidence fields and risk-report inputs can support collection | ORGANIZATIONAL RESPONSIBILITY | WhitePact does not perform or notify the legally required FRIA |
| Applicability/classification | Articles 3, 6, Annexes and operator roles | classification tool is informational | LEGAL DETERMINATION REQUIRED | counsel/qualified owner determines provider/deployer role, exclusions and high-risk category |

Public wording must say “provides technical controls that can support selected EU AI Act
obligations.” “EU AI Act certified” and “fully compliant” are prohibited.
