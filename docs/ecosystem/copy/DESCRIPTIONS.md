# Submission copy

Use these paragraphs as-is. They describe the open-source project and the
published package. They do not describe an unreleased build as something
`pip` can install.

Source commit audited: `35488a68e587df2adfdb1ceaad44001faca524a4`.

## 50-word description

WhitePact is open-source runtime authorization and governance for autonomous AI agents. The MIT-licensed Python distribution is rai-governance-platform. It can allow, redact, hold for human approval, deny, or quarantine an action before execution. Published releases support self-hosted technical evaluation from the documented package. The hosted enterprise release remains under operational qualification.

## 100-word description

WhitePact is open-source runtime authorization and governance for autonomous AI agents. Intelligence may propose an action. WhitePact decides whether that action may proceed. The public Python distribution is rai-governance-platform under the MIT license. A self-hosted evaluation uses the latest published release, which was 1.2.6 on 2026-10-09, or a qualified source checkout. The runtime can allow an action, redact arguments, require human approval, deny it, or quarantine it. Decisions are deterministic code, not a model call. An MCP server is included for clients that speak the Model Context Protocol. The hosted enterprise service is undergoing operational qualification and is not offered here as a worldwide production launch.

## 200-word description

WhitePact is an open-source security and governance project for autonomous AI agents. Its public name is WhitePact. Its Python distribution name is rai-governance-platform. Do not install a package named whitepact. On 2026-10-09, PyPI’s newest release of rai-governance-platform was 1.2.6. The source tree audited for this submission is 1.3.1 and has not been published as that version. Install the published release, or evaluate a qualified source checkout by following the repository instructions.

The runtime sits in front of an agent action. It can allow the action, allow it with redacted arguments, require a human approval, deny it, or quarantine it. Denied and approval-gated decisions do not receive an execution authorization. Short-lived grants expire. A consumed execution authorization is refused on replay. Evidence records store argument field names rather than raw argument values. Organization checks close cross-tenant reads in the sovereign resource guard.

WhitePact also includes an MCP server. The hosted MCP endpoint requires a bearer credential and is not an anonymous demo. The repository includes LangChain, LangGraph, and Google ADK trust-gate adapters. It does not include LlamaIndex, CrewAI, or AutoGen adapters. WhitePact holds an OpenSSF Best Practices silver badge for the open-source project. That badge is not a product security certification. The managed enterprise release is still undergoing operational qualification.

## Technical developer description

WhitePact’s installable distribution is the PyPI project rai-governance-platform. Import the library as responsibleai. The source tree’s preferred product command is whitepact, but the published 1.2.6 wheel still maps that console script to biasbuster.cli:main. In that same wheel, whitepact-mcp starts the stdio MCP server and whitepact-mcp-http starts the HTTP server. Python 1.2.6 requires Python 3.11 or 3.12. A local dashboard extra is installed with pip install "rai-governance-platform[dashboard]". The repository also contains an unpublished Python client package named rai-client and a TypeScript client under sdk/typescript. Neither client was on PyPI or npm on 2026-10-09. Container packaging exists as a Dockerfile and Helm chart in source. No public Docker Hub repository was found. MCP registry metadata in this branch pins the stdio package to rai-governance-platform 1.2.6. Do not point installers at 1.3.1 until that version exists on PyPI.

## AI security description

WhitePact is a runtime authorization layer for agent actions. Before a governed action executes, policy and authority checks can allow it, redact it, hold it for a person, deny it, or quarantine it. The denial path does not issue an execution authorization. Human approval is a separate state and is not itself permission to execute. Grants are short-lived. Replaying a consumed authorization is refused. Evidence of a decision keeps argument names, not raw values. These controls apply where the project’s governed paths are actually wired. The self-hosted stdio MCP transport has no organization identity and is not the hosted enforcement path. WhitePact does not claim complete protection against every attack.

## Open-source project description

WhitePact is a founder-led MIT-licensed project maintained by Guruprasath Annadurai. The repository is https://github.com/Guruprasath-Annadurai/Whitepact. Contributions follow CONTRIBUTING.md, including the Developer Certificate of Origin. Security reports go through GitHub private vulnerability reporting or the contact in SECURITY.md. The project has an OpenSSF Best Practices silver badge at https://www.bestpractices.dev/projects/14112. Support is best-effort community support, not a contractual SLA. The current source version is 1.3.1. The newest published package on 2026-10-09 was 1.2.6.

## MCP-focused description

WhitePact publishes an MCP server named io.github.Guruprasath-Annadurai/whitepact. The official registry’s latest listing on 2026-10-09 was version 1.2.3 and still pinned PyPI package 1.2.2. The stdio install that matches the newest PyPI release is uvx --from rai-governance-platform==1.2.6 whitepact-mcp. A hosted Streamable HTTP endpoint and a legacy SSE endpoint respond at whitepact-mcp-http.onrender.com and require a bearer credential. On 2026-10-09 their public server card reported 30 tools and 20 resources, with authentication required. Source tool definitions also include one test tool that the hosted card does not advertise. This branch’s server.json proposes a registry update to package pin 1.2.6. That update is not published.

## Enterprise buyer description

WhitePact can be evaluated as self-hosted open-source software using the published rai-governance-platform release or a qualified source tree. Demonstrated capabilities in this repository include a five-way runtime decision, human approval gating, short-lived grants, replay refusal for a consumed authorization, tenant-scoped resource checks, and decision evidence that omits raw argument values. A public site at https://whitepact.com responded on 2026-10-09 as a governance dashboard reporting version 1.2.6. That response is not a global production authorization for a managed enterprise service. Buyers should not treat the hosted enterprise offer as generally available.

## Founder and project story

Guruprasath Annadurai maintains WhitePact as a founder-led open-source project. The code is MIT licensed. The project’s purpose is to put a runtime decision in front of autonomous agent actions: allow, redact, require approval, deny, or quarantine. The work is public at https://github.com/Guruprasath-Annadurai/Whitepact. The Python package people install is rai-governance-platform. The hosted enterprise release is still in operational qualification, so this story does not claim a worldwide launch, a customer list, or a certification.

## Tags, categories, and keywords

Tags: open-source, ai-agents, ai-governance, ai-security, mcp, mcp-server, runtime-authorization, policy-engine, python, mit-license.

Categories to select when a form offers them: developer tools, security, open source, AI infrastructure, MCP servers.

Do not select a category that requires a certified cloud marketplace product, a generally available SaaS subscription, or a native LlamaIndex, CrewAI, or AutoGen integration.

## Public links

- Repository: https://github.com/Guruprasath-Annadurai/Whitepact
- License: https://github.com/Guruprasath-Annadurai/Whitepact/blob/main/LICENSE
- PyPI: https://pypi.org/project/rai-governance-platform/
- Security contact: https://github.com/Guruprasath-Annadurai/Whitepact/security/advisories/new
- OpenSSF Best Practices: https://www.bestpractices.dev/projects/14112
- Public site checked 2026-10-09: https://whitepact.com

## Installation

```bash
pip install "rai-governance-platform[dashboard]==1.2.6"
whitepact-mcp
```

The published 1.2.6 `whitepact` command is the legacy BiasBuster CLI, not the source tree’s `whitepact.cli:main` entrypoint. Use `whitepact-mcp` for the MCP server. There is no PyPI project named whitepact. Version 1.3.1 of rai-governance-platform was not on PyPI on 2026-10-09.

## License

MIT License. Copyright (c) 2026 Guruprasath Annadurai. The software is provided as-is, without warranty.

## Availability and limitations

Self-hosted technical evaluation is available from the published package or from qualified source. The hosted MCP endpoint requires authentication. A public self-serve flow that issues that credential was not verified. The dashboard at whitepact.com reported version 1.2.6 on 2026-10-09. The managed enterprise release has not received final global production authorization. OpenSSF Best Practices silver is a project badge, not a certification of the hosted service. No Docker Hub image was found. No Hugging Face Space was published by this work.

## Support and security

- Security email: annaduraiguruprasath7@gmail.com with subject `[WhitePact Security]`
- Private advisories: https://github.com/Guruprasath-Annadurai/Whitepact/security/advisories/new
- Public issues: https://github.com/Guruprasath-Annadurai/Whitepact/issues
- Support policy: SUPPORT.md states best-effort community support and not a contractual SLA.
