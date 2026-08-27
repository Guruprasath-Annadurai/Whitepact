# Security Policy

For encryption-at-rest, data residency, audit trail integrity, and SSO
enforcement details, see [ENTERPRISE_SECURITY.md](ENTERPRISE_SECURITY.md).

## Supported versions

This project does not yet maintain parallel supported branches — there
is one active line of development, and fixes land on the latest
release. `RELEASING.md` documents the actual release process;
`pyproject.toml`'s `version` field is the current source of truth for
what's shipping.

| Version | Supported |
|---|---|
| Latest release | Yes |
| Older releases | Critical fixes only, at maintainer discretion |

## Reporting a vulnerability

**Do not open a public GitHub issue for security vulnerabilities.**

Email **annaduraiguruprasath7@gmail.com** with the subject line:
`[WhitePact Security] <brief description>`

Please include:
- A description of the vulnerability and its potential impact
- Steps to reproduce (proof of concept preferred)
- Affected component (MCP governance engine / runtime governance core /
  BiasBuster / PrivacyLabel / Guardrails / RedTeam / etc. — see
  `SPEC.md` for the current architecture)
- Suggested fix if you have one

You will receive an acknowledgement within **48 hours** and a resolution timeline within **7 days**.

## Scope

In scope:
- All code under `src/` (biasbuster, privacylabel, responsibleai)
- Authentication, OAuth/OIDC, tenant-isolation, authorization, approval,
  evidence, and Heart enforcement bypasses
- Hosted dashboard, REST API, MCP Streamable HTTP/SSE transports, deployment
  manifests, release workflows, and supply-chain controls
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
