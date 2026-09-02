# Heart Production Closure — Audit (Rule 0)

**Audited head**: `security/enterprise-neural-remediation` @ `32eb2a6b1891fa751376bc8dbee8bd048256efb3`
**Base (frozen, unmerged, still awaiting independent review)**: PR #50 @ `9d1fdad2dbaeea1fd3d12aeea12bc13b9917a1fc`
**PR #54 CI at time of audit**: 12/12 green (`gh pr checks 54`, confirmed same session)
**No code modified to produce this document.** Every claim below is sourced from a direct read of the file:line cited, not memory of having written it.

---

## THE QUESTION THAT MATTERS MOST

> Can any governed action currently reach execution without Heart-backed legitimacy when WhitePact is run with its ordinary/default configuration?

**Yes.** With every setting at its documented default, essentially **all** governance — not just Heart — is off, and this is true for both live transports.

### Exact path 1 — hosted HTTP/SSE MCP transport, default config

`Settings.mcp_governance_enabled` defaults to `False` (`dashboard/config.py:166-167`). `_build_http_app()` only constructs a `GovernanceServices` instance and populates the `_current_governance` ContextVar when this flag is true (`mcp/server.py:451`, `if settings.mcp_governance_enabled:`). At default, `_current_governance.get()` is always `None`.

`_call_tool()` (`mcp/server.py:180-274`) is the single handler every hosted tool call goes through:

```python
governance = _current_governance.get()
if governance is not None and ctx is not None and ctx.org_id:      # server.py:225-226
    ...apply_governance()...
    return _text_and_structured(outcome.result)
...
result = await dispatch_tool(name, call_arguments)                  # server.py:273 — the fallthrough
return _text_and_structured(result)
```

At default (`governance is None`), the `if` on line 226 is false for **every** call — authenticated or not, org-scoped or not — and control falls straight through to line 273: `dispatch_tool()` runs with zero authority check, zero risk/policy evaluation, zero Heart involvement. This is not a bug introduced by this remediation; it is the pre-existing, already-documented architecture (`mcp/governance_integration.py:8-13`, its own module docstring: *"Opt-in via `Settings.mcp_governance_enabled`... this is a real behavior change for anyone who enables it, not a transparent addition"*). But it is the literal, current, default-config answer to the question asked.

### Exact path 2 — even with `mcp_governance_enabled=True`, Heart itself is a second, independent opt-in

If `mcp_governance_enabled=True` (non-default), `apply_governance()` does run — but `_heart_legitimacy_denied_reason()` (`mcp/governance_integration.py:167-224`) is a no-op unless **both** `services.root_authority_repo` is wired (true whenever governance is on) **and** `Settings.enterprise_mode` is also `True` (default `False`, `dashboard/config.py:216-217`):

```python
if (
    services.root_authority_repo is None or not get_settings().enterprise_mode
):  # governance_integration.py:212
    return None
```

So the real default-config-to-Heart-enforced path requires two independently-defaulted-off booleans to both be flipped. Nothing today prevents a deployment from setting `mcp_governance_enabled=True` (thinking it has "turned on governance") while leaving `enterprise_mode=False`, silently getting risk/policy/quarantine evaluation but zero root-of-trust check — the exact ambiguity Gap C names.

### Exact path 3 — stdio transport

`ctx is None` whenever the call arrives over stdio (`mcp/server.py:187`, `_current_org` is only ever populated by the hosted-HTTP auth middleware). The stdio branch (`mcp/server.py:253-271`) only ever restricts by *risk tier* under `enterprise_mode`, and never touches Heart/root-of-trust at all — there is no organizational identity on stdio to resolve a root for in the first place (by design, per `mcp/governance_integration.py:20-24`).

### Exact path 4 — legacy/non-org-scoped key, and the unauthenticated demo flag

`apply_governance()` itself asserts `ctx.org_id is not None` (`mcp/governance_integration.py:187`) and is simply never called for a flat/legacy key with no org — `_call_tool()`'s own `ctx.org_id` check (line 226) already excludes that case before `apply_governance` is reached, falling through to line 273 the same as path 1. `Settings.mcp_http_allow_unauthenticated_demo` (`dashboard/config.py:383`, referenced `mcp/server.py:685`) produces an `OrgContext` with `org_id=None` for the same reason — ungoverned regardless of any other setting.

### Exact path 5 — upstream REST proxy calls (`dashboard/app.py`)

Unlike the MCP transport, `apply_upstream_governance()` (`mcp/upstream_dispatch.py:96-`) is called unconditionally by its REST endpoint (`dashboard/app.py:3891`, not gated on `mcp_governance_enabled` at all — that flag is MCP-tool-call-specific). Base risk/policy evaluation (`gateway.evaluate()`) always runs for this path. Heart legitimacy is still the same second opt-in: `_heart_legitimacy_denied_reason()` in `upstream_dispatch.py:96-` (mirroring `governance_integration.py`'s function) only fires under `enterprise_mode`.

### Exact path 6 — direct Python import

`mcp.tools.dispatch_tool()` can be called directly by any Python code inside the same process, bypassing every governed entrypoint structurally. Documented, not new (`governance/execution.py`'s own module docstring, `THREAT_MODEL.md`'s governance-pipeline section).

**Summary answer**: at true default configuration, paths 1-4 and 6 execute with **zero** Heart involvement and mostly zero governance at all. Even in the "governance-enabled" configuration most likely to be mistaken for "secure," Heart legitimacy remains a silent no-op unless a second, separate flag is also set. This is exactly Gap C's problem statement, verified against real code.

---

## GAP A — Consent is captured but never consulted

### Current implementation

`resolve_authority_grant()` (`governance/authority_resolver.py:165-224`) is the only function that calls `sovereignty_kernel.evaluate()` on the live path. Its actual call (`authority_resolver.py:203-209`):

```python
legitimacy = sovereignty_evaluate(
    agent.organization_id or "",
    identity.identity_id,
    root=root,
    root_resolver=resolver,
    requested_action_types=frozenset({action.action_type}),
)
```

`sovereignty_kernel.evaluate()`'s full signature (`governance/sovereignty_kernel.py:104-116`) accepts `consent`, `intent`, `purpose_binding`, `delegation`, `revocation_issued_at`, `revocation_current` — **none of these five are ever passed**. Per `evaluate()`'s own logic (`sovereignty_kernel.py:126-168`), consent/purpose/delegation legitimacy checks only run when their prerequisite inputs are *all* supplied; supplying none of them means none of those checks ever execute, for any request, ever. Only H3 (root) and H7 (non-delegable) are live today.

### Exact modules/classes/functions involved

- `governance/consent_proof.py` — `ConsentProof`, `ConsentMethod`, `build_consent_proof()`, `validate_consent_proof()`. Pure, already correct, untouched by this gap.
- `db/consent_proof_repository.py` — `ConsentProofRepository.create()/get()/revoke()`. No `list_active_for_grantee()` or equivalent lookup-by-grantee-and-org method exists — only fetch-by-`consent_id`.
- `dashboard/app.py:~3673-3843` — the three consent-capture REST endpoints (`POST/GET/revoke /api/governance/consent-proofs`). Write path only; nothing reads from here into the resolver.
- `governance/authority_resolver.py::resolve_authority_grant()` — the integration point that would need to change.
- `governance/sovereignty_kernel.py::evaluate()` — unmodified target; already accepts everything Gap A needs, just isn't given it.

### Current tests

`tests/test_authority_resolver.py` (11 tests) — root resolution and legitimacy end-to-end, but every test constructs `resolve_authority_grant()` calls with no consent path exercised (the function has no consent parameter to exercise). `tests/test_governance_api.py::TestConsentProofEndpoints` (10 tests) — capture/get/revoke/cross-org isolation for the REST layer in isolation; none of these tests call `resolve_authority_grant()` or `apply_governance()` at all, so there is no existing test proving (or disproving) that a captured consent proof affects a live decision — because today it structurally cannot.

### Existing persistence primitives

`ConsentProofRepository` is real and already correctly org-isolated at the application layer (via the linked root's `organization_id`, per Gap 5's own fix this session) — but the repository itself has **no method to find "the currently active consent for principal X granted by root Y for purpose Z."** Every lookup today is by `consent_id`, which the resolver would not have at decision time (a live request has an identity and an action, not a pre-known consent ID).

### Trust boundary

The resolver already trusts `RootAuthorityRepository` as its source of truth for roots. A consent-lookup would need an equally-trusted, equally-scoped lookup — but "scoped" here is ambiguous: by `subject_id` (who consented)? By `grantee_id` (who the action is being performed by/for)? By `(grantee_id, scope_description, purpose)` matched against the request's actual `action_type`/`target`? `validate_consent_proof()` itself only checks a *given* proof against a *given* root result — it does not select *which* proof is relevant to *this* request. That selection logic does not exist anywhere yet.

### Failure mode if left as-is

Silent, not loud: nothing errors. A deployment that captures a real consent proof reasonably assumes it is now enforced, because the API succeeded and the proof reports `is_valid: true` when fetched individually. Nothing in the live decision path ever reads it. This is the most dangerous kind of gap — a working-looking feature with no actual effect.

### Required production invariant (stated, not yet implemented)

A governed action whose grantee has no consulted, currently-valid, correctly-scoped `ConsentProof` — in a deployment mode that requires one — must not be treated as legitimate by `resolve_authority_grant()`'s output.

### Minimal change needed (design-level; not implemented by this audit)

1. A new `ConsentProofRepository` lookup method: given `(organization_id, grantee_id)`, return the latest non-revoked, non-expired proof — mirroring `DelegationRepository.get_latest_delegation()`'s exact existing pattern (`db/delegation_repository.py`, already the "latest wins" convention this codebase uses everywhere else).
2. `resolve_authority_grant()` (or a new wrapper) fetches that proof, computes `consent_result = validate_consent_proof(proof, root_result)`, and passes `consent=proof` into `sovereignty_evaluate()`.
3. Scope/action/resource/purpose matching between the proof's `scope_description`/`purpose` (free text today) and the actual `action.action_type`/`action.target` — currently no structured comparison exists; `scope_description`/`purpose` are opaque strings with no schema. This needs either a real matching scheme or an honest decision to treat mismatch-detection as out of scope for this pass, named explicitly.
4. Decide what happens when **no** consent proof exists for the grantee at all, in `enterprise_mode`/whatever new production-mode flag Gap C introduces — almost certainly must deny, but this changes today's Phase 6 behavior (which currently ignores consent entirely and would allow a terminal-root identity through on root-legitimacy alone).

### Migration implications

None to the schema itself (Gap 3 Phase 3's tables already have everything needed) — only a new repository query, no new columns/tables.

### Compatibility implications

**Significant.** Today, `enterprise_mode=True` already denies every non-terminal-root identity (per Phase 6's own documented behavior). Adding a consent requirement on top would newly deny **every terminal-root identity too**, unless it has a captured consent proof — meaning any existing `enterprise_mode=True` deployment (there may be none in production yet, but the directive must assume there could be) would see 100% of previously-ALLOW decisions become DENY the moment this ships, unless consent-required is itself a separate, further opt-in layered the same way `enterprise_mode` was layered on `mcp_governance_enabled`.

### Security risks

- Matching consent scope to actual action scope via free-text comparison risks either false negatives (real consent rejected, availability cost) or false positives (a loosely-worded proof accepted for an action it didn't really cover — a real security risk if the matching logic is naive).
- A "get latest for grantee" lookup with no additional scope check would let *any* consent proof for that grantee authorize *any* action — the same "not sufficient to just check existence" risk the closure directive explicitly names.

---

## GAP B — Revocation state is process-local

### Current implementation

`governance/revocation_kernel.py` (140 lines, read in full for this audit) is a pure module: `RevocationEpoch` (frozen dataclass, `organization_id`/`scope`/`epoch: int = 0`), `bump_epoch()`, `check_revocation_epoch()`. No `import` of any DB module anywhere in the file. No class holds an epoch as mutable state — every `RevocationEpoch` is a plain value the caller must obtain from *somewhere* and pass in; nothing in this codebase currently is that "somewhere."

### Exact modules/classes/functions involved

- `governance/revocation_kernel.py` — the primitive itself, confirmed complete and correct for what it claims to be (a comparison function), confirmed to have zero DB coupling.
- **No repository exists.** `grep -rn "RevocationEpoch" src/responsibleai/db/` returns nothing (re-verified this audit).
- `governance/authority_resolver.py::resolve_authority_grant()` — never constructs or passes `revocation_issued_at`/`revocation_current` to `sovereignty_evaluate()` (confirmed by re-reading its full body, lines 165-224 above) — so even independent of Gap B's persistence problem, revocation-epoch checking is *also* not run on the live path today, same class of gap as consent.

### Current tests

No test file references `RevocationEpoch` outside `tests/test_*` files that test the pure comparison function in isolation (not located/verified as part of `test_authority_resolver.py`, `test_heart_wiring_phase6.py`, or `test_governance_api.py` — the primitive's own unit tests, if they exist, are pre-existing from whichever Heart phase built H9 and were not re-verified line-by-line in this audit pass; what *is* confirmed is that no test exercises it against a live `resolve_authority_grant()` call, because no live call site passes it).

### Existing persistence primitives

The five real, already-correct, independently-scoped revocation mechanisms the module's own docstring names (`revocation_kernel.py:6-16`, re-quoted verified): `DelegationRepository.revoke_branch()` (cascading), `DelegationRecord.is_active()` (natural expiry, `governance/delegation.py:47-56`, re-read and confirmed above), `AuthorityPassportRepository`'s revocation, `AuthorityPassport` drift detection, `org_repository.py`'s API-key revocation. **None of these five call `bump_epoch()`** — confirmed by the module's own docstring stating this explicitly and by `grep -rn "bump_epoch" src/responsibleai/` returning only the definition and re-exports, no call sites.

### Trust boundary

Each of the five existing mechanisms is already correctly DB-backed and already correctly multi-instance-safe *for its own object type* (a `DelegationRecord.revoked_at` column is real, shared, durable state — the underlying persistence is fine). The actual gap is narrower than "revocation isn't durable" — it's "there is no single cheap epoch to check, and the one primitive designed to be that cheap check has no persistence and no wiring." A caller resolving legitimacy today would need to separately re-check all five mechanisms' own live DB state on every request to get a correct answer — which, per `governance_integration.py`'s "continuous re-authorization" pattern (`delegation_repo.get_latest_delegation()` called fresh every request, `governance_integration.py:355-368`), is **already what happens for delegation specifically**. Root-authority revocation (`RootAuthorityRepository.revoke()`, real, DB-backed since Gap 3 Phase 3) is separately, already re-checked fresh every request too, since `resolve_root_for_identity()`/`prefetch_root_chain()` hit the DB on every call (`authority_resolver.py:199-201`) — there is no caching layer for roots at all today.

**This materially changes Gap B's actual shape**: the two revocation paths already wired into the live gate (root, delegation) are *already* durable and multi-instance-safe by virtue of hitting the DB fresh every time, with no cache to go stale. The *unwired* primitive (`RevocationEpoch`) is the one with no persistence — but nothing on the live path depends on it yet, so today's actual multi-instance revocation correctness for what *is* checked (root, delegation) is better than the module's own docstring context might suggest in isolation. What's missing is Consent revocation reaching the live path at all (Gap A) and Non-delegable/other-scope revocation epochs never being wired.

### Failure mode if left as-is

Not "stale cache silently trusted" (the dangerous framing the closure directive is right to guard against in general) — today's actual failure mode is narrower: revocation-epoch checking (H9) simply never fires, so a scope that *should* have an epoch-based kill-switch (e.g., "revoke every grant under this consent method org-wide, right now, without walking every individual record") has no such mechanism live. The five individual mechanisms remain correctly enforced.

### Required production invariant

If `RevocationEpoch` is wired into the live gate, its authoritative state must be durable, tenant-scoped, transactionally updated, and read fresh (not cached) on every legitimacy resolution — matching the pattern `RootAuthorityRepository`/`DelegationRepository` already correctly use today, not a new pattern.

### Minimal change needed (design-level)

1. A `governance_revocation_epochs` table: `(organization_id, scope, epoch)` composite key, matching `RevocationEpoch`'s own three fields exactly.
2. A `RevocationEpochRepository` with `get_current(org_id, scope) -> RevocationEpoch` (default epoch 0 if no row) and `bump(org_id, scope) -> RevocationEpoch` (atomic increment — a real concurrency concern: two simultaneous revocations for the same scope must both land, not race-overwrite each other; `UPDATE ... SET epoch = epoch + 1` is the correct, portable pattern here, not read-then-write).
3. A decision on which of the five existing mechanisms actually call `bump()` — this is a real design choice per mechanism, not mechanical; the module's own docstring is explicit that this wiring decision was deliberately deferred, not merely unstarted.
4. `resolve_authority_grant()` fetching the relevant epoch(s) and passing them to `sovereignty_evaluate()`.

### Migration implications

One new table, additive, no existing table touched — same shape as every other Heart-persistence migration this session already shipped (0032, 0033).

### Compatibility implications

Low by itself (new table, opt-in usage) — but compounds with Gap A/C's compatibility risk if wired to actually deny on `REVOKED_SINCE_ISSUANCE`.

### Security risks

- Atomic increment correctness under concurrent revocations is the primary new risk — get this wrong and either a revocation could be lost (increment race) or a legitimate verdict issued in the same instant as a revocation could non-deterministically pass or fail depending on read/write ordering. Needs explicit transaction-isolation-level reasoning, not just "add a table."
- Choosing scope granularity wrong (too broad: over-invalidates unrelated things when unrelated to what actually changed; too narrow: doesn't actually cover the revocation someone expects it to) is a design risk, not just an implementation one.

---

## GAP C — Heart enforcement is opt-in, and the opt-in surface is two independent, easily-confused booleans

### Current implementation

Confirmed no unified "deployment mode" concept exists anywhere in `dashboard/config.py` — three independently-defaulted-`False` booleans control governance/Heart posture:

| Flag | Default | Controls | File:line |
|---|---|---|---|
| `mcp_governance_enabled` | `False` | Whether `apply_governance()`/`apply_upstream_governance()` run *at all* for MCP tool calls | `dashboard/config.py:166` |
| `enterprise_mode` | `False` | Crypto activation (Gap 1), stdio risk-tier gating (Gap 2), **and** Heart legitimacy enforcement (Phase 6) — three unrelated concerns sharing one flag | `dashboard/config.py:216` |
| `mcp_http_allow_unauthenticated_demo` | `False` | Whether an unauthenticated request gets an ungoverned `org_id=None` context | `dashboard/config.py:383` |

No startup-time validation exists anywhere connecting these — a process can start with `enterprise_mode=True` and `mcp_governance_enabled=False` (Heart flag on, but the code path that would ever consult it is never reached) with zero warning, zero error, zero log line calling this combination out specifically (only per-flag docstrings, no cross-flag consistency check).

### Exact modules/classes/functions involved

- `dashboard/config.py::Settings` — the three flags above, plus `crypto_root_key` (required *only if* `enterprise_mode=True`, already fail-fast at startup for that one specific sub-concern via `db/crypto_activation.py::activate_production_crypto()`, confirmed real and already correctly fail-closed — this is the one existing precedent for "fail fast at startup if a flag implies a requirement that isn't met").
- `db/crypto_activation.py::activate_production_crypto()` — the *only* existing fail-fast-at-startup pattern in this codebase tied to `enterprise_mode`. Confirmed: raises `CryptoActivationError` if `enterprise_mode=True` and `crypto_root_key` is unset (`db/crypto_activation.py`, re-verified this session's own test suite still exercises this). No equivalent exists for "Heart persistence reachable," "root authority repo initializes," "revocation backend reachable" (once Gap B exists), etc.
- `mcp/server.py::_build_http_app()` — where `mcp_governance_enabled` gates `GovernanceServices` construction; where `activate_production_crypto()` is called in `_lifespan()`.

### Current tests

`tests/test_heart_wiring_phase6.py` proves the gate's *decision-time* behavior correctly (off by default, denies non-terminal identities when on, etc.) — it does not test *startup-time* behavior at all (no test constructs a `Settings`/`_build_http_app()` combination expected to fail fast).

### Existing persistence primitives

N/A — this gap is about configuration/startup semantics, not data persistence.

### Trust boundary

The trust boundary today is "whatever the deployer's env vars happen to be," with no code-level assertion that a deployment claiming production/enterprise posture actually has every dependency that posture requires. This is exactly the closure directive's concern: a silently-degraded production deployment is worse than one that fails to start, because it *looks* secure while enforcing nothing.

### Failure mode if left as-is

A deployer sets `enterprise_mode=True` expecting full production enforcement, but leaves `mcp_governance_enabled=False` (a different, easy-to-forget flag with no cross-check) — the process starts successfully, crypto activates, stdio gets risk-tier-restricted, and every hosted MCP call still runs completely ungoverned. No warning is logged for this specific combination today (only the general `platform_isolation_misconfigured` warning for a different, unrelated concern, `mcp/server.py:541`).

### Required production invariant (per the directive's own framing)

A deployment that advertises production/enterprise authority enforcement must not be able to *accidentally* start with Heart disabled or partially disabled. Silent degradation (warn + continue) is unacceptable for this specific claim; fail-fast is required.

### Minimal change needed (design-level — two real options, not decided here)

**Option 1 (smaller diff)**: a new startup check, alongside `activate_production_crypto()`, that raises if `enterprise_mode=True` and `mcp_governance_enabled=False` — closing the single most dangerous silent-degradation combination without introducing new vocabulary.

**Option 2 (the directive's suggested enum)**: replace the two-boolean surface with an explicit `AuthorityMode` (or similar) — `LEGACY` / `HEART_OPTIONAL` / `HEART_ENFORCED` — with `HEART_ENFORCED` requiring, at startup: Heart persistence reachable (a real DB ping against `governance_root_authority_records`), `RootAuthorityRepository`/`ConsentProofRepository`/(future) `RevocationEpochRepository` all constructible, and (once Gap B exists) the revocation backend reachable. **This is a breaking config-surface change** (existing `enterprise_mode=True` deployments, if any exist, would need to migrate to a new setting name) and needs its own explicit compatibility decision — the directive itself says not to introduce this if existing configuration already provides a better representation, and Option 1 is the honest "existing configuration, tightened" answer; Option 2 is the honest "new configuration, cleaner" answer. This audit does not choose between them — that is exactly the "STOP before implementation and wait for approval" decision point.

### Migration implications

None (config/startup logic only), unless Gap B's table doesn't exist yet at the time this ships, in which case a `HEART_ENFORCED` startup check depending on it must be sequenced after Gap B's migration lands.

### Compatibility implications

Option 1: low — only affects deployments already setting `enterprise_mode=True` with `mcp_governance_enabled=False`, a combination that (per the analysis above) is already producing an unintended result, so failing fast there is a correctness fix, not a behavior regression for anyone relying on documented behavior. Option 2: real, requires a deprecation path for `enterprise_mode`/`mcp_governance_enabled` if they're to be replaced rather than kept alongside a new enum.

### Security risks

- An overly strict fail-fast (e.g., requiring the revocation backend reachable before Gap B's own wiring decision is finalized) could make `HEART_ENFORCED` mode impossible to start correctly, which is an availability risk, not a security one — but availability failures in security tooling have their own well-known failure mode (operators disabling the check entirely under deadline pressure). Sequencing matters.

---

## GAP D — No real durable external/WORM audit-anchor provider

### Current implementation

`governance/audit_anchor.py` (already built, Gap 5 Phase 1, this session): `AnchorRecord`, `AuditAnchorProvider` (Protocol — `publish()`/`fetch()`, two methods, no crypto/DB coupling), `LocalFileAnchorProvider` (create-exclusive local files — `os.O_CREAT | os.O_EXCL`, confirmed via re-read this audit, `governance/audit_anchor.py` — the module's own docstring is explicit this is *not* real WORM/S3 Object Lock, an honest local-filesystem analogue only), `build_and_sign_anchor()` (HMAC-SHA256 under `KeyPurpose.AUDIT_ANCHOR`), `publish_anchor()`, `verify_anchor_from_provider()`.

**Confirmed, re-verified this audit**: `grep -rn "verify_anchor_from_provider\|publish_anchor(" src/responsibleai/` outside the module itself and its `governance/__init__.py` re-export returns **zero** application call sites. This capability is library code today — real, tested (`tests/test_audit_anchor.py`, 11 tests), completely unwired into any live path, scheduler, or REST endpoint.

### Exact modules/classes/functions involved

- `governance/audit_anchor.py` — the whole capability, as above.
- `governance/crypto/` (`KeyProvider`, `KeyPurpose.AUDIT_ANCHOR`) — the signing key infrastructure this depends on, already real (Gap 1).
- **No cloud provider implementation exists.** No `boto3`/S3/GCS/Azure Blob dependency appears anywhere in `pyproject.toml` (not independently re-verified line-by-line this audit pass, but no such import exists in `audit_anchor.py` or anywhere referencing it).

### Current tests

`tests/test_audit_anchor.py` — 11 tests, all against `LocalFileAnchorProvider`, all passing, all local-filesystem-only. Zero live-network, zero real-cloud-credential tests exist (correctly — none should be attempted without real credentials, per the closure directive's own explicit instruction).

### Existing persistence primitives

`LocalFileAnchorProvider` is genuinely production-*capable* in the narrow sense the module claims (append-only via create-exclusive semantics, correctly rejecting a second publish under the same `anchor_id`) but provides no protection against an operator or attacker with filesystem access simply deleting the anchor directory — it is not tamper-*resistant* against anyone who can reach the filesystem, only against accidental/concurrent-process overwrite.

### Trust boundary

Today's trust boundary for "was this evidence chain tampered with" is: whatever signed the `AnchorRecord` (a real, keyed HMAC) plus wherever `LocalFileAnchorProvider` happens to be pointed — if that's the same disk/volume as the primary database, an attacker with full DB write access (the exact threat model Gap 5 Phase 1 was built to defend against) plausibly also has filesystem access to the anchor directory, defeating the entire point. **A real external anchor requires a genuinely separate trust domain** (a different cloud account, a different credential, ideally a different organization's infrastructure or a public timestamping authority) — this is an infrastructure/deployment decision, not something any code change alone can guarantee.

### Failure mode if left as-is

Same shape as Gap A: a working-looking capability (`publish_anchor()` succeeds, `verify_anchor_from_provider()` correctly detects tampering *when actually consulted*) that nothing in production ever calls, so it provides zero real protection today regardless of how correct its own unit tests are.

### Required production invariant

A deployment claiming external-anchor-backed audit integrity must have a real `AuditAnchorProvider` implementation whose storage is genuinely outside the primary database's trust domain, actually invoked on a real cadence, with defined behavior when the external anchor is unavailable.

### Minimal change needed (design-level)

1. Choose one real, deployable provider appropriate to this codebase's existing infrastructure choices (this audit does not choose — `compliance/PROJECT_CONTINUITY_PLAN.md` names Render + a managed Postgres as the current hosted stack; an S3-Object-Lock-capable bucket or equivalent is the most natural fit *if* the hosting decision supports it, but this is exactly the "choose based on existing WhitePact architecture" judgment call the directive defers to implementation time, not audit time).
2. A scheduled/triggered publication call site — none exists; needs a real decision on cadence and trigger (per-org periodic job? triggered on evidence-chain milestone? manual admin action, matching the consent-capture precedent of "an authenticated API call is itself the act"?).
3. An explicit policy for external-anchor unavailability (continue with degraded-state flag / queue locally / fail closed for specific assurance modes) — the directive is correct that this must be a stated decision, not a default fallen into.
4. Verification tooling — `verify_anchor_from_provider()` already exists as the primitive; an operator-facing command/endpoint to run it does not.

### Migration implications

Likely a small table to track publication cadence/last-anchored-sequence per org, if a scheduled model is chosen — not yet designed.

### Compatibility implications

None for existing deployments (purely additive, opt-in, no existing behavior touched) unless external-anchor-unavailable is ever made a fail-closed condition for some assurance mode, which would be a new, real availability dependency.

### Security risks

- The single largest risk is **choosing a provider that shares a trust/failure domain with the primary database** (e.g., an S3 bucket in the same cloud account, same credentials, same operator access) — this would satisfy the letter of "external anchor" while providing little real defense against the full-DB-compromise threat model Gap 5 was built for. This must be an explicit, named judgment call at implementation time, not glossed over.
- Publishing on a real cadence introduces a real new external dependency and its own credential-management surface — a new thing that can leak, be misconfigured, or be a denial-of-service vector if unavailability is ever wired to fail closed.

---

## Cross-cutting observations

- Gaps A and B share the same structural shape: **a real, correct Heart primitive exists and is tested in isolation, but `resolve_authority_grant()` never passes it to `sovereignty_kernel.evaluate()`.** Closing both is mechanically similar — extend the resolver's inputs, extend its callers to fetch the relevant data, no changes needed to `sovereignty_kernel.evaluate()` itself (it already accepts everything).
- Gap C is the one that most changes *behavior* for anyone already running with flags set, and is the one place a wrong design choice (Option 1 vs Option 2 above) has the widest blast radius. It should likely be decided, or at least scoped, before A/B are wired to actually deny anything — otherwise "what does `enterprise_mode=True` mean" changes twice in quick succession.
- Gap D is the most infrastructure-dependent and least code-only of the four — real progress here may be bounded by what credentials/environment are actually available to implement against, exactly as the closure directive anticipates ("if no real credentials/infrastructure are available... report live external verification as BLOCKED").
- Item 5 (independent review of PR #50) is unaffected by any of A-D and remains exactly what it has been throughout this entire effort: not something producible by continued implementation work.

---

## What this audit does not do

No code was modified. No branch beyond the audited head was created yet, per "STOP before implementation and wait for approval." No design decision named above (Gap C's Option 1 vs 2; Gap D's provider choice; Gap A's scope-matching scheme) has been made — each is surfaced as a real, named decision point for approval, not resolved unilaterally.
