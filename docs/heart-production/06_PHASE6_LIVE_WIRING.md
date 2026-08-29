# Heart Production Integration — Phase 6: Live Decision-Path Wiring

> Continues the numbered series (`00` runtime audit, `01` contract,
> `02` identity resolution, `03` Zero-Trust Identity, `04` Authority
> Resolver, `05` OIDC subject classifier — this is `06`, the wiring
> both `04` and `05` deliberately deferred).

## What this phase wires in

Two things, both gated the same way (**opt-in, default-off, zero
behavior change unless explicitly enabled**):

1. **The Authority Resolver (Phase 5)**, into `apply_governance()`
   (`mcp/governance_integration.py`) and `apply_upstream_governance()`
   (`mcp/upstream_dispatch.py`) — the second wiring point
   `00_CURRENT_RUNTIME_MAP.md` §15 named as missing. A new
   `_heart_legitimacy_denied_reason()` function in each file runs
   `resolve_authority_grant()` and denies with
   `ReasonCode.HEART_LEGITIMACY_FAILED` when the Heart's own verdict
   says the identity's authority doesn't trace to a legitimate root —
   but **only** when both `GovernanceServices.root_authority_repo` is
   wired (always true once `mcp_governance_enabled` is on) **and**
   `Settings.enterprise_mode` is true. Follows the identical
   "continuous re-authorization" insertion point the delegation-graph
   check already established: computed before `gateway.evaluate()`,
   short-circuits to `DENY` if set, evidence-recorded like any other
   decision.
2. **The OIDC subject classifier (`05_OIDC_SUBJECT_CLASSIFIER.md`)**,
   into both copies of `_resolve_oidc_context()`
   (`mcp/server.py`, `dashboard/app.py`). A new `OrgContext.
   oidc_classified_human` field carries the classifier's verdict from
   token-resolution time through to identity construction. A new
   `identity_kind_from_org_context()` function
   (`governance/models.py`) replaces the three previously-duplicated
   `IdentityKind.OIDC if ... else IdentityKind.ORGANIZATION` ternaries
   (`IdentityContext.from_org_context()`,
   `mcp/governance_integration.py`, `mcp/upstream_dispatch.py`) with
   one shared source of truth, so the classifier's `HUMAN` elevation
   can't silently drift between the three call sites.

## Why the Authority Resolver's live effect is deliberately narrow

Wiring the resolver as a hard gate would, if turned on today, deny
**every** OIDC- or VC-authenticated identity that has no configured
`authority_source` — which is all of them, since no live consent/
delegation-chain-building flow exists yet (Phase 5's own documented
scope limit). Only a static-API-key identity (`kind=ORGANIZATION`,
terminal by construction) or a classifier-elevated `kind=HUMAN`
identity passes today. This is not a bug to work around — it is the
correct, honest behavior of actually enforcing root-of-trust
legitimacy: a deployment that turns `enterprise_mode` on is asserting
it wants that enforcement, and must configure real root chains
(or classifier claims) for any identity kind beyond static API keys
before doing so, exactly the same "opt-in, understand what you're
enabling" posture every other `enterprise_mode`-gated feature in this
remediation (crypto activation, stdio governance) already has.

## A real bug this phase's own testing caught

Both new `_heart_legitimacy_denied_reason()` functions were initially
written with a **module-level** `from responsibleai.dashboard.config
import get_settings` import. `get_settings()` is a process-wide
cached singleton (`dashboard/config.py`'s own `_settings` global) —
`mcp/server.py`'s `_build_http_app()` already works around this by
using a **local** import inside the function body, re-resolving
`get_settings` fresh from the module every call, specifically so tests
that monkeypatch `config_module.get_settings` to inject a different
`Settings` instance actually take effect. The module-level import in
both new functions bypassed that pattern: it bound `get_settings` once
at whatever moment `governance_integration`/`upstream_dispatch` was
first imported in the test process, silently ignoring any later
test's monkeypatched settings and always reading the real,
env-derived, `enterprise_mode=False` singleton instead.

This was caught by `tests/test_heart_wiring_phase6.py` itself — the
first version of the Heart-gate-denies test passed in isolation but
failed when run after `TestHeartGateOffByDefault` in the same process,
exactly the test-order-dependent symptom a stale cached reference
produces. Fixed by switching both functions to the same local-import
pattern `mcp/server.py` already established. Named here explicitly
because it's a real, general lesson for this codebase: any new
`enterprise_mode`/`Settings`-gated code path needs a local import of
`get_settings`, not a module-level one, to stay test-controllable —
and because it's proof this phase's "test before wiring into the hot
path" discipline caught something real, not just theoretical caution.

## Verification

- New test file `tests/test_heart_wiring_phase6.py`, 5 tests, all
  passing, end-to-end through a real hosted MCP app (not just the
  resolver/classifier in isolation): the gate is a complete no-op by
  default; a non-terminal OIDC identity is correctly denied once
  `enterprise_mode` is on; a terminal static-API-key identity is still
  allowed even with the gate on (proves the common case isn't broken);
  a classifier-elevated `HUMAN` identity passes the gate that an
  unclassified `OIDC` identity fails; a configured-but-non-matching
  claim correctly stays denied (the classifier's own fail-safe,
  proven again at the live-wiring level).
- Full pre-existing regression suite re-run clean: `test_mcp_governance_dispatch.py`,
  `test_resilience_fail_closed_matrix.py`, `test_upstream_gateway.py`,
  `test_identity_authority_adapter.py`, `test_identity_kind.py`,
  `test_authority_resolver.py`, `test_oidc_subject_classifier.py`,
  `test_config.py`, `test_mcp_oauth.py`, `test_governance_observability.py`,
  `test_mcp_verified_principal.py` — 189 tests, all passing, confirming
  the wiring didn't regress any existing governed-call behavior.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 169 source files.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.

## What remains, named honestly

- **No live consent/delegation-chain-building flow.** An identity
  beyond a static API key needs a real `authority_source` chain to
  pass the gate under `enterprise_mode` — building that flow (linking
  an OIDC/VC identity to a legitimate human/org root, in the general
  case, not just via the classifier's narrow HUMAN-elevation path) is
  separate, substantial, product-shaped work.
- **Revocation-epoch and consent/purpose/delegation-legitimacy checks
  remain unrun**, per `04_AUTHORITY_RESOLVER.md`'s own scope limits —
  this phase wires in exactly what Phase 5 built, nothing more.
- **`RootAuthorityRepository.get_latest_for_subject()` bootstraps a
  fresh root on first sight of any identity.** For a static API key
  this is immediately terminal and harmless; for anything else it
  creates a persisted, non-terminal root record with no source that
  will keep failing the gate until a real chain is established — not
  itself a problem, but worth knowing this phase does create DB rows
  for identities it denies, not just for ones it allows.
