# WhitePact 1.2.4rc1 Enterprise Gate Register

Last reviewed: 2026-08-27

This register distinguishes controls that can be completed in the repository
from gates that require deployed infrastructure, third parties, legal counsel,
or provider accounts. `1.2.4rc1` is an enterprise **release candidate**, not an
external certification claim.

## Repository-controlled controls

| Control | Candidate state |
|---|---|
| Production topology | Dashboard, MCP service, migrations, PostgreSQL, Redis, readiness/liveness, Compose, Helm, and Render Blueprint are defined |
| Runtime authorization | Heart root/consent/intent/purpose/passport resolution and approval reauthorization are wired fail-closed |
| OAuth resource server | RFC 9728 metadata, authorization-server validation, audience/issuer/expiry/scope/tenant checks, and distributed auth throttling implemented |
| Tenant isolation | Repository-scoped Heart, intent, passport, delegation, policy, evidence, and organization access; unknown tenants rejected |
| MCP schemas | Inputs validate as JSON Schema; every tool advertises structured object output and accurate side-effect annotations |
| Supply chain | Immutable action SHAs, dependency review, Dependabot, SAST, secret scan, SBOM, trusted publishing, provenance attestation, signed-tag gate |
| Release integrity | Tag/package version equality gate, versioned container/chart, wheel/sdist verification, changelog/release artifact workflow |
| Provider portability | Streamable HTTP/SSE, OAuth and static bearer paths, provider matrix, and tested Gemini bridge |

## External gates — must not be represented as complete

| Gate | Owner/action | Evidence required to close |
|---|---|---|
| Production deployment | Operator deploys `1.2.4rc1` with PostgreSQL, Redis, TLS, backups, monitoring, and secrets manager. The previously listed Render MCP endpoint timed out on 2026-08-27 and is not treated as live. | Deployment revision, readiness output, migration log, restore test, monitoring screenshots/logs |
| Authorization server | Identity team configures OAuth clients/metadata, exact resource indicators, S256 PKCE, tenant claims, scopes, and key rotation | Discovery documents, redacted client config, successful/negative token tests |
| Independent penetration test | Contract an independent qualified assessor after deployment freeze | Final report, remediation evidence, retest letter |
| SOC 2 / ISO 27001 | Establish organization controls and complete audit if buyer requires certification | Auditor-issued report/certificate; repository self-assessments do not qualify |
| Legal documents | Licensed counsel completes Terms, DPA, privacy, liability, governing law, SCC/data-transfer, and subprocessor terms | Signed counsel-approved versions and entity details |
| Cyber insurance | Operator selects coverage appropriate to hosted enterprise contracts | Active policy and limits recorded outside the repository |
| Release signer | Approved maintainer public SSH signing key remains in `security/release-signers.allowed`; tag is signed | `git tag -v v1.2.4rc1` and passing release workflow |
| PyPI/registry release | Maintainer approves protected `pypi` environment and publishes the signed candidate | PyPI URL, GitHub release, SBOM, successful provenance verification |
| Provider acceptance | Run the live test in `docs/integrations/PLATFORM_COMPATIBILITY.md` separately for every provider | Dated provider-specific evidence; account/UI approval where applicable |
| OpenAI/Claude onboarding | Complete first because their OAuth/tool surfaces are the primary candidate targets | Successful governed call and negative authorization cases on both |
| Microsoft/xAI/AWS/Mistral onboarding | Complete after OpenAI and Claude pass | Separate compatibility record for each provider |
| Gemini native MCP | Continue bridge for Gemini model paths that still lack native remote MCP | Google documentation change plus direct live compatibility test |
| Managed Codex Security scan | Run when the host provides the required managed filesystem permission profile | Completed scan manifest, findings, coverage, remediation/retest evidence |

## Release decision

The repository can produce a candidate artifact when all automated checks pass.
Production enterprise onboarding is blocked until, at minimum, deployment,
authorization-server configuration, independent penetration testing, legal
review, signed publication, and the relevant provider live test are complete.
