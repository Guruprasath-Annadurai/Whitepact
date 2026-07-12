# Security Policy

For encryption-at-rest, data residency, audit trail integrity, and SSO
enforcement details, see [ENTERPRISE_SECURITY.md](ENTERPRISE_SECURITY.md).

## Supported versions

| Version | Supported |
|---|---|
| 0.4.x | Yes |
| 0.3.x | Yes (critical fixes only) |
| < 0.3 | No |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **milchcreamfoods@gmail.com** with the subject line:
`[ResponsibleAI Security] <brief description>`

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (proof of concept preferred)
- Affected component (BiasBuster / PrivacyLabel / Guardrails / RedTeam / etc.)
- Suggested fix if you have one

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**.

## Scope

In scope:
- All code under `src/` (biasbuster, privacylabel, responsibleai)
- Prompt injection vulnerabilities in the RedTeam simulator test logic
- Privacy violations in the federated learning or differential privacy stack
- PII leakage through the guardrails engine
- Authentication or verification bypass in AI Passport hash verification

Out of scope:
- Vulnerabilities in third-party dependencies (report those upstream)
- Social engineering attacks
- Issues requiring physical access to the system

## Responsible disclosure

We ask that you:
- Allow reasonable time for a fix before public disclosure
- Not access or modify data belonging to other users
- Not perform denial-of-service attacks against our infrastructure

We commit to:
- Crediting reporters in the release notes (unless you prefer to remain anonymous)
- Not pursuing legal action against good-faith security researchers
- Communicating resolution timeline within one week of receipt
