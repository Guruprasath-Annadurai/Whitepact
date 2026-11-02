<!-- WhitePact public documentation. This repository deliberately contains no proprietary implementation. -->

<div align="center">

# WhitePact

### Intelligence may propose. WhitePact decides.

**Runtime governance and assurance for AI agents, automated workflows and MCP-connected systems.**

[Python package](https://pypi.org/project/rai-governance-platform/) · [MCP Registry](https://registry.modelcontextprotocol.io/) · [Smithery listing](https://smithery.ai/servers/guruprasathannadurai-official/whitepact) · [Report a security issue](mailto:annaduraiguruprasath7@gmail.com?subject=WhitePact%20Security)

</div>

---

## Why WhitePact?

AI agents do more than generate text. They call tools, access information and propose actions that can change real systems.

**An AI model proposing an action is not the same as an authorized system permitting that action.**

WhitePact is designed to help developers put policy, identity, approvals, risk assessment and accountable evidence between an autonomous agent's proposal and its execution. It is an additional governance layer—not a substitute for secure application design or a guarantee that every AI risk can be eliminated.

## What WhitePact covers

| Area | What it is intended to help with |
| --- | --- |
| **Runtime governance** | Five structured decision outcomes: `ALLOW`, `ALLOW_WITH_REDACTION`, `REQUIRE_APPROVAL`, `DENY` and `QUARANTINE`. |
| **Delegated authority & human approval** | Explicitly limit sensitive operations and involve authorized reviewers. |
| **Evidence & auditability** | Preserve governance decision records for investigation and review. |
| **MCP and agent integrations** | Bring governance checks into compatible tool and agent workflows. |
| **AI trust & risk assessments** | Trust scoring, guardrails, bias evaluation, hallucination-risk signals and compliance mapping. |
| **Operational insight** | Cost awareness, drift monitoring, incident-oriented assessment and evaluation tooling. |

These are **product areas and published software capabilities**, not a claim that every component is deployed, externally audited or generally available as an enterprise service. Feature availability depends on the particular released package and deployment.

## Start with the published open-source package

The existing package is distributed on PyPI as **`rai-governance-platform`**, with Python **3.11+** support. The historical distribution and import names are retained for compatibility; WhitePact is the product name.

**Latest PyPI release verified on 1 November 2026: `1.2.6`, released 30 August 2026.**

```bash
# Core package installation:
python -m pip install "rai-governance-platform==1.2.6"

# For the `whitepact` CLI, explicit installation of `rich` is required for v1.2.6:
python -m pip install "rai-governance-platform==1.2.6" rich

# For developer-facing MCP support and CLI tools:
python -m pip install "rai-governance-platform[mcp]==1.2.6" rich
```

> **Note on CLI Dependency:** For the published 1.2.6 distribution, the `whitepact` CLI entry point requires `rich`, which was omitted from the base package dependencies in `pyproject.toml`. Install `rich` explicitly alongside the package to enable the command-line interface.

The package documentation identifies `whitepact-mcp` as a self-hosted MCP entry point. Configure and validate the appropriate local service, authentication and dependencies for your environment before using it with an MCP client.

See [the published PyPI release](https://pypi.org/project/rai-governance-platform/) for the actual distribution files, package metadata, supported extras, provenance and accompanying open-source license.

**Important:** Self-hosted package availability does not prove the availability of a separate hosted MCP service. Public directory listings may contain stale or unreachable endpoints. Check live connectivity and authentication before relying on any remote connection.

## The open-source / enterprise separation

WhitePact follows a separated publication model:

| Public materials | Private or restricted materials |
| --- | --- |
| This product overview and approved public documentation | Unreleased enterprise platform source |
| Previously published PyPI distributions under their accompanying licenses | Privileged runtime authority and operational integrations |
| Explicitly approved open-source SDKs or client components, if separately published | Private deployment, infrastructure and security evidence |
| Public installation, contact and distribution information | Credentials, customer data and internal incident records |

**This is a documentation repository, not the WhitePact enterprise source repository.** It must not contain private source code, internal configuration, security reports, tokens, proprietary deployment files or confidential customer information.

Past MIT-licensed open-source releases retain the rights provided by the licenses under which they were distributed. Making a development repository private does **not** retroactively remove those rights or recall copies already distributed.

## Current product readiness

**Status as of 1 November 2026:** The broader WhitePact enterprise runtime is still undergoing security and integration qualification. **Global enterprise production deployment has not been authorized.**

Successful component tests, a published package, badges or an MCP listing must not be treated as an end-to-end security certification or proof of production readiness.

Users may evaluate the published open-source package according to its release-specific documentation and license. No claim is made here that a new enterprise hosted service, production identity-verification workflow or public SaaS launch is generally available.

## Integration ecosystem

WhitePact has a published MCP-related software offering and third-party directory listings. Listings establish discoverability, **not** service uptime or production acceptance.

- [PyPI: rai-governance-platform](https://pypi.org/project/rai-governance-platform/) — versioned downloadable Python distribution.
- [Official MCP Registry](https://registry.modelcontextprotocol.io/) — search for WhitePact; review the listing's current package and remote metadata before connecting.
- [Smithery: WhitePact](https://smithery.ai/servers/guruprasathannadurai-official/whitepact) — third-party listing; connection availability must be checked independently.

Do not send production data, credentials or consequential instructions to an endpoint solely because it appears in a directory.

## Responsible security reporting

Please **do not** publish exploitable vulnerability details, private tokens or customer information in public issues. Contact [WhitePact security](mailto:annaduraiguruprasath7@gmail.com?subject=WhitePact%20Security) with a concise impact statement and safe reproduction details. This repository's public issues are for documentation and product-discovery matters only.

## Licensing and rights

The published `rai-governance-platform` release is distributed under the **MIT License**. See the license included with the specific distributed software.

This public documentation repository does not grant a license to any privately held, unpublished implementation, and it does not change licenses already granted for previously released source or packages. Product and brand use may be governed separately from software copyright licenses.

---

<div align="center">

**Govern the action. Preserve the evidence. Keep authority explicit.**

</div>
