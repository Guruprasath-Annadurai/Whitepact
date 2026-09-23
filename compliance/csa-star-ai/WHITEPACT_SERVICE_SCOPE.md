# WhitePact service scope (CSA AI-CAIQ Phase 2)

## 1. Product definition
WhitePact is an **AI governance and authorization runtime** for autonomous agents: constitution → identity → authority → policy → capability graph → risk → approval → short-lived execution grant → isolated execution → controlled egress → evidence → audit → revocation.

## 2. AI functionality
Governance dispatch, guardrails, MCP tool registry, authority kernel, human approvals, audit metadata, revocation — not foundation-model training or hosting.

## 3–6. Architecture & flows
See `src/responsibleai/runtime/authority_kernel.py`, `mcp/upstream_dispatch.py`, `guardrails/engine.py`.

## 7. Model-provider dependencies
Customer-chosen LLM APIs; WhitePact does not train or distribute model weights.

## 8. Cloud-provider dependencies
Render/Supabase/Upstash-class hosting per `SUBPROCESSOR_REGISTER.md` — WhitePact is **not** the underlying CSP.

## 9–10. WhitePact vs customer control
WhitePact: enforcement layer. Customer: data, model choice, IdP, deployment configuration.

## 11–14. CSA roles (evidence-based)
| Role | Conclusion |
|------|------------|
| **Primary OSP** | Orchestrates governed agent execution without owning MP pipelines |
| **Secondary AP** | Application APIs/dashboard/MCP surface |
| **Excluded MP** | No training/fine-tuning/signing of model artifacts in-repo |
| **Excluded CSP** | No physical DC/hypervisor operation |

## 15. Submission scope boundary
AI-CAIQ answers reflect OSP/AP responsibilities; MP training (MDS) and physical CSP controls are NA or provider-assurance NO as documented per control.
