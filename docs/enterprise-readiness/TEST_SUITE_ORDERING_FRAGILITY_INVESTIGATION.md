# Investigation — Pre-Existing Test-Suite Ordering Fragility

Follow-up to `PHASE7_CROSS_TENANT_ISOLATION.md`'s "separate, pre-existing
finding" section, which recorded that a real test-suite fragility had
been *discovered* but not yet root-caused. This document is that root
cause, the fix, and the verification.

## Root cause, confirmed with direct instrumentation, not guessed

`responsibleai.dashboard.config.get_settings()` is a **lazy,
process-wide singleton** — the `Settings` object is constructed once,
on whichever line of code across the *entire pytest session* first
calls it, and cached forever after (`dashboard/config.py`'s module-level
`_settings: Settings | None = None`). `dashboard/app.py` triggers this
at **module import time** (`settings = get_settings()`), so the
singleton's real, unpatched values get frozen the moment *any* test
file first imports `responsibleai.dashboard.app` — not when that file's
own tests actually run.

Several test files (`test_dashboard_api.py`, `test_redteam_audit_billing_api.py`,
`test_signup.py`) tried to force a known baseline (`auth_enabled=False`,
`db_path=":memory:"`, etc.) via `os.environ.setdefault("RAI_AUTH_ENABLED", "false")`
at their own module level, betting that their own import would be the
*first* thing in the whole session to construct the settings singleton.
`Settings` being a `pydantic-settings` `BaseSettings` reads environment
variables only at construction time — so this bet only pays off if
their `os.environ.setdefault()` line executes *before* any other file's
import chain reaches `dashboard.app`'s `settings = get_settings()` line.

**`auth_enabled`'s real Pydantic field default is `True`, not `False`**
(confirmed directly: `Settings().auth_enabled == True` with no env
override) — so whichever file loses that race gets the singleton
frozen with `auth_enabled=True`, and every `monkeypatch.setattr(settings,
"auth_enabled", True)` elsewhere in the suite correctly reverts back to
that now-wrong "true" baseline afterward, since `True` genuinely was
the object's unpatched value the whole session.

**Confirmed with direct diagnostic instrumentation** (temporary prints
at `get_org_context()` and at the `_auth_enabled_with_bootstrap_key`
fixture's set/revert points, since reverted): `id(settings)` was
identical across the entire failing sequence — same singleton
throughout — and `settings.auth_enabled` really was `True` at the
exact request that should have seen `False`, while a sibling
monkeypatched attribute on the same object (`api_keys`) correctly
reverted to its own true default (`[]`) at the same moment. This ruled
out thread/task leakage, event-loop reuse, or object aliasing (all
checked and ruled out first) — the singleton itself was simply frozen
with the wrong baseline before the "fix it via os.environ" file ever
got a chance to run.

**Directly identified which file won/lost the race**, via
`pytest --collect-only -q` on the real default (directory-scan)
collection order:

```
tests/test_cross_tenant_isolation_sweep.py::...   (line 649)
tests/test_dashboard_api.py::...                  (line 727)
```

`test_cross_tenant_isolation_sweep.py` (added in the Phase 7 work) is
collected — and therefore imported, triggering
`from responsibleai.dashboard.app import app, limiter, settings` —
*before* `test_dashboard_api.py` is even imported, let alone before its
`os.environ.setdefault("RAI_AUTH_ENABLED", "false")` line runs. This
froze the singleton with `auth_enabled=True` before
`test_dashboard_api.py` ever got a chance to influence it. Two other
pre-existing files sort alphabetically earlier still
(`test_config.py`, `test_crypto_activation.py`) but were checked and
confirmed to import only `responsibleai.dashboard.config.Settings`
(the class) — never `responsibleai.dashboard.app` — so neither of them
ever triggered the singleton early. `test_cross_tenant_isolation_sweep.py`
is genuinely the first file, across this whole session's changes, to
do so.

**This explains both previously-reported failure clusters** (23–25%
and 78–80% of the full suite): `test_dashboard_api.py` (cluster 1) and
`test_redteam_audit_billing_api.py` (cluster 2) used the identical
fragile pattern; both lost the same race once
`test_cross_tenant_isolation_sweep.py` existed.

**Why this was "pre-existing" but never manifested before**: the
`os.environ.setdefault()` pattern was always fragile by construction —
it depended on an implicit, undocumented assumption about collection
order that nothing enforced. It happened to hold by accident for as
long as no alphabetically-earlier file imported `dashboard.app` before
these files did. Confirmed this was already a *known, named* problem
in this codebase, not a novel discovery: `test_mfa_login_flow.py`
already carries a module docstring describing this exact race and
already uses the robust fix (explicit `monkeypatch.setattr(settings, ...)`)
— that file's author had already hit and fixed this once, but the
fix was never applied to the other three files sharing the fragile
pattern.

## Fix

Replaced the `os.environ.setdefault(...)` pattern in all three
remaining fragile files with an explicit `autouse=True` fixture that
`monkeypatch.setattr()`s the shared `settings` singleton directly —
the same pattern `test_mfa_login_flow.py`, `test_governance_api.py`,
`test_org_api.py`, and others already use. This is deterministic
regardless of module-import order: it doesn't matter who constructs
the singleton first, because every test in these files now forces its
own required values explicitly, every time, and `monkeypatch` reverts
them correctly after each test regardless of what the object's
"native" unpatched value happens to be.

Files fixed:
- `tests/test_dashboard_api.py`
- `tests/test_redteam_audit_billing_api.py`
- `tests/test_signup.py`

No production code changed — this is purely a test-infrastructure fix.

## Verification

- All three fixed files pass in isolation (109 + 45 = 154 tests).
- The exact previously-failing sequence
  (`test_governance_api.py`'s last 11 tests → `test_dashboard_api.py` →
  `test_redteam_audit_billing_api.py` → `test_signup.py`, all in one
  process) now passes cleanly: 165 passed, 0 failed.
- Full suite re-run in progress/completed separately to confirm no
  other file shares this same fragile pattern in a way that still
  surfaces under the real default collection order.

## Lesson, stated plainly

A module-level `os.environ.setdefault()` used to configure a lazily-
constructed singleton is a race condition disguised as configuration —
it "works" only as an accident of file collection order, which no one
declares or enforces, and which changes every time a new test file is
added anywhere in the suite. The fix that was already half-adopted in
this codebase (`test_mfa_login_flow.py`'s explicit monkeypatch) should
be the only pattern used going forward; any remaining
`os.environ.setdefault("RAI_*", ...)` at test-module level for a
setting the `Settings` singleton reads is the same latent bug waiting
for the right new file to surface it again.
