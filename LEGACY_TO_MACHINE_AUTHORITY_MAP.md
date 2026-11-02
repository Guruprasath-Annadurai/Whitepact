# Legacy Authorization → Machine Authority Map

Last reviewed: 2026-08-17 · Platform version: 1.2.0

For a reader arriving from traditional access control (RBAC, OAuth, IAM,
API gateways) rather than from `MACHINE_AUTHORITY_PROBLEM.md`'s framing:
this document maps each familiar concept onto its closest WhitePact
equivalent, and states plainly what's actually different, not just
renamed. Where a row says "no equivalent," that's an honest gap, not an
oversight — see `ENFORCEMENT_BOUNDARY.md` for what's in scope at all.

| Legacy concept | Closest WhitePact primitive | What's actually different |
|---|---|---|
| Static API key / bearer token | `IdentityContext` + per-call `AuthorityContext` | A legacy key is a fixed bag of permissions checked once at request time. `AuthorityContext` is constructed fresh per call (`mcp/governance_integration.py`) from the org's live ceiling/policy/delegation state — the same key can be authorized differently on two calls a minute apart if the org's configuration changed in between. |
| RBAC role (`ADMIN`, `ANALYST`, ...) | `Role` (`rbac/models.py`) *plus* `AuthorityContext.granted_action_types` | RBAC roles still gate the REST configuration API (who can set a ceiling, grant a delegation). They do **not** gate individual governed tool calls — that's `AuthorityContext`, a finer-grained, per-call grant, not a per-session role. |
| OAuth scope (`payments:write`) | `AuthorityContext.granted_action_types` + `constraints` | A scope is typically boolean (you have it or you don't). A WhitePact grant carries *quantitative* constraints alongside the boolean (`max_value_usd`, `allowed_targets`, `allowed_hours_utc`) — narrower than "can write payments," closer to "can write payments up to $X, to these targets, during these hours." |
| IAM policy document (allow/deny statements) | `Policy` / `PolicyRule` (`governance/policy.py`) | Same first-match-wins rule-evaluation shape. Difference: a WhitePact `Policy` match is one step in a larger deterministic pipeline (quarantine → workflow → attenuation → authority → risk → constraints → policy → content scan → trust) — a policy `ALLOW` does not skip the PII/toxicity scan or the trust check that come after it, by design (defense in depth), unlike many IAM engines where a matching allow statement is the final word. |
| Assumed-role chains (`sts:AssumeRole`, role A assumes role B) | Delegation Graph (`db/delegation_repository.py`) | The closest structural analogue — a chain of grants, each pointing at its parent. The real difference: AWS's `AssumeRole` does not, by default, verify that the assumed role's *policy* is narrower than the assuming role's — that's opt-in, separate tooling (permission boundaries, SCPs). WhitePact's attenuation check is **mandatory and automatic** at grant time (`DelegationEscalationError` on any widening), not an optional guardrail an admin has to remember to configure. |
| Rate limiting (requests/sec, quota) | Autonomy Budget (`governance/autonomy_budget.py`) | A rate limit caps *volume regardless of content*. An Autonomy Budget caps volume specifically of *unsupervised* decisions (`ALLOW`/`ALLOW_WITH_REDACTION`) — a call that required human approval doesn't count against it, since a human already looked. The two are complementary, not substitutes: nothing here replaces a network-layer rate limiter (`slowapi`, already used elsewhere in this codebase for that purpose). |
| Circuit breaker (trip after N failures) | Quarantine (`governance/quarantine.py`) | Structurally similar (a rolling-window count triggers a state change). Different trigger: a circuit breaker trips on *failed calls to a downstream dependency*; quarantine trips on a pattern of *denied* actions from one identity — it's about the caller's behavior, not a dependency's health. |
| Web Application Firewall / content filter | Memory Firewall (`governance/memory_firewall.py`) + `GuardrailsEngine` | A WAF inspects traffic at the network/HTTP layer, pattern-agnostic to what the content is *for*. The Memory Firewall is narrower and purpose-built: it scans specifically for patterns that try to inject a persistent instruction into content destined for an agent's own memory — not a general content filter (that role is `GuardrailsEngine`'s PII/toxicity scan, which already runs on every action's arguments regardless of memory involvement). |
| mTLS / service mesh identity (SPIFFE, etc.) | A2A Trust Gate (`integrations/a2a_adapter.py`) | mTLS answers "is this the service it claims to be" — cryptographic identity. `A2ATrustGate` answers a different question: "given that I know which agent this is, should I trust what it's telling me and send it this message" — a trust/reputation judgment (Trust Index score) plus a content check (memory-firewall scan of the outbound message), not an identity/transport-security primitive. The two are complementary; WhitePact does not replace mTLS. |
| Audit log / SIEM event stream | Evidence chain + Evidence Bundle (`governance_evidence` table, `governance/evidence_bundle.py`) | A SIEM event stream is typically append-only but not cryptographically chained, and consumed live. WhitePact's evidence is hash-chained per-org (tamper-evident) and exportable as a self-contained, **offline**-verifiable bundle — verifiable by a party with no ongoing access to the live system at all, which a typical SIEM export is not. |
| Approval workflow (change-management ticket, human-in-the-loop gate) | `REQUIRE_APPROVAL` decision + `ApprovalRepository` | Structurally similar. WhitePact's approval binding is execution-gated, not just advisory: `ExecutionAuthorization`/`InternalToolExecutor` structurally cannot run an action without a matching, unexpired, single-use authorization — an approved-but-stale or already-consumed approval cannot be replayed (`db/approval_repository.py`'s mutation/replay/self-approval protections). |

## What has no WhitePact equivalent at all (honest gaps)

- **Federated identity / SSO integration for the *agents themselves*** —
  Identity Bridge adapters (Entra ID, AWS IAM, Google Workspace, Okta) for
  mapping an enterprise's existing identity provider onto WhitePact
  identities are a named, not-yet-built item — see the project's own
  remaining-work tracking, not this document, for status.
- **Cross-identity aggregation** — Autonomy Budget and the Workflow
  Authority Engine both key off a single `(org_id, agent_id)`; there is no
  primitive here for "cap the combined unsupervised volume of these five
  cooperating agent identities together."
- **A general-purpose policy DSL** (Rego/OPA-equivalent) — `Policy`'s rule
  matching is deliberately a fixed, small rule shape, not an expression
  language; see `governance/models.py`'s own docstring for why that's a
  stated non-goal, not an oversight.
