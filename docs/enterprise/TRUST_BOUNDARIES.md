# Trust Boundary Diagram

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phases 32/33. `00_MASTER_READINESS_AUDIT.md`
named this as low-priority — "the properties are already true in code,
just not diagrammed."

**Found already substantially true, not just in code but in
documentation too**: `SECURITY_ASSURANCE_CASE.md` §3 ("Trust
Boundaries") already contains a real, thorough ASCII diagram of the
primary request path plus a table of every secondary boundary
(Postgres, Redis, OIDC provider, LLM provider, webhook targets,
upstream MCP servers, CI/CD, secrets manager) — that document remains
the authoritative source, cross-referencing each boundary to the exact
code enforcing it. This page adds a rendered diagram for readers who
want the visual form, and does not restate the authoritative prose —
see [`SECURITY_ASSURANCE_CASE.md` §3](../../SECURITY_ASSURANCE_CASE.md#3-trust-boundaries)
for the full boundary-by-boundary validation detail.

## Primary request path

```mermaid
flowchart TD
    U["User / Agent"]:::untrusted
    I["Internet"]:::untrusted
    TLS["TLS termination / reverse proxy<br/>(deployer-configured)"]:::conditional
    API["WhitePact API / MCP transport<br/>(Pydantic validation, security headers,<br/>DNS-rebinding protection)"]:::boundary
    AUTH["Authentication<br/>(Bearer token / OIDC / SAML)"]:::boundary
    RBAC["RBAC / tenant isolation<br/>(require_role, org_id scoping —<br/>see Phase 7's IDOR fix)"]:::boundary
    GOV["Machine Authority / Governance Runtime<br/>(WhitePactRuntimeGateway — deterministic,<br/>DB-free evaluation)"]:::trusted
    POL["Policy / Risk / Workflow / Approval<br/>(deterministic, internal)"]:::trusted
    PERM["Execution Permit / execution control<br/>(ExecutionAuthorization: digest + org +<br/>expiry + single-use, Phase 3/4)"]:::boundary
    EXT["MCP / API / external target<br/>(InternalToolExecutor, or upstream<br/>MCP proxy — SSRF-guarded)"]:::untrusted

    U --> I --> TLS --> API --> AUTH --> RBAC --> GOV --> POL --> PERM --> EXT

    classDef untrusted fill:#f8d7da,stroke:#c0392b,color:#611a15
    classDef conditional fill:#fff3cd,stroke:#b7891a,color:#5c4404
    classDef boundary fill:#d1ecf1,stroke:#0c7793,color:#063542,font-weight:bold
    classDef trusted fill:#d4edda,stroke:#2e7d4f,color:#1a4529
```

## Secondary boundaries (not on the primary request path)

```mermaid
flowchart LR
    WP["WhitePact"]:::trusted

    PG[("PostgreSQL")]:::trusted
    RD[("Redis")]:::conditional
    OIDC["OIDC Provider"]:::conditional
    LLM["LLM Provider"]:::untrusted
    WH["Webhook target"]:::untrusted
    UMCP["Upstream MCP server"]:::untrusted
    GH["GitHub CI"]:::trusted
    PYPI["PyPI"]:::trusted
    SEC["Secrets manager"]:::trusted

    WP -->|"parameterized queries only"| PG
    WP -->|"rate-limit counters only,<br/>never PII/credentials"| RD
    WP -->|"JWKS validated; claims trusted<br/>once signature-verified"| OIDC
    WP -->|"opt-in, customer-configured;<br/>not audited past send"| LLM
    WP -->|"SSRF-validated at registration<br/>AND every delivery"| WH
    WP -->|"registry + SSRF-guarded proxy;<br/>result content not verified"| UMCP
    GH -->|"branch-protected, required<br/>status checks"| WP
    GH -->|"OIDC Trusted Publishing,<br/>no static token"| PYPI
    SEC -->|"deployer-managed; never<br/>logged or echoed"| WP

    classDef untrusted fill:#f8d7da,stroke:#c0392b,color:#611a15
    classDef conditional fill:#fff3cd,stroke:#b7891a,color:#5c4404
    classDef trusted fill:#d4edda,stroke:#2e7d4f,color:#1a4529
```

## Legend

- **Red (untrusted)**: no assumption of good behavior; every input
  from this side is validated (SSRF checks, request schema validation)
  or explicitly out of this platform's control (an LLM provider's own
  handling of a sent request).
- **Yellow (conditionally trusted)**: trusted for a specific, narrow
  purpose only — Redis holds rate-limit counters, never governance
  data; an OIDC provider is trusted for token signing, not for
  arbitrary claim content beyond what's cryptographically verified.
- **Blue (boundary — validates and forwards)**: where this platform's
  own code actively checks something before letting a request proceed
  further in. Every one of the four blue nodes on the primary path
  corresponds to a specific closure-phase's own work this session:
  authentication (Phase 6's `AuthFailureLimiter`), RBAC/tenant
  isolation (Phase 7's cross-org IDOR fix), the execution permit
  (Phases 3/4's structural binding + replay protection).
- **Green (trusted, internal)**: deterministic, DB-free, no external
  input crosses in at this layer — `DETERMINISTIC_VS_PROBABILISTIC.md`
  is the fuller argument for why this is a meaningful trust
  distinction, not just an internal/external label.
