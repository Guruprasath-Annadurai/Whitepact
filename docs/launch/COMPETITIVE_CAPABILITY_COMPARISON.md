# Competitive capability comparison

Date of public documents consulted: 2026-10-09. This is not a
performance ranking and not a certification. No customer endorsement is
claimed. WhitePact behavior below is what this tree's tests exercise,
not an independent production verdict.

| Capability | WhitePact on this tree | Documented competitor capability | Gap or advantage |
| --- | --- | --- | --- |
| Agent identity | Organization-bound principals. OIDC, SAML, and verifiable-credential admission fail closed for an unknown tenant. Tests in `tests/test_p0_tenant_admission.py` and `tests/test_mcp_verified_principal.py`. | Microsoft Entra Agent ID issues agent identities and can target them in Conditional Access. Google Cloud Agent Identity is a per-agent SPIFFE identity with mTLS and DPoP. | WhitePact does not provide a globally trusted agent directory or SPIFFE attestation. Entra and Google do not replace WhitePact's per-action constitutional decision. |
| Independent enforcement | The gateway denies an action the authority did not grant. The container runner is a trusted file, not caller workspace input. | Entra evaluates policy when a token is issued. The resource then trusts the token. Google IAM and Principal Access Boundary constrain credentials. | Token issuance is a different boundary from WhitePact's action gateway. WhitePact's advantage is the explicit deny of an ungranted action even after a session exists. That was retested locally, not in a customer tenant. |
| MCP protection | Hosted metering follows an authorization decision. Governance denial does not consume allowed quota (`tests/test_launch_gate_hosted_metering.py`). | Cloudflare Access can front MCP servers, and MCP portal logs can export through Logpush on Enterprise. Google Model Armor can inspect and block MCP tool calls with project floor settings. | WhitePact does not ship a global edge or DLP product. Cloudflare and Google do not show, in the cited docs, an append-only per-organization evidence chain signed outside the application database. |
| Least privilege | Authority is an allow-list of action types. Container execution drops capabilities, uses a read-only root, and defaults to no network. | Google documents least privilege for agent identities and IAM deny policies. Entra agent-identity policies can block; autonomous agent identities have no step-up remediation in the cited guide. | WhitePact's container profile is implemented and unit-tested. Live cgroup proof was skipped because Docker was not running. |
| Approval and revocation | Resume refuses an approval with no requester (`tests/test_launch_gate_resume_identity.py`). | Entra Conditional Access can block a risky agent. The cited page does not describe a human approval object bound to one action digest. | Action-digest approval is WhitePact's model. Enterprise identity vendors center token policy. Both are needed; neither was compared in a joint deployment. |
| Evidence | Signed publication detects rollback and a rewritten head. Live object lock is not provisioned. | Cloudflare Logpush retains MCP portal logs in a customer-chosen store. Entra sign-in logs are Microsoft's audit plane. | A customer-controlled SIEM is more operationally mature than WhitePact's unprovisioned R2 target. WhitePact's signed head is a narrower integrity control and is only proven locally. |
| Enterprise identity | OIDC, SAML, and VC admission require a pre-provisioned tenant. | Entra, Google Identity, and Cloudflare Access are production identity planes with broad IdP catalogs. | WhitePact is not a replacement IdP. External enterprise IdP certification on this tree was not performed. |
| Reliability | Fail-closed paths exist. Backup restore and multi-replica failover were not drilled. | The cited vendors operate global control planes. No uptime figure is copied here because this candidate has no comparable measurement. | Operational maturity is a gap. |
| Latency | In-process kernel p50 about 0.006 ms on one core, no database. HTTP SLO not approved and not remeasured. | No vendor latency number is cited. Publishing one would be an invented comparison. | No latency advantage is claimed. |
| Administration and developer experience | HTTP audit export returned one tenant's rows with hash columns. A full browser onboarding journey was not run. | Vendor consoles are their supported admin UX. | WhitePact's console was not re-qualified in a browser on this tree. |
| Tenant separation | Audit export for org A did not contain org B. SSO admission will not create a tenant from a claim. | Cloud IAM and Access policies are tenant-scoped in the vendor account model. | Local tests passed. A hostile multi-tenant cloud deployment was not run. |
| Incident investigation | SIEM JSONL export exists. Chain verification is not an external witness. | Cloudflare and Entra ship retained logs to customer tools. | WhitePact can export. Retention on an independent store is blocked. |

## Additional vendors (consulted 2026-10-10)

These are content-and-conversation guardrail libraries and governance registries. They
overlap WhitePact in part and are not like-for-like with an independent pre-execution
authorization layer. Statements are taken from each vendor's own documentation; no
independent review or customer evidence was found, and no benchmark is compared.

| Vendor | Documented capability | Relation to WhitePact | Gap or advantage |
| --- | --- | --- | --- |
| NVIDIA NeMo Guardrails | Open-source toolkit. Five rail types: input, dialog, retrieval, execution, output. Execution rails "control tool and action calls". Configured in YAML plus Colang flows. Built-in flows cover jailbreak detection, PII masking, topic control, self-check moderation and hallucination checks. | Overlaps on tool-call gating. Rails run in the application's own process and configuration. The cited pages do not describe a separate identity-bound authorization decision, approval object or tamper-evident evidence chain. | NeMo has a far broader catalogue of content rails and a larger ecosystem. WhitePact's distinct claim is an independent authorization decision with human delegation, approvals, evidence and isolated execution. That claim here rests on this repository's tests, not on an outside assessment. |
| Guardrails AI | Open-source `Guard` composed of validators from a Hub. Validators chain into input and output guards; custom validators are supported; guards are best deployed server-side. A July 2026 README note says validators are moving to standard PyPI packages and hosted remote inferencing is being discontinued. | Output and input validation. The cited pages describe validating text, not authorizing an agent action under delegated authority. | Guardrails AI has a mature validator hub. WhitePact has no comparable validator catalogue. |
| Lakera Guard | Hosted API. `/v2/guard` takes messages and a project id and returns `flagged`. Policies hold input and output detectors with thresholds; `prompt_attack` is the prompt-injection detector. A project in Detection mode never sets `flagged`. Guidance recommends scanning tool outputs and retrieved data. | Detects prompt injection and data leakage in content. Does not decide whether an agent may act. A detector verdict is an input to a decision, not an authority grant. | Lakera's detection models are trained on its own attack data; WhitePact ships no comparable detector (its heuristics are keyword and regex). The two can sit in series. |
| Credo AI (Agent Registry, Agent Governor) | Registry: agent inventory, agent cards, autonomy classification, reviewers and approvals (public preview). Governor: governance-as-code in the agent harness, starting with Claude Code (research preview); policy resolves to allow, block, escalate or advise with a structured decision record; custom policy upload is marked "coming soon". | Closest in intent: runtime allow/block/escalate with a decision record. Both products are described by the vendor as early. All capability statements are the vendor's own. | Credo is a governance-programme platform with a registry. WhitePact does not have that breadth. WhitePact's decision engine is a separate, tested kernel with approvals, short-lived execution permits and evidence. Neither side has an independent comparison. |

Not claimed: that WhitePact is better, faster or more complete than any vendor above.

Sources:

- https://learn.microsoft.com/en-us/entra/identity/conditional-access/agent-id
- https://learn.microsoft.com/en-us/entra/identity/conditional-access/howto-target-agent-identities
- https://docs.cloud.google.com/iam/docs/agent-identity-overview
- https://docs.cloud.google.com/model-armor/model-armor-mcp-google-cloud-integration
- https://developers.cloudflare.com/cloudflare-one/access-controls/ai-controls/mcp-portals/
- https://developers.cloudflare.com/changelog/post/2026-02-27-mcp-portal-logpush/
- https://docs.nvidia.com/nemo/guardrails/latest/about/rail-types.html
- https://github.com/NVIDIA-NeMo/Guardrails
- https://www.guardrailsai.com/docs/concepts/hub
- https://github.com/guardrails-ai/guardrails
- https://docs.lakera.ai/docs/quickstart
- https://www.credo.ai/agent-governor
- https://www.credo.ai/ai-agent-registry
