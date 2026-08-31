# OWASP AI and Agent Security Mapping

Primary reference: OWASP Top 10 for Agentic Applications 2026 and complementary OWASP
Top 10 for LLM Applications guidance (`https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/`).
OWASP publishes guidance, not a WhitePact certification. Mappings describe implemented
controls and residual risk, not complete prevention.

| Risk | WhitePact control | Code/docs evidence | Support | Residual gap |
|---|---|---|---|---|
| ASI01 Agent Goal Hijack | intent/purpose constraints; independent structured governance decision | `intent.py`, `purpose_binding.py`, MCP intent tests | Strong technical mitigation | malicious intent encoded inside allowed arguments/outputs |
| ASI02 Tool Misuse & Exploitation | tool/action/target allowlists, risk tier, approval/quarantine, exact execution binding | gateway, policy, approval/execution modules; gauntlet tests | Strong technical mitigation | semantic tool side effects and compromised remote tool |
| ASI03 Identity & Privilege Abuse | OIDC/VC/API-key verification, conservative root mapping, RBAC, tenant scope, attenuation/revocation | auth, identity bridge, Heart roots/kernels, tenant tests | Strong technical mitigation | stolen bearer credential and live IdP misconfiguration |
| ASI04 Agentic Supply Chain Vulnerabilities | upstream registry, pinned Actions/containers, SBOM, dependency review/SCA/VEX | upstream gateway tests, workflows, vulnerability policy | Partial mitigation | remote MCP/model/data integrity cannot be fully established |
| ASI05 Unexpected Code Execution (RCE) | typed schemas, no generic eval/shell execution path, tool allowlists and approval | MCP tools/dispatch, internal review, Bandit | Partial mitigation | explicitly registered tools may execute dangerous operations downstream |
| ASI06 Memory & Context Poisoning | memory-write pattern firewall and intent/purpose re-evaluation | `memory_firewall.py`, property tests | Partial mitigation | pattern scanning is not semantic provenance for all memory/context |
| ASI07 Insecure Inter-Agent Communication | authenticated/scoped MCP/HTTP context, delegation chain and A2A adapter boundary | auth/middleware, delegation, A2A tests | Partial mitigation | transport identity/provider interoperability needs live tests |
| ASI08 Cascading Failures | autonomy budgets, workflow-composition rules, rate limits, quarantine and veto | autonomy/workflow/Heart tests | Partial mitigation | multi-system recovery, rollback and blast-radius validation |
| ASI09 Human-Agent Trust Exploitation | explicit reason/risk display, self-approval block, quorum and exact-action approval | approval/quorum/evidence tests | Partial mitigation | UI dark patterns, reviewer fatigue and deceptive model explanations |
| ASI10 Rogue Agents | bounded authority, expiry/revocation, approval, deny/quarantine, evidence/outcomes | Heart authority suites and runtime gateway | Strong technical mitigation | policy owner may over-grant; downstream emergency stop is deployment-specific |
| LLM01 Prompt Injection | content guardrails/red-team payloads plus action governance independent of prompt | guardrails/redteam, gateway tests | Partial mitigation | prompt detection is probabilistic; governance constrains impact rather than guaranteeing detection |
| LLM02 Sensitive Information Disclosure | PII detection/redaction, argument values excluded from evidence, tenant isolation | guardrails, evidence model, tenant tests | Partial mitigation | customer/model/provider handling and free-text outputs |
| LLM03 Supply Chain | SCA/SBOM/pins/VEX/release evidence | workflows, security policy, release docs | Partial mitigation | mutable end-user resolution and third-party services |
| LLM05 Improper Output Handling | structured MCP schemas and no automatic trust in model text | tool schemas/dispatch | Partial mitigation | downstream clients must validate/sanitize outputs |
| LLM06 Excessive Agency | authority ceilings, purpose binding, approvals/budgets | governance/Heart modules | Strong technical mitigation | correctness depends on configured least privilege |
| LLM10 Unbounded Consumption | route/plan rate limits and autonomy budgets | rate limiter/autonomy budget tests | Partial mitigation | cloud/provider spend controls remain external |

The threat model and property suites contain the detailed attack paths and tests. Public
wording may say “mapped to selected OWASP GenAI risks”; “OWASP certified” is prohibited.
