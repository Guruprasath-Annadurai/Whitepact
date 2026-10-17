# Provider compatibility — APEX reconciliation

Current M13 classification as of2026-10-16. GLOBAL PRODUCTION NO-GO.
No provider credentials, paid API calls, hosted rollout or directory submission
used in this qualification. Historical integration notes remain historical;
their VERIFIED labels do not qualify the current APEX commit.

| Provider surface | APEX status | Supported contract / remaining gate |
|---|---|---|
| OpenAI Responses MCP | BLOCKED | Official remote-MCP contract documented; no authorized current provider roundtrip |
| Claude API / Claude clients | BLOCKED | Official MCP integration surfaces documented; separate client/OAuth acceptance missing |
| Gemini SDK / clients | BLOCKED | Official SDK MCP integration documented; no actual provider invocation |
| Grok API / interactive connector | BLOCKED | Remote MCP API documented; historical August receipt not current-head verification |
| GitHub Copilot | BLOCKED | Client and organization MCP policy required; no actual authorized client session |
| Microsoft Copilot Studio | NOT_TESTED | Distinct product from GitHub Copilot; no interchangeable acceptance claimed |
| Amazon Q Developer | BLOCKED | Official remote HTTP and local-process configuration supported; local legacy config needs current client acceptance |
| Cursor | BLOCKED | Official stdio/HTTP/SSE configuration documented; no actual authenticated Cursor roundtrip |
| Mistral connectors / Le Chat | BLOCKED | Current connector registration/OAuth contract exists; old transport/submission-only blocker is not a current technical conclusion |
| AWS AgentCore | BLOCKED | Streamable HTTP protocol, ARM64/port8000/session contract documented; no provisioning authorized |

`PROTOCOL_VERIFIED` applies only to individually evidenced WhitePact local
transport tests, not any row above. `CONFIG_READY` requires validated client
configuration for its exact product/version, not merely an example file.
`REAL_PROVIDER_VERIFIED` requires an actual authenticated provider roundtrip on
the current implementation. None is asserted here. External identities/OAuth,
client policy and protocol session continuity cannot substitute for server-side
execution authorization; especially provider-side tool approvals cannot qualify
WhitePact approval or delegated authority.

## Primary-source checks

- [OpenAI remote MCP](https://developers.openai.com/api/docs/guides/tools-connectors-mcp): discovery and remote invocation through Responses.
- [Anthropic MCP surfaces](https://docs.anthropic.com/en/docs/mcp): API/client integrations require separate qualification.
- [Gemini function calling and MCP](https://ai.google.dev/gemini-api/docs/function-calling/): SDK support is not a WhitePact provider test.
- [xAI remote MCP](https://docs.x.ai/developers/tools/remote-mcp): server URL/allowed-tools contract; Responses-style require_approval is not supported there, so never infer its enforcement.
- [GitHub Copilot MCP](https://docs.github.com/en/copilot/how-tos/copilot-in-your-ide/customize-copilot/extend-copilot-with-tools-and-context/extend-copilot-chat-with-mcp): organization policy and client configuration matter.
- [Amazon Q configuration](https://docs.aws.amazon.com/amazonq/latest/qdeveloper-ug/command-line-mcp-config-CLI.html): local and remote servers are distinct configurations.
- [Cursor MCP](https://prod.cursor.com/docs/mcp): supported transport and authentication configuration.
- [Mistral connectors](https://docs.mistral.ai/studio/connectors), [management](https://docs.mistral.ai/studio/connectors/management): register server, authenticate, discover, invoke; API is public preview.
- [AgentCore protocol](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-mcp-protocol-contract.html): streamable HTTP/container/session requirements; documentation review only.

No external listing or hosted endpoint was contacted to manufacture acceptance.
Repository examples containing a hosted URL are configuration history, not an
approved operational endpoint under the production NO-GO.
