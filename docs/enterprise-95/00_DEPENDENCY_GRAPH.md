# WhitePact 95+ — Dependency Graph

The directive's proposed shape is directionally right but assumes work
(Brain/Device/BCI, Network Fabric) that does not exist and has no
current requirement to exist (see `00_REALITY_BASELINE.md` items 4, 24,
25). Reordered below to reflect actual repository evidence — that work
is moved out of the mainline sequence into a clearly-marked deferred
branch rather than deleted, in case a real requirement appears later.

```
Independent human security review (SHA-confirmed, on the frozen
candidate)
        ↓
Clean integration onto main (see 00_INTEGRATION_STRATEGY.md;
reconciles main's SLSA/Scorecard/evidence-bundle work with PR #55's
Heart/governance work — neither should be silently lost)
        ↓
Process isolation (Stage 10 architecture decision, THEN implementation
— not before)
        ↓
Live purpose binding across every ingress path
        ↓
Credential / API-key lifecycle (rotation, expiry)
        ↓
Tenant + RBAC gauntlet (exhaustive endpoint-by-endpoint)
        ↓
Evidence / replay / revocation closure (fork-resistance attack test,
concurrent-consume race testing, revocation_epoch binding at grant time)
        ↓
Production runtime verification (Docker + Helm, against a real daemon/
cluster this project doesn't currently have access to — external
dependency, see below)
        ↓
Enterprise IAM completion (SCIM — OIDC/SAML already exist)
        ↓
Observability / SRE / DR (live-fire alert verification, repeatable DR
program — DR mechanism itself already proven once)
        ↓
Trust Center (docs/trust/ASSURANCE_MATRIX.json) + Dashboard/commercial
control-plane polish
        ↓
Real-world pilots
        ↓
Further external assurance (a second, SHA-confirmed, scope-documented
security review; eventually a formal audit/pentest when there's budget)
        ↓
95+ final evidence score
```

**Deferred branch (not on the critical path, no current requirement):**
Network Fabric, Device/Edge architecture, Brain/AI/BCI integration.
Nothing currently depends on these; inventing them now would be
building ahead of any real requirement, which the audit was explicitly
told not to do.

## Why this order

- **Security review first, always.** Every later step either produces
  more surface area to review (integration, process isolation) or
  assumes review passed. Reviewing after integration means reviewing a
  moving target.
- **Integration before process isolation.** Process isolation is a
  structural rewrite of the execution boundary — doing it once, on the
  post-integration codebase, avoids doing the rewrite twice (once on
  PR #55 alone, again after merging `main`'s independent changes).
- **Credential lifecycle and RBAC gauntlet before production
  verification.** No point running a Docker/Helm live-fire drill against
  an auth/authz layer that's still being hardened.
- **IAM/observability/DR before Trust Center.** The Trust Center is a
  claims artifact — it should describe what's actually true, not be
  built ahead of the evidence it's supposed to summarize.
- **Pilots and further external assurance are downstream of everything
  else**, not a substitute for any of it.
