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

Preferred: open a [private GitHub vulnerability report](https://github.com/Guruprasath-Annadurai/Whitepact/security/advisories/new).

Alternatively, email **annaduraiguruprasath7@gmail.com** with the subject line:
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
- Prompt injection vulnerabilities in the RedTeam simulator test logic
- Privacy violations in the federated learning or differential privacy stack
- PII leakage through the guardrails engine
- Authentication or verification bypass in AI Passport hash verification

Dependency vulnerabilities that affect WhitePact are in scope for triage and mitigation.
WhitePact may coordinate the upstream fix rather than maintain a permanent fork.

Out of scope:
- Social engineering attacks
- Issues requiring physical access to the system

## Triage and advisory process

1. The maintainer acknowledges the report and validates affected versions and impact.
2. Severity is assigned using exploitability, affected confidentiality/integrity/
   availability, tenant impact, required privileges, and reachable deployment paths.
3. Confirmed reports are tracked privately in a GitHub Security Advisory when practical.
4. A fix or documented mitigation is tested on all supported Python versions. Critical
   and high findings block a release unless an explicit, time-bounded non-exploitability
   analysis is recorded.
5. The maintainer requests a CVE through GitHub when the issue meets CVE criteria, then
   publishes the advisory and release notes after a fixed release is available.
6. Secret exposures trigger immediate revocation before normal remediation work.

The detailed dependency, exception, disclosure, and release policy is in
[compliance/VULNERABILITY_MANAGEMENT.md](compliance/VULNERABILITY_MANAGEMENT.md).

## Responsible disclosure

We ask that you:
- Allow reasonable time for a fix before public disclosure
- Not access or modify data belonging to other users
- Not perform denial-of-service attacks against our infrastructure

We commit to:
- Crediting reporters in the release notes (unless you prefer to remain anonymous)
- Not pursuing legal action against good-faith security researchers
- Communicating resolution timeline within one week of receipt
