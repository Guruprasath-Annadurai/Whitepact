# Enterprise evaluation kit

Everything here is evidence a reviewer can re-run. Status of each claim is in `docs/launch/` and `docs/assurance/`.

## The fifteen questions, answered plainly

1. **What does WhitePact protect?** Tool calls that are routed through a supported, configured enforcement path: hosted MCP, REST governed calls, approval resume, upstream proxy.
2. **What is outside the boundary?** Actions that do not pass through those paths: an agent calling an API directly; local stdio MCP (advisory); SDK decision calls on code that ignores them. `docs/launch/ENFORCEMENT_PATH_MATRIX.md`.
3. **Authentication of humans and machines?** API keys, OIDC/SAML/SCIM, web sessions with CSRF; TOTP step-up for privileged actions (OIDC and WebAuthn step-up are not supported).
4. **Privilege escalation?** Delegation can only narrow authority (attenuation checks), revocation cascades to descendants, policy edits are attributed and (optionally) two-person controlled.
5. **An agent that ignores a policy?** It is not stopped unless its action goes through WhitePact; the decision and the execution happen on the server.
6. **Independent of a model provider?** Decisions use identity, authority and policy, not model output; tested with injection corpora.
7. **Customer-hosted?** Docker/Helm/Terraform material exists; no deployment was applied or qualified.
8. **Can the customer inspect evidence?** Hash-chained records, export, restore drill; no external anchor yet.
9. **Revocation?** Stops new admissions and resumes; does not cancel a running tool.
10. **If the service is down?** The protected path fails closed (tests); the local stdio server is unaffected because it enforces nothing.
11. **IAM and logging integration?** OIDC/SAML/SCIM, webhooks, Prometheus/OTel; no real-IdP interoperability test yet.
12. **Operational cost?** PostgreSQL, optional Redis, Docker on Linux for isolation; one worker handled ~80–170 req/s in the single same-host test.
13. **Security testing done?** Unit/integration/adversarial tests, CodeQL, Bandit, dependency scanning, AI-agent audits. **No human penetration test.**
14. **Independent reviewers?** Antigravity (an AI agent) only.
15. **Unproven?** See `docs/launch/ENTERPRISE_RECOVERY_ISSUE_REGISTER.md`, the NOT TESTED lists, and the gap analyses.

## Run the proof yourself

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact && cd Whitepact
uv sync --extra dev --extra dashboard --extra mcp
scripts/test-postgres.sh up && eval "$(scripts/test-postgres.sh env)"
python scripts/authority_challenge.py --out authority-challenge.json    # 12 scenarios; skips are BLOCKED, not PASS
scripts/verify-linux-container-isolation.sh nonroot                      # real Linux container tests (needs Docker)
python scripts/bench_http_authorization.py --levels 1,10,100 --out bench.json
```

Verify a release without trusting the project: `docs/VERIFY_RELEASE.md`.
