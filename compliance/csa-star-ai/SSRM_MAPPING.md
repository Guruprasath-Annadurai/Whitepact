# Shared Security Responsibility Model (SSRM)

| Role | Definition for WhitePact |
|------|------------------------|
| **CSP (WhitePact)** | Application code, governance logic, hosted configuration when WhitePact operates SaaS |
| **CSC (Customer)** | IdP, LLM vendor choice, endpoint security, policy content, approver assignments |
| **3rd-party / provider** | Datacenter physical security, managed DB disk encryption, network backbone |

Column D in AI-CAIQ = SSRM owner. Column F = customer responsibility text (specific actions, not generic "best practices").

Examples for Column F:

- Configure SAML/OIDC with MFA at customer IdP  
- Rotate org API keys on compromise  
- Define which MCP tools agents may invoke  
- Assign human approvers for high-risk actions  
- Maintain workstation security for administrators  

Physical security controls → provider unless WhitePact operates bare metal (it does not).
