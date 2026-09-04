# WhitePact launch copy

Use only after the linked quickstart, release, and MCP evidence remain current.

## One line

WhitePact is an open-source runtime authority layer that decides whether an AI
agent action may proceed, be redacted, require approval, be denied, or be quarantined.

## 50 words

AI agents should not be the final authority over their own actions. WhitePact sits
between intelligence and execution, evaluating identity, delegated authority, risk,
policy, context, and approval requirements. It returns one of five deterministic
decisions and can record evidence explaining why. It integrates through MCP, API,
and Python.

## Technical description

WhitePact is an MIT-licensed runtime authority layer for AI agents and autonomous
systems. An agent proposes an action; WhitePact evaluates identity, delegated
authority, constraints, risk tier, organization policy, content controls, approval
requirements, and recent behavior before an executor may run it. The deterministic
gateway returns ALLOW, ALLOW_WITH_REDACTION, REQUIRE_APPROVAL, DENY, or QUARANTINE.
The repository includes a Python API, REST surface, MCP server, approval and evidence
models, supply-chain checks, and supporting AI-governance evaluators. Release v1.2.6
publishes a wheel, sdist, CycloneDX SBOM, checksums, a signed tag, and verifiable
GitHub attestations. WhitePact publishes self-assessments and control mappings, not
claims of ISO, SOC 2, NIST, EU AI Act, or CSA certification.

## Show HN draft

**Title:** Show HN: WhitePact – independent runtime authority for AI agents

AI agents can choose actions, but they should not be the final authority over whether
those actions execute. I built WhitePact as an independent, deterministic layer
between an agent and its tools. It evaluates delegated authority, policy, risk,
approval requirements, and content, then returns one of five explicit outcomes.

The quickest demo proposes an $8,500 payment and shows WhitePact hold it for human
approval without executing anything. It runs locally with no model key. The same
authority surface is available over MCP (30 tools in v1.2.6), API, and Python.

I would especially value review of the enforcement boundary, threat model, MCP client
behavior, and evidence model. The project is early: no customer, partnership,
independent-pentest, or certification claim is implied.

## GitHub launch post

WhitePact asks a narrow question: who decides whether an AI agent action actually
runs? The open-source runtime gateway separates proposal from permission and returns
ALLOW, REDACT, APPROVAL, DENY, or QUARANTINE with inspectable reasons. Try the
no-key demo, verify the v1.2.6 artifacts, or help test an MCP client.

## MCP community post

WhitePact v1.2.6 is an MCP-compatible authority and governance server with 30 tools
and 20 advertised resources, derived from its live definitions and protected by a
count-drift check. I am looking for independent client verification; compatible,
tested, listed, submitted, and approved are tracked as separate states.

## Security-community post

WhitePact puts deterministic authority checks before an agent executor and documents
the enforcement boundary, threat model, release provenance, and known limitations.
Independent review is welcome, especially around tenant isolation, authorization,
approval replay, MCP transport/auth, and deployment assumptions. This is not a claim
of an independent penetration test.

## Design-partner invitation

Evaluating a bounded autonomous-agent workflow? Share a reversible action, authority
model, approval rule, and failure condition in issue #58. Participation does not
imply deployment, partnership, customer status, or endorsement.

## Contributor invitation

Useful independent work includes MCP client verification, security review,
integrations, documentation, benchmarks, and focused good-first issues. See
`CONTRIBUTING.md` and issues #56–#58. Real review history matters more than vanity
activity; no affiliation is implied.
