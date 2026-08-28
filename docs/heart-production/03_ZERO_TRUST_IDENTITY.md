# Zero-Trust Identity — Phase 1 (Typed `IdentityKind`)

> Closes the gap `docs/enterprise-neural/PROGRESS_LEDGER.md` already
> forward-referenced as "NOT STARTED (merges with `docs/heart-production/`
> Phase 3+)" and this series' own `02_IDENTITY_RESOLUTION.md` left open.
> Numbered `03_` to continue that series' own sequence — this is that
> forward reference, not a new, disconnected initiative.

## Reproduction

Independently re-verified: `IdentityContext.kind` (`governance/models.py`,
pre-this-phase) was a plain, unconstrained `str` with six informal
literal values documented only in a trailing comment
(`kind: str  # "human" | "api_key" | "agent" | "oidc" | "workload"` —
note even that comment omitted `"vc"`, itself evidence of how easy an
unconstrained string field is to let drift out of sync with reality).
Of those six, only three were ever actually constructed anywhere in
`src/` (`"api_key"`, `"oidc"`, `"vc"`) — `"human"`, `"agent"`,
`"workload"` existed only in comments and in
`02_IDENTITY_RESOLUTION.md`'s mapping table, aspirational rather than
live. A second, independent unconstrained `str` field,
`PrincipalClaim.holder_kind` (`governance/principal.py`), carried
overlapping identity-type meaning (`"service_account"` /
`"external_agent"`) with no formal reconciliation to the first. No
`Device`, `BCI Session`, `Tool`, or `Service` identity type existed in
either vocabulary, despite this codebase having a real (if
no-hardware-adapter) BCI/neural product surface (`governance/neural/`)
whose `session_id`/`device_identity` fields were never linked to
`IdentityContext` at all.

## What this phase does

Adds `IdentityKind(StrEnum)` (`governance/models.py`) as the closed,
typed replacement for `IdentityContext.kind`'s free-form string:

| Member | Value | Status before this phase |
|---|---|---|
| `HUMAN` | `"human"` | Documented, never constructed |
| `ORGANIZATION` | `"api_key"` | Constructed (as `"api_key"`) |
| `OIDC` | `"oidc"` | Constructed |
| `VERIFIED_CREDENTIAL` | `"vc"` | Constructed (as `"vc"`) |
| `AGENT` | `"agent"` | Documented, never constructed |
| `WORKLOAD` | `"workload"` | Documented, never constructed |
| `DEVICE` | `"device"` | **New — no prior representation** |
| `BCI_SESSION` | `"bci_session"` | **New — no prior representation** |
| `TOOL` | `"tool"` | **New — no prior representation** |
| `SERVICE` | `"service"` | **New — no prior representation** |

`identity_authority_adapter.py`'s `_KIND_TO_ROOT_TYPE` mapping table is
now keyed by `IdentityKind` (was `str`) and gains four new rows —
`DEVICE`/`BCI_SESSION` → `RootType.WORKLOAD_IDENTITY`, `TOOL`/`SERVICE`
→ `RootType.SERVICE_PRINCIPAL` — none terminal, for the same reason
`AGENT`/`WORKLOAD` already aren't: none of the four is human- or
organization-controlled by construction.

A new `identity_kind_from_holder_kind()` function reconciles
`PrincipalClaim.holder_kind`'s independent wire-format values
(`"service_account"` → `IdentityKind.SERVICE`, `"external_agent"` →
`IdentityKind.AGENT`) with the new typed vocabulary, and
`build_root_authority_record_from_principal_claim()` now routes
through it instead of hardcoding `RootType.SERVICE_PRINCIPAL` directly
— both known mappings still resolve to `SERVICE_PRINCIPAL`, so this is
a consistency/documentation change, not a behavior change.

Five construction sites in `src/` updated to use `IdentityKind` members
instead of raw string literals: `governance/models.py` (both
`IdentityContext` classmethods), `mcp/governance_integration.py` (two
sites), `mcp/upstream_dispatch.py`, and
`integrations/identity_bridge.py`'s `to_identity_context()` default
parameter.

## Why this is non-breaking

`IdentityKind` is a `StrEnum` — its members compare and hash equal to
their plain string value. Python does not enforce dataclass field
types at runtime. The ~30 existing test files across this repository
that already construct `IdentityContext(kind="agent")` (a plain `str`,
not an `IdentityKind` member) continue to behave identically: dict
lookups in `_KIND_TO_ROOT_TYPE`, equality checks, and every existing
test assertion all still pass, verified directly in
`tests/test_identity_kind.py`'s `TestBackwardCompatibilityWithPlainStrings`
class. `mypy` only checks `src/responsibleai` in this repo's CI
(`.github/workflows/ci.yml`), not `tests/`, so no test file needed
updating for the stricter type annotation either.

## What this phase does not do — named explicitly

- **Does not separate authentication mechanism from identity type.**
  `OIDC`/`VERIFIED_CREDENTIAL` describe *how* something authenticated,
  not *what* it is — `identity_authority_adapter.py`'s own docstring
  already documents `"oidc"` as ambiguous (a human via SSO and a
  machine via client-credentials both produce `kind=OIDC` today, no
  discriminator exists in the live code to tell them apart). Properly
  resolving this needs a real signal this codebase doesn't capture yet
  (e.g. a token's `azp`/client-type claim). Left as a documented,
  known remaining gap — not silently designed around, and not solved
  by this phase's type-safety upgrade alone.
- **Does not wire `DEVICE`/`BCI_SESSION`/`TOOL`/`SERVICE` into any live
  construction path.** No code today authenticates a request as a
  device, BCI session, or tool — these four members close the
  *vocabulary* gap (a type-safe place for them to exist once such a
  path is built) without inventing the authentication mechanism that
  would produce one. `governance/neural/` (the real BCI/neural
  product surface) still has its own separate `session_id`/
  `device_identity` vocabulary; this phase does not merge them —
  doing so honestly requires deciding how a neural session's device
  trust (`DeviceTrustLevel`, `neural/device.py`) relates to
  `IdentityContext`'s authentication concept, which is a real design
  question, not a mechanical rename, and is left for a later phase.
- **Does not touch `AgentContext`.** Per `docs/heart-production/00_CURRENT_RUNTIME_MAP.md`
  §4, `AgentContext.agent_id` still equals the org credential's own
  `key_id` in every live path — the structural separation between
  "what identity type authenticated" (`IdentityContext.kind`, now
  typed) and "what distinct agent/service is acting" (`AgentContext`)
  already existed before this phase and is unchanged by it.

## Verification

- 34 tests passing: 15 new (`tests/test_identity_kind.py`) plus all 19
  pre-existing `tests/test_identity_authority_adapter.py` tests
  unmodified and still green — confirming the type change broke
  nothing.
- `ruff check` / `ruff format --check` clean on every touched file.
- `mypy src/responsibleai` (the exact CI invocation): clean, 166
  source files, no errors.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
