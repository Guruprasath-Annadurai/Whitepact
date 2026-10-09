# Platform eligibility matrix

Audit date: 2026-10-09. Source commit: `35488a68e587df2adfdb1ceaad44001faca524a4`.

Statuses mean preparation state only. None of these rows is a submission, an approval, or a new publication made by this lane.

| Status | Meaning |
|---|---|
| GREEN | Ready for the owner to act. Two of the three are external directories. GitHub Discussions is a first-party community post, not an external directory. |
| YELLOW | A minor fix or an external prerequisite remains. |
| RED | A mandatory requirement is not met. |
| BLUE | Already live on the authoritative site checked below. |
| GREY | The free route or the live listing could not be verified. |

Platforms in this inventory: 45. GREEN 3. YELLOW 5. RED 10. BLUE 7. GREY 20.

Of those 45, the actionable split is 2 external directory submissions (Future Tools, Ignlab Launch), 1 first-party community post (GitHub Discussions), 7 already-live entries, 5 conditional platforms, 10 blocked platforms, and 20 unverified platforms. The missing-inventory defect is not a sixth conditional platform.

Machine-readable source: `docs/ecosystem/inventory.json`.

| ID | Platform | Group | Status | Free | Deploy required | Moderation | Official URL |
|---|---|---|---|---|---|---|---|
| `github-topics` | GitHub Topics | A | BLUE | yes | false | false | https://github.com/Guruprasath-Annadurai/Whitepact |
| `devhunt` | DevHunt | A | YELLOW | yes | false | true | https://devhunt.org/faq |
| `future-tools` | Future Tools | A | GREEN | yes | false | true | https://futuretools.io/submit-a-tool |
| `ignlab-launch` | Ignlab Launch | A | GREEN | yes | false | true | https://launch.ignlab.net/submit.html |
| `github-discussions` | GitHub Discussions | A | GREEN | yes | false | false | https://github.com/Guruprasath-Annadurai/Whitepact/discussions |
| `owasp-genai` | OWASP GenAI Security | A | YELLOW | yes | false | true | https://genai.owasp.org/contribute/ |
| `openinfra` | OpenInfra community | A | GREY | unverified | false | true | https://openinfra.org/ |
| `mcp-registry` | Official MCP Registry | B | BLUE | yes | false | true | https://registry.modelcontextprotocol.io/v0/servers?search=io.github.Guruprasath-Annadurai/whitepact&version=latest |
| `glama` | Glama | B | BLUE | yes | false | true | https://glama.ai/mcp/servers/Guruprasath-Annadurai/Whitepact |
| `smithery` | Smithery | B | BLUE | yes | false | true | https://smithery.ai/servers/guruprasathannadurai-official/whitepact |
| `mcp-market` | MCP Market | B | BLUE | unverified | false | true | https://mcpmarket.com/server/whitepact |
| `mcpbeat` | MCPBeat | B | GREY | unverified | false | true | https://mcpbeat.com/mcp-servers/guruprasath-annadurai/whitepact/ |
| `alternativeto` | AlternativeTo | B | GREY | unverified | false | true | https://alternativeto.net/software/whitepact/ |
| `openssf-best-practices` | OpenSSF Best Practices | B | BLUE | yes | false | true | https://www.bestpractices.dev/projects/14112 |
| `pypi` | PyPI | B | BLUE | yes | false | true | https://pypi.org/project/rai-governance-platform/ |
| `cncf-landscape` | CNCF Landscape | C | RED | yes | false | true | https://github.com/cncf/landscape |
| `huggingface-spaces` | Hugging Face static Spaces | C | YELLOW | yes | false | true | https://huggingface.co/docs/hub/spaces-overview |
| `docker-hub` | Docker Hub | C | RED | yes | true | true | https://hub.docker.com/ |
| `langchain` | LangChain | C | YELLOW | unverified | false | true | https://github.com/Guruprasath-Annadurai/Whitepact/blob/35488a68e587df2adfdb1ceaad44001faca524a4/src/responsibleai/integrations/langchain_middleware.py |
| `langgraph` | LangGraph | C | YELLOW | unverified | false | true | https://github.com/Guruprasath-Annadurai/Whitepact/blob/35488a68e587df2adfdb1ceaad44001faca524a4/src/responsibleai/integrations/langgraph_gate.py |
| `llamaindex` | LlamaIndex | C | RED | unverified | false | true | https://developers.llamaindex.ai/ |
| `crewai` | CrewAI | C | RED | unverified | false | true | https://www.crewai.com/ |
| `autogen` | AutoGen and successor ecosystem | C | RED | unverified | false | true | https://github.com/microsoft/autogen |
| `pulsemcp` | PulseMCP | C | GREY | unverified | false | true | https://www.pulsemcp.com/ |
| `product-hunt` | Product Hunt | D | GREY | unverified | true | true | https://www.producthunt.com/ |
| `peerlist-launchpad` | Peerlist Launchpad | D | GREY | unverified | false | true | https://peerlist.io/launchpad |
| `uneed` | Uneed | D | GREY | unverified | false | true | https://www.uneed.best/ |
| `startup-stash` | Startup Stash | D | GREY | unverified | false | true | https://startupstash.com/ |
| `ai-tools-directory` | AI Tools Directory | D | GREY | unverified | false | true | https://aitoolsdirectory.com/submit-tool |
| `the-next-ai` | The Next AI | D | GREY | unverified | false | true | https://www.thenextai.com/ |
| `ai-superhub` | AI SuperHub | D | GREY | unverified | false | true | https://aisuperhub.com/submit |
| `hyzenpro` | HyzenPro | D | GREY | unverified | false | true | https://hyzenpro.com/ |
| `codehype` | CodeHype | D | GREY | unverified | false | true | https://codehype.com/ |
| `launching-next` | Launching Next | D | GREY | unverified | false | true | https://www.launchingnext.com/ |
| `startup-buffer` | Startup Buffer | D | GREY | unverified | false | true | https://startupbuffer.com/ |
| `microsaas-directory` | MicroSaaS Directory | D | GREY | unverified | true | true | https://microsaas.directory/ |
| `saas-hunt` | SaaS Hunt | D | GREY | unverified | true | true | https://saashunt.best/ |
| `saaspa-ge` | Saaspa.ge | D | GREY | unverified | false | true | https://www.saaspa.ge/ |
| `sidehunt` | Sidehunt | D | GREY | unverified | false | true | https://sidehunt.io/submit |
| `firsto` | Firsto | D | GREY | unverified | false | true | https://firsto.co/ |
| `aws-marketplace` | AWS Marketplace | E | RED | no | true | true | https://aws.amazon.com/marketplace |
| `github-marketplace` | GitHub Marketplace | E | RED | unverified | true | true | https://github.com/marketplace |
| `csa-star` | Cloud Security Alliance STAR | E | RED | no | true | true | https://cloudsecurityalliance.org/star |
| `linux-foundation` | Linux Foundation project hosting | E | RED | no | false | true | https://www.linuxfoundation.org/projects |
| `openssf-membership` | OpenSSF formal membership | E | RED | no | false | true | https://openssf.org/join/ |

## Evidence, owner action, and blockers

### GitHub Topics (`github-topics`)

Status: BLUE.

Evidence: GitHub API on 2026-10-09 listed 14 topics: agentic-ai, ai-agents, ai-governance, ai-safety, ai-security, llm-security, mcp, mcp-server, openssf, policy-engine, responsible-ai, runtime-security, supply-chain-security, zero-trust.

Owner action: Optional: add up to six more accurate topics. Fourteen topics are already set.

Change in this branch: None. Topics are repository settings, not source.

Remaining blocker: None for the current topics.

### DevHunt (`devhunt`)

Status: YELLOW.

Evidence: https://devhunt.org/faq fetched 2026-10-09: listing is free, free launches wait in a queue, and paid week selection is optional ($19 / $49 on that page).

Owner action: Create the listing with a GitHub login after an authentic product screenshot exists.

Change in this branch: Submission copy is in docs/ecosystem/copy/DESCRIPTIONS.md.

Remaining blocker: The official FAQ requires a logo and screenshots. This repository has logo assets and no authentic product-UI screenshot.

### Future Tools (`future-tools`)

Status: GREEN. Channel: external directory.

Evidence: Submit page returned 200. FAQ text fetched the same day says the site is kept free for people who submit tools and that inclusion is not guaranteed.

Owner action: Submit the form. Do not send an affiliate or waitlist URL.

Change in this branch: Submission copy only.

Remaining blocker: Manual review can still reject the listing. The live homepage title is a dashboard, not a marketing page.

### Ignlab Launch (`ignlab-launch`)

Status: GREEN. Channel: external directory.

Evidence: https://launch.ignlab.net/ and submit.html fetched 2026-10-09. The site states submission is free, has no account, and has no featured-listing fee.

Owner action: Paste the copy and submit. No account is required by the official page.

Change in this branch: Submission copy only.

Remaining blocker: Reviewers must approve it before it is public. Screenshot is optional; logo URL can be the repository logo.

### GitHub Discussions (`github-discussions`)

Status: GREEN. Channel: first-party repository community activity, not an external directory.

Evidence: GitHub GraphQL on 2026-10-09 returned categories Announcements, General, Ideas, Polls, Q&A, and Show and tell.

Owner action: Post the draft in Show and tell or Announcements. Do not post from this lane.

Change in this branch: Draft text is in FOUNDER_MANUAL_ACTIONS.md.

Remaining blocker: None. Discussions are enabled.

### OWASP GenAI Security (`owasp-genai`)

Status: YELLOW.

Evidence: https://genai.owasp.org/ and https://genai.owasp.org/contribute/ returned 200 on 2026-10-09.

Owner action: Offer a factual project note to the project’s public contribution channel. Do not claim an OWASP listing.

Change in this branch: Contribution note is in FOUNDER_MANUAL_ACTIONS.md.

Remaining blocker: No WhitePact page on the OWASP GenAI site was verified, and a specific accepted contribution slot was not identified.

### OpenInfra community (`openinfra`)

Status: GREY.

Evidence: https://openinfra.org/ returned 200. That confirms the organization site, not a WhitePact submission route.

Owner action: Confirm the current community-join page before participating.

Change in this branch: None.

Remaining blocker: https://openinfra.dev/community/ returned 404. A free project-listing form was not found.

### Official MCP Registry (`mcp-registry`)

Status: BLUE.

Evidence: Registry API on 2026-10-09: name io.github.Guruprasath-Annadurai/whitepact, isLatest true, version 1.2.3, package rai-governance-platform 1.2.2, status active, updated 2026-08-12.

Owner action: Publish the corrected server.json with mcp-publisher after review. Do not publish from this lane.

Change in this branch: server.json package pin moved from 1.2.2 to the verified PyPI release 1.2.6. Remote copy no longer promises an unverified free signup.

Remaining blocker: The corrected manifest is not published. The live registry latest remains listing 1.2.3 / package 1.2.2.

### Glama (`glama`)

Status: BLUE.

Evidence: Page fetched 2026-10-09, title WhitePact by Guruprasath-Annadurai | Glama, HTTP 200.

Owner action: Update the existing server after the registry correction. Do not create a second listing.

Change in this branch: Correction notes are in ALREADY_LIVE_DIRECTORY_AUDIT.md.

Remaining blocker: Glama content still mirrors older README claims, including mixed 27-tool and 30-tool wording.

### Smithery (`smithery`)

Status: BLUE.

Evidence: Fetched 2026-10-09. Title: whitepact - MCP | Smithery. Visible text: Published Aug 12, 2026, No description.

Owner action: Refresh the existing server. The public page currently says No description.

Change in this branch: Correction notes only. No second listing.

Remaining blocker: Smithery’s page has an empty description and a 42/100 score. README links still use the older /server/ path, which redirects.

### MCP Market (`mcp-market`)

Status: BLUE.

Evidence: Fetched 2026-10-09. Title: Whitepact: AI Governance, Trust, & Compliance Platform. Body names Guruprasath-Annadurai.

Owner action: Claim the existing listing. Do not submit a duplicate.

Change in this branch: Correction notes only.

Remaining blocker: The page says Claim this listing. Pricing for a claim was not stated on the fetched page.

### MCPBeat (`mcpbeat`)

Status: GREY.

Evidence: A web index returned a page titled WhitePact MCP Server Status that claimed 27 tools. That claim was not re-fetched from the origin.

Owner action: Open the URL in a browser and correct the listing only if it is the same server.

Change in this branch: None applied to a live listing.

Remaining blocker: This audit host received HTTP 403, so the page body was not verified here.

### AlternativeTo (`alternativeto`)

Status: GREY.

Evidence: Direct fetches of the software URL and the search URL returned 403 on 2026-10-09.

Owner action: Search AlternativeTo while logged in before suggesting the software.

Change in this branch: None.

Remaining blocker: HTTP 403 from this host. No listing was verified, so none should be created blindly.

### OpenSSF Best Practices (`openssf-best-practices`)

Status: BLUE.

Evidence: https://www.bestpractices.dev/projects/14112.json on 2026-10-09: id 14112, name WhitePact, badge_level silver, badge_percentage_0 100, updated_at 2026-08-29.

Owner action: Keep the badge answers current when release facts change. Do not call the badge a certification.

Change in this branch: No badge form was edited.

Remaining blocker: Gold was not the reported level.

### PyPI (`pypi`)

Status: BLUE.

Evidence: PyPI JSON on 2026-10-09: latest 1.2.6. Releases present: 0.6.0 through 1.2.3 and 1.2.6. No 1.2.4, 1.2.5, or 1.3.1. The whitepact project name returned 404.

Owner action: Do not publish 1.3.1 from this lane. A later release can refresh the summary and classifier.

Change in this branch: Source classifier is handled in a separate metadata commit. The live 1.2.6 files were not replaced.

Remaining blocker: Live 1.2.6 still says Development Status :: 5 - Production/Stable and its whitepact script is biasbuster.cli:main.

### CNCF Landscape (`cncf-landscape`)

Status: RED.

Evidence: README fetched from github.com/cncf/landscape on 2026-10-09. GitHub API stargazers_count was 2.

Owner action: Do not open an upstream pull request until the star guideline and a real SVG logo are satisfied.

Change in this branch: A draft YAML entry and a text SVG stand-in are in docs/ecosystem/cncf/. They are not a submission.

Remaining blocker: The landscape README says cloud-native projects are generally included at 300 GitHub stars. This repository had 2 stars. The repo has no SVG logo.

### Hugging Face static Spaces (`huggingface-spaces`)

Status: YELLOW.

Evidence: Spaces overview returned 200. https://huggingface.co/new-space redirected to login, which shows an account is required.

Owner action: Create a free Space with SDK static and upload docs/ecosystem/huggingface-space/. Do not select paid hardware.

Change in this branch: Static educational files were added. Nothing was deployed.

Remaining blocker: A Hugging Face account upload is still required. The page does not run the engine.

### Docker Hub (`docker-hub`)

Status: RED.

Evidence: https://hub.docker.com/v2/search/repositories/?query=whitepact returned count 0 on 2026-10-09. Source Dockerfile exists and labels version 1.3.1.

Owner action: Authorize a later image publish before any Hub listing. This lane must not push an image.

Change in this branch: None to the Dockerfile.

Remaining blocker: Docker Hub search for whitepact returned count 0. A listing without an image is not eligible.

### LangChain (`langchain`)

Status: YELLOW.

Evidence: TrustGateMiddleware.wrap_tool_call exists and is covered by tests/test_langchain_middleware.py.

Owner action: Do not submit a partner listing until a current free directory form is confirmed.

Change in this branch: Entrypoint documented in examples/ecosystem/README.md. No adapter behavior was changed.

Remaining blocker: No official free LangChain integration directory form was verified.

### LangGraph (`langgraph`)

Status: YELLOW.

Evidence: make_trust_gate_node exists and is covered by tests/test_langgraph_gate.py.

Owner action: Same as LangChain. Use the in-repo gate, not a new listing.

Change in this branch: Entrypoint documented. No behavior change.

Remaining blocker: No separate free LangGraph directory form was verified.

### LlamaIndex (`llamaindex`)

Status: RED.

Evidence: Repository search for llamaindex and llama_index under src returned no matches.

Owner action: Do not list a LlamaIndex integration.

Change in this branch: None. A blocker was recorded instead of a new adapter.

Remaining blocker: No LlamaIndex import, extra, or example exists in this commit.

### CrewAI (`crewai`)

Status: RED.

Evidence: Repository search for crewai under src returned no matches.

Owner action: Do not list a CrewAI integration.

Change in this branch: None.

Remaining blocker: No CrewAI adapter exists in this commit.

### AutoGen and successor ecosystem (`autogen`)

Status: RED.

Evidence: Repository search for autogen under src returned no matches.

Owner action: Do not list an AutoGen or AG2 integration.

Change in this branch: None.

Remaining blocker: No AutoGen or AG2 adapter exists in this commit.

### PulseMCP (`pulsemcp`)

Status: GREY.

Evidence: Homepage returned 200 on 2026-10-09 and contains the word submit. Listing status was not confirmed.

Owner action: Search PulseMCP for an existing WhitePact server before any submission.

Change in this branch: None.

Remaining blocker: A WhitePact listing and a free submit rule were not verified.

### Product Hunt (`product-hunt`)

Status: GREY.

Evidence: https://www.producthunt.com/ and /posts/new returned 403 on 2026-10-09.

Owner action: Read the current launch form in a browser before scheduling a launch.

Change in this branch: Copy is ready if the form’s current rules match a free maker launch.

Remaining blocker: The launch URL returned HTTP 403 to this audit host, so the free route and asset rules were not read from the official page.

### Peerlist Launchpad (`peerlist-launchpad`)

Status: GREY.

Evidence: https://peerlist.io/launchpad returned 200 with an empty title on 2026-10-09.

Owner action: Open the launchpad while signed in and record whether launch week is free.

Change in this branch: Copy is ready. Eligibility is not.

Remaining blocker: The page returned 200 but did not expose pricing text to this fetch.

### Uneed (`uneed`)

Status: GREY.

Evidence: Homepage returned 200, title Daily Product Launches: Discover the Best New Tools | Uneed.

Owner action: Find the current submit control on the live site before listing.

Change in this branch: Copy is ready.

Remaining blocker: https://www.uneed.best/submit and https://uneed.best/submit returned 404. A free route was not verified.

### Startup Stash (`startup-stash`)

Status: GREY.

Evidence: Homepage returned 200 on 2026-10-09.

Owner action: Locate the current add-listing control. Do not pay for inclusion from this budget.

Change in this branch: None.

Remaining blocker: Guessed submit URLs returned 404. Pricing was not verified.

### AI Tools Directory (`ai-tools-directory`)

Status: GREY.

Evidence: https://aitoolsdirectory.com/submit-tool returned 200. The word free on that page described the product’s language, not a confirmed zero listing fee.

Owner action: Read the full form, including any fee step, before submitting.

Change in this branch: Copy is ready if the form stays free and accepts a developer security tool.

Remaining blocker: The fetched page addresses end-user products. A listing fee was not confirmed.

### The Next AI (`the-next-ai`)

Status: GREY.

Evidence: Homepage returned 200, title The Next AI — Curated AI Tools Directory for Developers | Creators.

Owner action: Find the current submission control on the site.

Change in this branch: None.

Remaining blocker: https://www.thenextai.com/submit returned 404.

### AI SuperHub (`ai-superhub`)

Status: GREY.

Evidence: https://aisuperhub.com/ and /submit returned 200 on 2026-10-09.

Owner action: Open the submit page in a browser and record the fee before using it.

Change in this branch: None.

Remaining blocker: The URL returned 200 but no pricing text was extracted.

### HyzenPro (`hyzenpro`)

Status: GREY.

Evidence: Homepage returned 200, title Simplifying AI for Everyone | HyzenPro.

Owner action: Find a submission page on the live site.

Change in this branch: None.

Remaining blocker: https://hyzenpro.com/submit returned 404.

### CodeHype (`codehype`)

Status: GREY.

Evidence: DNS lookup failed for both hostnames from this host.

Owner action: Do not submit until a resolving official URL is confirmed.

Change in this branch: None.

Remaining blocker: codehype.com and codehype.co did not resolve on 2026-10-09.

### Launching Next (`launching-next`)

Status: GREY.

Evidence: Homepage returned 200, title Launching Next | New startups, startup ideas, great business ideas.

Owner action: Find the current startup submission control and its fee.

Change in this branch: None.

Remaining blocker: /submit and /add-startup returned 404.

### Startup Buffer (`startup-buffer`)

Status: GREY.

Evidence: Both URLs returned 403 on 2026-10-09.

Owner action: Retry from a browser. This host was forbidden.

Change in this branch: None.

Remaining blocker: Homepage and /submit returned HTTP 403.

### MicroSaaS Directory (`microsaas-directory`)

Status: GREY.

Evidence: https://microsaas.directory/ returned 200, title MicroSaaS Directory - Discover Independent Products. www.microsaas.directory was not the working host.

Owner action: Confirm the directory still accepts open-source developer tools and whether a public product URL is mandatory.

Change in this branch: None.

Remaining blocker: /submit returned 404. A free route was not verified. The hosted enterprise SaaS is not globally authorized.

### SaaS Hunt (`saas-hunt`)

Status: GREY.

Evidence: Homepage returned 200 on 2026-10-09.

Owner action: Confirm the live submit form and fee. Do not present the enterprise SaaS as launched.

Change in this branch: None.

Remaining blocker: /submit returned 404. SaaS-listing rules were not verified.

### Saaspa.ge (`saaspa-ge`)

Status: GREY.

Evidence: Homepage returned 200, title Saaspa.ge - Launch Your Product This Week. Submit redirected to /auth/signin.

Owner action: Sign-in is required to reach submit. Confirm the fee after login and do not pay.

Change in this branch: None.

Remaining blocker: https://saaspa.ge/submit redirected to an auth sign-in URL. The fee after login was not visible.

### Sidehunt (`sidehunt`)

Status: GREY.

Evidence: https://sidehunt.io/ returned 200. https://sidehunt.io/submit title was Submit your side project | Sidehunt.

Owner action: Read the submit page’s fee terms in a browser before posting.

Change in this branch: Copy is ready if the form is free.

Remaining blocker: The submit page returned 200 but the fetched text did not state that submission is free.

### Firsto (`firsto`)

Status: GREY.

Evidence: Homepage returned 200, title Firsto – Fair Product Launch Platform Where Every Launch Gets Seen.

Owner action: Find the current launch form on the site.

Change in this branch: None.

Remaining blocker: https://firsto.co/submit returned 404.

### AWS Marketplace (`aws-marketplace`)

Status: RED.

Evidence: AWS partner/marketplace pages describe a seller program. No WhitePact product page was found, and this lane forbids cloud changes.

Owner action: Do not start seller registration in this lane.

Change in this branch: None.

Remaining blocker: A marketplace listing needs a seller account, a packaged product, and operational readiness this release has not authorized. No listing was verified.

### GitHub Marketplace (`github-marketplace`)

Status: RED.

Evidence: https://docs.github.com/en/apps/github-marketplace/github-marketplace-overview/about-github-marketplace returned 404 on 2026-10-09.

Owner action: Do not create a Marketplace draft.

Change in this branch: None.

Remaining blocker: Marketplace listing requires a GitHub App and publisher review. This repository has no such app listing. The previously documented docs URL returned 404.

### Cloud Security Alliance STAR (`csa-star`)

Status: RED.

Evidence: https://cloudsecurityalliance.org/star returned 200. No public WhitePact STAR registry entry was verified.

Owner action: Do not file a STAR entry or invent questionnaire evidence.

Change in this branch: None.

Remaining blocker: STAR publication requires an organizational assessment. This lane must not create compliance evidence.

### Linux Foundation project hosting (`linux-foundation`)

Status: RED.

Evidence: https://www.linuxfoundation.org/projects returned 200. WhitePact is not a Linux Foundation project.

Owner action: Do not apply for foundation hosting.

Change in this branch: None.

Remaining blocker: Project hosting is an organizational acceptance process, not a free directory form.

### OpenSSF formal membership (`openssf-membership`)

Status: RED.

Evidence: https://openssf.org/join/ returned 200, title Join OpenSSF | Open Source Security Foundation Membership.

Owner action: Do not start a membership application. The free Best Practices badge is a separate, already-live item.

Change in this branch: None.

Remaining blocker: Join OpenSSF is an organizational membership, distinct from the Best Practices badge.
