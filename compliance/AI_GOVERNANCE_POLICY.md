# WhitePact AI Governance and Security Policy

**Status:** Effective when merged to `main`  
**Owner:** WhitePact maintainer / service owner  
**Initial approval date:** 2026-08-27  
**Review cadence:** At least annually, and on material AI architecture, provider, tool, agent, or regulatory change

## 1. Purpose

This policy defines how WhitePact governs AI-enabled and agentic behavior in the product and its integrations. It is intended to support transparent assessment against the Cloud Security Alliance AI Controls Matrix (AICM) and AI-CAIQ. It does not claim CSA STAR for AI status until an AI-CAIQ is submitted and accepted/published in the CSA STAR Registry.

## 2. WhitePact's AI role and scope

WhitePact is primarily an **AI application/orchestration governance provider**, not a foundation-model provider. WhitePact does not currently train or distribute its own foundation model weights. Customer-selected or externally provided models may be evaluated or governed through WhitePact integrations.

Controls that presuppose WhitePact owns foundation-model pre-training datasets, model-weight training infrastructure, or base-model training are therefore assessed as **Not Applicable** unless that product scope changes. N/A must always include a scope rationale; it must never be used to hide a missing applicable control.

## 3. AI system inventory

The minimum maintained inventory is:

| Component | Role | AI relevance | Primary security boundary |
|---|---|---|---|
| WhitePact runtime decision engine | Governance/enforcement | Produces deterministic governance outcomes such as allow, redact, require approval, deny, or quarantine | Policy rules, authorization, audit trail |
| Guardrails / PII and safety scanning | Input/output safety control | Detects sensitive or prohibited patterns and can redact or gate processing | Validation rules, redaction, logging |
| Trust / bias / hallucination evaluation components | AI assurance | Evaluates behavior and risk signals | Scoring logic, evidence, customer configuration |
| MCP / agent integration surface | Agent/tool governance | Connects agent workflows and tools to WhitePact governance | Authentication, authorization, tool boundaries, approval gates |
| Dashboard / API | Administrative and integration plane | Configures and exposes governance state | RBAC, SSO/MFA, tenant isolation, rate limiting, audit |
| External/customer-selected LLM providers | Third-party AI dependency | Generate or process model outputs under customer/provider terms | Customer credentials, provider controls, WhitePact guardrails |

The inventory must be updated when a new AI model, model provider, agent framework, privileged tool, autonomous action, or material decisioning component is introduced.

## 4. Human oversight and autonomous actions

WhitePact is designed to support human oversight rather than treating every AI action as implicitly authorized.

Where policy identifies a high-risk or approval-required action, the system should use an explicit approval path or deny/quarantine outcome rather than silently execute the action. Security and compliance documentation must distinguish what WhitePact itself enforces from what a downstream integrator must configure.

No documentation may claim that every third-party agent action is sandboxed by WhitePact unless technical isolation actually exists. Governance gating and sandbox isolation are distinct controls.

## 5. Input and prompt security

AI-facing inputs must be treated as untrusted.

Applicable controls include:

- schema and length validation for exposed APIs;
- adversarial-pattern and PII scanning where the relevant guardrail surface is enabled;
- rejecting or gating inputs that violate configured policy;
- keeping system/configuration instructions separate from untrusted user or retrieved data wherever WhitePact controls prompt construction;
- avoiding interpolation of untrusted text into executable shell, SQL, policy, or privileged tool instructions;
- logging security-relevant governance decisions without intentionally recording secrets or unnecessary prompt bodies.

Prompt-injection resistance is treated as defense-in-depth, not as a solved problem. Changes to agent/tool instruction handling require threat review.

## 6. Output security and decision integrity

AI-generated output must not automatically become a privileged action merely because a model produced it. Where WhitePact is in the enforcement path, outputs may be subject to validation, policy checks, redaction, approval, denial, or quarantine.

Model output is probabilistic and may be incorrect. WhitePact's deterministic governance decision layer must not be described as proof that the underlying model output is true or safe in all contexts.

## 7. Agent and tool security boundaries

For agentic integrations:

- authenticate callers and bind authorization to organization/tenant scope;
- apply least privilege to tools and credentials;
- distinguish read-only from state-changing operations;
- require approval for actions classified by policy as high risk;
- prevent cross-tenant access;
- keep customer secrets out of model prompts unless explicitly required and protected;
- audit material tool/governance decisions;
- apply outbound URL/SSRF protections to webhook-like network actions;
- document when isolation is provided by the customer's runtime or cloud platform rather than WhitePact itself.

**Sandboxing status:** WhitePact's governance layer can gate tool/action decisions, but that is not equivalent to executing every external AI tool/plugin in an OS/container sandbox. AICM sandboxing questions must be answered according to the actual deployment/integration architecture.

## 8. Model and provider governance

Because WhitePact does not currently train its own foundation models:

- model-weight integrity, training-data provenance, poisoning controls, and pre-training lifecycle controls are generally provider/customer-owned or N/A to WhitePact's own service scope;
- provider selection and data-sharing must be documented when WhitePact itself contracts with a model provider;
- customer-configured providers remain shared/customer responsibility where customers supply their own accounts and keys;
- a new WhitePact-hosted/fine-tuned model would trigger re-scoping of the AICM assessment before release.

## 9. Data and privacy

AI features must follow the same data-minimization, tenant-isolation, retention, access-control, encryption, and incident-response requirements as other WhitePact processing.

WhitePact must not claim that customer prompts/completions are never retained or used for training by a third-party provider unless that is established by the actual integration and provider terms. Customer/provider responsibility must be stated accurately.

## 10. Testing and assurance

AI-related security testing should cover, as applicable:

- prompt injection and instruction-confusion attempts;
- sensitive-data leakage;
- authorization bypass and cross-tenant access;
- unsafe or unauthorized tool/action requests;
- output policy bypass;
- rate-limit and abuse scenarios;
- provider failure/degradation;
- audit evidence completeness;
- regression tests for previously fixed security findings.

Automated and self-conducted testing is useful evidence but is not an independent audit or penetration test.

## 11. AI incident management

AI-specific incidents include unauthorized autonomous actions, sensitive-data disclosure through AI processing, material prompt-injection exploitation, policy-engine bypass, model/provider compromise affecting WhitePact, cross-tenant AI data exposure, or materially incorrect governance behavior creating security/safety impact.

Such events follow `compliance/INCIDENT_RESPONSE_RUNBOOK.md`, with preservation of relevant policy decisions, audit-chain evidence, versions, provider context, and remediation actions.

## 12. Change management

The following are material AI changes requiring review of this policy, the AI system inventory, risk register, and AI-CAIQ applicability:

- adding or replacing a foundation model/provider used by WhitePact itself;
- hosting or fine-tuning WhitePact-owned model weights;
- adding an autonomous action or privileged tool;
- changing prompt/system-instruction architecture;
- adding retrieval over sensitive customer data;
- changing approval/deny/redaction/quarantine logic;
- adding new AI data retention or training use;
- significant changes to applicable AI law, contract, or assurance requirements.

## 13. Transparency rules

Public claims must use accurate wording:

- Allowed before registry publication: `WhitePact has completed/prepared an AI-CAIQ self-assessment` only when the assessment is actually completed.
- Allowed only after CSA publication: `WhitePact is listed at CSA STAR for AI Level 1` or equivalent designation language.
- Never claim `CSA certified`, `independently audited`, or `SOC 2 equivalent` for a Level 1 self-assessment.

## 14. Review record

| Date | Reviewer | Outcome |
|---|---|---|
| 2026-08-27 | WhitePact maintainer | Initial policy created to formalize AICM/AI-CAIQ scope, ownership, agent boundaries, and N/A rules. |
