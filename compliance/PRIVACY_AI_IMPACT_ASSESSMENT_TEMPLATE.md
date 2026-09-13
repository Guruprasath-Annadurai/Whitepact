# WhitePact Privacy + AI Impact Assessment Template

**Status:** Mandatory first-party review template for material privacy/AI changes  
**Owner:** WhitePact maintainer / service owner

> This template is a technical/organizational risk review, not a legal opinion, regulatory conformity assessment or external certification.

## Assessment metadata

- Assessment ID:
- Change / system name:
- Requester / owner:
- Review date:
- Target release / commit SHA:
- Deployment/environment:
- Related PR/design/issue:
- Review trigger(s):

## 1. Intended purpose

- What problem does the system/change solve?
- Who are the intended users/affected people?
- What decisions/actions can it influence or execute?
- Is the use optional, required or automated?
- What would constitute misuse or out-of-scope use?

## 2. AI/system role

- WhitePact role: developer / provider / deployer / orchestrator / governance layer / other:
- External model/provider(s):
- Agent/tool integrations:
- Does WhitePact train/fine-tune/store its own model weights for this change? Yes/No
- Is AI output advisory, determinative or capable of causing a real-world action?
- Human oversight point(s):

## 3. Data inventory

| Item | Answer |
|---|---|
| Personal data processed? | |
| Sensitive/special-category data? | |
| Children's data? | |
| Financial/health/biometric/employment data? | |
| Customer confidential data? | |
| Source(s) of data | |
| New subprocessor/provider? | |
| Processing/storage regions | |
| Retention period | |
| Public disclosure involved? | |
| Used for model training/fine-tuning? | |

Data minimization: explain why every new category is necessary and whether a less-invasive design exists.

## 4. Authority and capability assessment

- What credentials/permissions can the AI/agent/tool use?
- What is the maximum reachable action if components are chained?
- Is the action reversible?
- Can it create financial, security, legal or reputational consequences?
- Can authority be delegated/transferred?
- How is authority revoked?
- What happens if approval/evidence/policy services fail?
- Can untrusted model output become executable authority without an independent control?

## 5. Foreseeable harms / threat scenarios

Evaluate at minimum:

- unauthorized action or privilege escalation;
- prompt/instruction injection;
- cross-tenant access;
- sensitive-data leakage;
- excessive collection/retention;
- inaccurate/misleading model output;
- discrimination/unfair impact where relevant;
- automation bias / inadequate human oversight;
- tool/MCP/supply-chain compromise;
- replay/stale authorization;
- runaway/recursive behavior;
- vendor/model outage or silent model change;
- inability to explain/audit a consequential event;
- public disclosure/re-identification risk;
- legal/regulatory misclassification.

## 6. Risk table

| Risk ID | Scenario | Likelihood | Impact | Inherent risk | Controls | Residual risk | Owner | Treatment |
|---|---|---|---|---|---|---|---|---|
| | | | | | | | | |

Risk scale and acceptance rules follow `compliance/RISK_MANAGEMENT_POLICY.md`.

## 7. Human oversight

- Who can approve/refuse the action?
- Is the approver sufficiently informed and independent from the requesting agent?
- Can approval expire?
- Can approval be revoked before execution?
- Are high-risk actions distinguishable from routine actions?
- Is there a safe fallback if no human is available?

## 8. Transparency and user information

Record what users/customers must be told about:

- intended purpose;
- limitations;
- data handling/retention;
- external model/providers;
- automated/probabilistic behavior;
- human-oversight boundaries;
- audit/evidence behavior;
- public disclosure where applicable;
- security/shared-responsibility assumptions.

## 9. Security and privacy controls

Confirm applicability/evidence for:

- authentication/RBAC/tenant isolation;
- least privilege;
- secrets/key handling;
- encryption in transit/at rest as applicable;
- input/schema/length validation;
- PII/sensitive-data controls;
- SSRF/egress restrictions where applicable;
- rate limits/abuse controls;
- approval/deny/quarantine/revocation;
- audit/evidence creation;
- retention/deletion;
- incident response;
- vendor/subprocessor review;
- security/regression testing;
- release/SBOM/provenance controls.

## 10. Regulatory/contract screening

This section flags questions for qualified review; it does not answer them conclusively.

- GDPR/UK GDPR processing or DPIA trigger potentially applicable? Yes/No/Unclear
- India DPDP obligations potentially applicable? Yes/No/Unclear
- EU AI Act role/high-risk/prohibited/transparency obligations potentially applicable? Yes/No/Unclear
- Sector-specific law (finance, health, employment, government, children, biometrics) potentially applicable? Yes/No/Unclear
- Customer contract/security requirements implicated? Yes/No/Unclear
- External counsel required before release? Yes/No + reason

## 11. Validation plan

List concrete tests required before release, for example:

- authorization/cross-tenant negative tests;
- approval/revocation/replay tests;
- prompt-injection/adversarial tests;
- data-leakage/PII tests;
- evidence fail-closed tests;
- provider degradation/failure tests;
- red-team/pentest tests where warranted;
- rollback/recovery tests.

## 12. Decision

- [ ] Approve — residual risk acceptable.
- [ ] Approve with conditions — list conditions and owners below.
- [ ] Hold — evidence/control work required.
- [ ] Reject / redesign.

Conditions/actions:

| Action | Owner | Due date / release gate | Evidence required |
|---|---|---|---|
| | | | |

Risk accepted by authorized owner (if applicable):

Final rationale:

## 13. Post-release review triggers

Reopen this assessment after a material incident, new provider/model, new privileged capability, material data-flow change, major regulatory change, unexpected user harm, or evidence that a control is ineffective.
