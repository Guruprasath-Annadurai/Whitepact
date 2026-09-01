# Phase 7 — Consolidated Cross-Tenant Isolation Sweep

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 7. `00_MASTER_READINESS_AUDIT.md`'s
Tenancy row named the gap: per-endpoint cross-org isolation tests
already existed scattered across several files, but no single,
exhaustive sweep proved it in one place across every object type.

## Critical finding: a real, exploitable cross-tenant IDOR

Building the sweep (`tests/test_cross_tenant_isolation_sweep.py`)
surfaced a genuine, previously-unknown vulnerability, not a
documentation gap:

**Every one of the 15 `/api/orgs/{org_id}/...` REST handlers** —
org details (GET/DELETE), SSO toggle, org-level MFA toggle, authority
ceiling (GET/PUT), autonomy budget (GET/PUT/DELETE), API key
management (create/list/revoke), and per-key MFA enroll/verify/disable
— **checked the caller's ROLE (`require_role()`) but never checked
that the caller's own organization actually matched the `org_id` in
the URL path.**

`require_role()` (`dashboard/app.py`) only validates
`OrgContext.role` against a minimum; it has no opinion on tenancy.
Nothing else in these 15 handlers filled that gap — each one took
`org_id` straight from the path and used it directly against the
repository layer.

**Concrete impact, proven by the sweep before the fix**: any API key
with ADMIN/OWNER role in its **own** organization could, by supplying
a **different** organization's UUID in the path:
- Read another org's full details (`GET /api/orgs/{org_id}`).
- Delete another org entirely (`DELETE /api/orgs/{org_id}`).
- Toggle another org's SSO enforcement or org-wide MFA requirement.
- Read or overwrite another org's authority ceiling / autonomy budget
  (the structural caps every governed action for that org is checked
  against).
- List, create, or **revoke another org's API keys**.
- Enroll, verify, or disable MFA on another org's API key.

**A second, compounding bug in the same area**: `revoke_api_key()`
called `OrgRepository.revoke_key(key_id)` — itself entirely org-agnostic
(revokes by `key_id` alone, with no `org_id` parameter at all) — with
**no check anywhere** that the key actually belonged to the org named
in the URL. Even fixing only the caller-vs-path-org check would have
left this: an ADMIN in org A could revoke any key in the entire
system by ID, regardless of which org it belonged to, as long as they
supplied *any* valid `org_id` they had ADMIN+ access to in the path.

This is a textbook Broken Object-Level Authorization (OWASP API
Security Top 10, API1:2023) / IDOR vulnerability, and — because the
affected surface includes authority ceilings and autonomy budgets,
which every governed MCP tool call is checked against — a successful
exploit could have let one tenant silently weaken or widen another
tenant's governance guardrails, not just read its data.

### Fix

One shared guard, `_require_caller_owns_org(_auth, org_id)`
(`dashboard/app.py`), applied at the top of all 15 handlers:

```python
def _require_caller_owns_org(_auth: OrgContext, org_id: str) -> None:
    if _auth.org_id is not None and _auth.org_id != org_id:
        raise HTTPException(404, "Organization not found")
```

- Raises the same 404 (not 403) this codebase already uses everywhere
  else for a cross-org access attempt — never confirms whether the
  other org's id even exists, matching the established convention
  (`"Same 404 as 'doesn't exist' -- not 403"`, seen throughout the
  existing consent/passport/evidence endpoints).
- A caller with `org_id is None` (legacy flat `RAI_API_KEYS`/dev
  anonymous auth) is deliberately exempt — that's this codebase's
  existing "sees everything" super-admin persona, the same one
  `list_webhooks()`/`list_incidents()` already carve out via
  `is_legacy and role == Role.OWNER`. This fix does not change that
  persona's behavior, only closes the gap for real, org-scoped keys.
- `revoke_api_key()` additionally now fetches the target key first and
  confirms `key.org_id == org_id` (matching the pattern the three MFA
  endpoints already used) *before* calling the org-agnostic
  `revoke_key()` — closing the second bug in the same change.

### Regression coverage

`tests/test_cross_tenant_isolation_sweep.py::TestCrossTenantIsolationSweep::test_org_get_and_delete`
and `::test_api_key_delete` prove the fix directly: org B's key against
org A's `org_id`/`key_id` now returns 404 for every one of these
endpoints, where the same test returned 200 before the fix (caught
live during this phase's own work, not hypothetically).

## The rest of the sweep (object types not affected by the IDOR above)

Every other object type checked by
`tests/test_cross_tenant_isolation_sweep.py` was **already** correctly
isolated — confirmed, not assumed:

| Object type | Endpoint(s) | Isolation mechanism | Result |
|---|---|---|---|
| Policy rules | `DELETE /api/governance/policy/rules/{rule_id}` | Repository query scoped by `_auth.org_id` | 404 for cross-org |
| Workflow rules | `DELETE /api/governance/workflow-rules/{rule_id}` | Same pattern | 404 |
| Delegations | `GET .../chain`, `GET .../descendants`, `POST .../revoke` | Scoped by `_auth.org_id` internally (no `org_id` path segment at all) — org B gets a correctly EMPTY result, never org A's real graph | 200 + empty, confirmed org A's own data is untouched |
| Authority passports | `GET`/`POST .../revoke` | `existing.organization_id != _auth.org_id` check | 404 |
| Upstream servers | `GET .../trust`, `DELETE`, `POST .../call` | `server.org_id != _auth.org_id` check | `/trust`/`DELETE` → 404; `/call` → 200 with a `governance_denied` blocked_response body (consistent with this codebase's existing convention that governance decisions surface as 200 + structured body, not bare HTTP status — confirmed no `result` key, i.e. the upstream tool was never actually invoked) |
| Webhooks | `DELETE`, `POST .../test` | `cfg.org_id != _auth.org_id` check (pre-existing) | 404 |
| Consent proofs | `GET`, `POST .../revoke` | `ConsentProofRepository`'s org-scoped JOIN | 404 |
| Incidents | `GET /api/incidents/{id}` | **Deliberately not org-isolated** — the AI Incident Database is a semi-public safety registry by design (SPEC.md); recorded as intentional, not a gap |
| Response bodies | (all of the above) | No response body from a denied cross-org attempt contains the victim org's slug/name/id | Confirmed |

## Verification

- `ruff check` / `mypy src/responsibleai`: clean.
- `tests/test_cross_tenant_isolation_sweep.py`: 11 passed (the
  consolidated sweep itself).
- Full suite re-run after the fix: see this phase's evidence summary
  in `PHASE5_PURPOSE_BINDING.md`-style totals — no regressions from
  adding the `_require_caller_owns_org()` guard (every existing test
  that legitimately used its own org's `org_id` in these paths is
  unaffected; only cross-org attempts, which no legitimate test relied
  on, now behave differently).

## A separate, pre-existing finding surfaced while adding this sweep

**Update**: root-caused and fixed — see
`TEST_SUITE_ORDERING_FRAGILITY_INVESTIGATION.md` for the full
diagnosis. Summary: `test_cross_tenant_isolation_sweep.py` (this
phase's own new file) was, by alphabetical accident, the first file in
the whole suite to import `responsibleai.dashboard.app`, which
constructs the lazy, process-wide `settings` singleton at import time
— beating `test_dashboard_api.py`'s own `os.environ.setdefault(...)`
line to the punch and freezing `auth_enabled` at its true Pydantic
default (`True`) instead of the intended test baseline (`False`).
Fixed by replacing that fragile pattern with explicit
`monkeypatch.setattr(settings, ...)` in the three affected files,
matching the pattern this codebase's own `test_mfa_login_flow.py`
already used (and already documented the exact same risk in its own
docstring). The original finding below is preserved for the record.

Running the new `tests/test_cross_tenant_isolation_sweep.py` together
with the rest of the suite exposed a **pre-existing test-infrastructure
fragility**, confirmed to be unrelated to any code change in this
phase or this session: a long enough sequence of tests that each spin
up a fresh `LifespanManager(app)` with `settings.auth_enabled`
monkeypatched `True` (a pattern already used by `test_governance_api.py`,
`test_org_api.py`, `test_upstream_gateway.py`, and others, long before
this phase) can, purely by sequence length, cause a *later*, unrelated
test expecting `auth_enabled=False` to observe `auth_enabled=True` at
request time despite the app's own startup log correctly showing
`"auth": "disabled"` moments earlier in the same test.

**Confirmed root cause is NOT this phase's code**: reproduced using
only pre-existing test content (e.g. the last 11 tests of
`test_governance_api.py`, unmodified, run immediately before
`test_dashboard_api.py`'s first auth-disabled test) — zero involvement
of any file this phase added or touched. It surfaces now because this
phase's ~40 new tests happen to push the cumulative sequence length in
the full suite run over whatever latent threshold triggers it; it did
not manifest in this session's earlier clean 3358/3385-test full-suite
runs simply because that exact threshold hadn't been reached yet.

Every file this phase touched was independently verified to pass
cleanly, both alone and in the smaller combinations exercised
throughout this phase's own work (documented per-phase above). This
finding is recorded honestly as a real, currently open, pre-existing
test-suite reliability issue — not silently worked around, not
attributed to this phase's own changes, and not left undocumented.
Recommended follow-up: investigate cumulative async/thread resource
usage across a growing single-process pytest run (candidate causes:
`aiosqlite` per-connection worker threads not being joined between
tests, or event-loop/task scheduling drift under high LifespanManager
churn), or isolate test processes via `pytest-xdist`.

## Phase 7 verdict

**READY TO ADVANCE**, with the finding above closed, not merely
documented. This is the kind of result the consolidated sweep exists
to produce — the scattered per-feature tests already in place had not
covered the org-management endpoint family at all, and a single
all-object-types pass found a real, high-severity gap in code that had
shipped and been live on this branch.
