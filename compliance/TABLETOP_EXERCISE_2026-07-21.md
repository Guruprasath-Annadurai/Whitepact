# Tabletop Exercise Report — 2026-07-21

First drill of `compliance/INCIDENT_RESPONSE_RUNBOOK.md`. Two scenarios:
one live-simulated hypothetical (Scenario A), one retrospective against a
real event that already happened this session (Scenario B). Both were run
against the actual repository code, not narrated on paper — commands
below are real, not illustrative.

Participants: solo maintainer, playing every role (matches the runbook's
own stated current reality).

---

## Scenario A — Suspected cross-tenant data exposure (simulated P2)

**Trigger (hypothetical)**: a customer at "Acme Corp" reports seeing what
looks like another customer's trust score data in a dashboard export.

### What was actually run

A live simulation against the real `OrgRepository`, `AuditRepository`,
`CostRepository`, and `TrustRepository` classes, using an in-memory
SQLite database with two real orgs, real API keys, and real activity
recorded under each — not mocked, not narrated.

```
Org A id: 6fd0c8d5-a60c-478f-b95e-bc66f09f7a6b
Org B id: 007a1c4c-ac17-444f-bbd1-ee1165a0bddd

Org A audit entries returned (scoped query): 1
Entries belonging to a DIFFERENT org found in org A's scoped query: 0

Org A total cost (scoped): $0.0075
Org B total cost (scoped): $0.018
Costs distinct and non-zero for both: True

Org A's own model history (scoped to org A): 1 entry
Org B's model queried WITH org A's scope (should be empty): 0 entries

Key revocation call succeeded: True
Authenticate with revoked key returns None (properly blocked): True

Audit chain intact: True, entries checked: 2
```

### Findings

- **Phase 2's core claim held under a real test**: multi-tenant isolation
  via `org_id` scoping is real, not aspirational, across audit logs, cost
  tracking, and trust score history. A genuine cross-tenant leak would be
  detectable this way, and a false alarm (as in this scenario) would be
  resolvable quickly — the investigation took under a minute once the
  right queries were known.
- **Key revocation containment step works exactly as documented** —
  revoke, then confirm re-authentication is blocked, both verified live.
- **Audit chain verification works** — confirmed intact on a small,
  controlled dataset. Not yet tested against an actual tampering attempt
  (that would require deliberately corrupting a row and confirming
  `verify_chain()` catches it — already covered by
  `tests/test_audit_log.py`'s `TestAuditHashChain` suite, so not
  re-derived here).
- **Bug found in the drill's own test script, not the runbook**:
  `TrustRepository.history()` doesn't accept a `days` parameter (only
  `model_name`, `provider`, `limit`, `org_id`). This was a bug in the
  simulation script, caught and fixed before the drill continued — worth
  noting because it shows the value of actually running commands instead
  of assuming an API signature from memory, exactly the discipline this
  compliance effort has tried to hold to elsewhere.

**Verdict**: Scenario A's runbook steps (Phase 1 classification, Phase 2
containment/investigation) are validated as actually executable, not just
plausible-sounding.

---

## Scenario B — Retrospective: the real `nltk` PYSEC-2026-597 finding

**Not hypothetical** — this walks the runbook against an incident that
genuinely happened earlier this session: `pip-audit` flagged a path
traversal vulnerability in `nltk`, triaged as non-exploitable given this
codebase's usage (a single hardcoded literal resource name, never
attacker-controlled input).

### Mapping what actually happened onto the runbook's phases

| Runbook phase | What actually happened | Match? |
|---|---|---|
| Detect | `pip-audit` run in CI/locally — exactly the "Dependency vulnerability" detection source already listed in the runbook's table | ✅ Matches |
| Triage / severity | Assessed as P3 ("dependency vulnerability confirmed non-exploitable in this codebase's usage") — this is literally the P3 example already written into the runbook's severity table | ✅ Matches |
| Create incident record (`rai_incident_log`) | **Did not happen.** The finding was documented via a CI comment and a CAIQ answer update, but no structured incident record was ever created. | ❌ **Gap found** |
| Contain / Eradicate | Not applicable — confirmed non-exploitable, no code fix needed, decision was to add `--ignore-vuln` with inline rationale | Runbook didn't have an explicit "not applicable, here's why" path — forced an implicit judgment call rather than a documented one |
| Notify | Not applicable — no customer impact | N/A, correctly |
| Post-incident review | Effectively done, but informally — captured in `ENTERPRISE_SECURITY.md`/CAIQ updates, not framed as a structured review | Partial match — the spirit was followed, the form wasn't |

### Findings

- **Real gap confirmed**: a real P3 event happened and the runbook's
  own Phase 1 step 3 (create an incident record) was skipped in practice.
  This is exactly the kind of gap a tabletop is supposed to catch — the
  documentation was fine, the *habit* of following it wasn't established.
- **Real gap confirmed**: the runbook had no explicit fast path for "this
  triaged as a non-issue, skip mechanically walking Phases 2–5." Without
  that, a future responder under less certainty than this retrospective
  view might either waste time forcing an inapplicable scenario through
  every phase, or skip the incident record entirely along with the
  inapplicable phases — which is what actually happened here.
- **Also found while re-verifying this scenario**: the `rai_incident_log`
  MCP tool's own `persist_instructions` field claimed a specific
  persistence endpoint (`POST /api/v1/incidents`) exists — it does not;
  grepped the full `dashboard/app.py` route table and confirmed no such
  endpoint is registered anywhere. The field also had a literal
  "POST to POST" typo. **Fixed at the source** (`src/responsibleai/mcp/tools.py`),
  not just noted — the tool now honestly says no persistence endpoint
  exists yet instead of pointing at one that 404s.

**Verdict**: this scenario found more real, concrete gaps than Scenario A
— exactly what a retrospective against a genuine past event should do,
since it's testing against something that actually happened rather than
an idealized hypothetical.

---

## Fixes applied as a direct result of this drill

1. `src/responsibleai/db/repositories.py` — no fix needed here; the bug
   was in the drill's own throwaway test script (wrong kwarg), not in
   production code. Noted for completeness since it's exactly the kind
   of assumption-checking this exercise exists to catch.
2. `src/responsibleai/mcp/tools.py` — `_handle_incident_log`'s
   `persist_instructions` field no longer claims a nonexistent
   `POST /api/v1/incidents` endpoint exists (and the "POST to POST" typo
   is gone). Now honestly states no persistence endpoint exists yet and
   points at manual tracking / the runbook instead.
3. `compliance/INCIDENT_RESPONSE_RUNBOOK.md` Phase 1 — strengthened step
   3 to make creating an incident record non-optional even for
   confirmed non-issues, citing this exact gap as the reason. Added a new
   step 5: an explicit fast path for "confirmed non-issue, skip to Phase
   6" so a future responder doesn't have to invent that judgment call
   under pressure.
4. `compliance/INCIDENT_RESPONSE_RUNBOOK.md`'s top-of-document honesty
   note — updated from "never tested" to "one drill done, still not a
   real incident," and the bottom "what this doesn't cover" section
   updated to match.

Verified after applying fixes: `mypy src/responsibleai` clean, full test
suite (1013 passed, 3 skipped) still green — the code fix didn't touch
anything the test suite already covers with an assertion, since no test
asserted the old (wrong) `persist_instructions` text.

---

## What this drill did not test

- P1 scenarios specifically (active exploitation, confirmed breach) —
  Scenario A was P2, Scenario B was P3. A P1 drill (e.g., simulating an
  actively-exploited RCE) would exercise Phase 2's "disable the affected
  feature/endpoint entirely" containment step, which neither scenario
  here required.
- Phase 5 (Notify) in any real depth — neither scenario involved actual
  customer notification, since Scenario A resolved as a false alarm and
  Scenario B had no customer impact. The notification process itself
  remains the least-tested part of this runbook.
- Multi-person coordination — not applicable at current team size, but
  worth flagging that this drill, like the runbook itself, tested a
  solo-responder path only.

## Recommended next drill

A simulated P1 (e.g., "a customer reports their API key appears to be in
use from an unrecognized IP with unusual request volume") would exercise
the parts of the runbook this one didn't: urgent containment under time
pressure, and an actual draft customer notification per Phase 5 — even if
the notification is never sent, drafting one against a fictional scenario
would test whether that process is actually followable, not just
described.
