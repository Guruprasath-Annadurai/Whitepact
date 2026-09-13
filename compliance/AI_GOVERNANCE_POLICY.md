# WhitePact AI Governance and Security Policy

**Status:** Effective when merged to `main`  
**Owner:** WhitePact maintainer / service owner  
**Initial approval date:** 2026-08-27  
**Review cadence:** At least annually and on material AI/model/tool/agent/regulatory change

## Purpose and role

This policy defines how WhitePact governs AI-enabled and agentic behavior and supports transparent assessment against CSA's AI Controls Matrix (AICM) / AI-CAIQ. It does not claim STAR for AI status until the AI-CAIQ is submitted and published/accepted in the CSA STAR Registry.

WhitePact is primarily an **AI application/orchestration governance provider**, not a foundation-model provider. It does not currently train or distribute its own foundation model weights. Controls that presuppose WhitePact owns foundation-model training datasets, training infrastructure, or base-model weights are assessed `N/A` unless that scope changes; N/A must always include a rationale.

## AI system inventory

| Component | Role | Main boundary |
|---|---|---|
| Runtime decision engine | Deterministic governance/enforcement (allow, redact, require approval, deny, quarantine) | Policy, authorization, audit |
| Guardrails / PII & safety scanning | Input/output safety | Validation, redaction, logging |
| Trust / bias / hallucination evaluation | AI assurance | Scoring logic, evidence, customer configuration |
| MCP / agent integration surface | Tool/agent governance | Authentication, authorization, approval boundaries |
| Dashboard / API | Administrative/integration plane | RBAC, SSO/MFA, tenant isolation, rate limiting, audit |
| External/customer-selected LLM providers | Third-party model dependency | Provider/customer controls plus WhitePact integration boundary |

The inventory is reviewed whenever a model/provider, agent framework, privileged tool, autonomous action, retrieval source, or material decision component changes.

## Human oversight and autonomous actions

High-risk or approval-required actions should use explicit approval, deny, or quarantine paths rather than silent execution. WhitePact documentation must distinguish controls enforced by WhitePact from controls the downstream integrator/cloud runtime must configure.

Governance gating is **not** automatically equivalent to OS/container sandboxing. WhitePact must not claim every third-party tool/plugin is sandboxed unless technical isolation actually exists.

## Input, prompt, and output security

AI-facing inputs are untrusted. Applicable controls include schema/length validation, adversarial and PII scanning where enabled, policy gating/redaction, separation of trusted system/configuration instructions from untrusted data where WhitePact constructs prompts, and avoidance of untrusted interpolation into executable shell/SQL/policy/tool instructions.

Prompt-injection resistance is defense-in-depth, not a solved problem. Material changes to agent/tool instruction handling require threat review.

AI-generated output must not automatically become a privileged action merely because a model produced it. Where WhitePact is in the enforcement path, outputs may be validated, redacted, approved, denied, or quarantined. WhitePact's deterministic governance decision must not be represented as proof that the underlying probabilistic model output is true or safe in every context.

## Agent and tool boundaries

For agentic integrations WhitePact requires/targets: authenticated callers; organization-scoped authorization; least-privilege credentials; separation of read-only vs state-changing operations; approval for policy-classified high-risk actions; tenant isolation; avoidance of unnecessary secrets in prompts; audit of material decisions; outbound URL/SSRF protection where applicable; and clear documentation of shared/customer responsibilities.

## Model/provider governance

Because WhitePact does not currently train foundation models, model-weight integrity, pre-training dataset provenance/poisoning, and model-training infrastructure controls are generally provider/customer-owned or N/A to WhitePact's service scope. A new WhitePact-hosted or fine-tuned model triggers re-scoping of the AICM/AI-CAIQ before release.

Customer-configured model providers remain shared/customer responsibility when customers supply their own accounts and keys. WhitePact must not claim provider-side retention/training guarantees unless supported by the actual integration and provider terms.

## Data and privacy

AI features follow WhitePact data-minimization, tenant-isolation, access-control, retention, encryption, audit, vendor-risk, and incident-response requirements. Security evidence must avoid unnecessary prompt/completion bodies, credentials, or customer secrets.

## Testing and assurance

AI-related testing should cover, as applicable: prompt injection/instruction confusion; sensitive-data leakage; authorization/cross-tenant bypass; unauthorized tool/action requests; output-policy bypass; abuse/rate limits; provider degradation; audit evidence completeness; and regression tests for fixed findings.

Automated and self-conducted testing is useful evidence but is not independent assurance or a penetration test.

## AI incident management

AI incidents include unauthorized autonomous actions, sensitive-data disclosure through AI processing, material prompt-injection exploitation, policy-engine bypass, model/provider compromise affecting WhitePact, cross-tenant AI data exposure, or materially incorrect governance behavior with security/safety impact. Handle them through `compliance/INCIDENT_RESPONSE_RUNBOOK.md`, preserving relevant versions, decisions, evidence and remediation.

## Material-change triggers

Review this policy, the AI inventory, risk register and AI-CAIQ applicability when: adding/replacing a model/provider used by WhitePact itself; hosting/fine-tuning WhitePact-owned weights; adding a privileged/autonomous tool; changing prompt/system-instruction architecture; adding retrieval over sensitive data; changing approval/deny/redaction/quarantine logic; changing AI retention/training use; or after material legal/contractual changes.

## Transparency rules

Before registry publication WhitePact may only state that an AI-CAIQ has been prepared/completed if true. Only after CSA publication may WhitePact state it is listed at **STAR for AI Level 1**. Never call Level 1 `CSA certified`, `independently audited`, or `SOC 2 equivalent`.

## Review record

| Date | Reviewer | Outcome |
|---|---|---|
| 2026-08-27 | WhitePact maintainer | Initial AICM/AI-CAIQ governance policy and AI-system scope established. |
