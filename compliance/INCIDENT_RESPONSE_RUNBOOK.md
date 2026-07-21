# Internal Security Incident Response Runbook — ResponsibleAI

This is the internal process for responding to a security incident
affecting the ResponsibleAI platform or its infrastructure — not a
customer-facing document, and not a substitute for `SECURITY.md` (external
vulnerability disclosure intake) or `SLA.md`'s P1–P4 classification
(general uptime/availability incidents).

**Scope**: unauthorized access, data exposure, compromised credentials,
exploited vulnerabilities, malicious use of the platform's own
infrastructure, or a confirmed breach of customer data. A routine bug,
performance degradation, or feature outage with no security dimension
belongs in `SLA.md`'s incident classification instead, not here.

**Stated honestly, per this project's standing practice**: this runbook
has been through one tabletop exercise (2026-07-21 — see
`compliance/TABLETOP_EXERCISE_2026-07-21.md`) but not a real production
incident. The drill exercised a live P2 scenario (suspected cross-tenant
data exposure) against the real repository code — not just a paper
walkthrough — and a retrospective P3 scenario against an incident that
actually happened this session (the `nltk` CVE triage). Both surfaced
real, fixed gaps (see the report). Treat "one drill done" as meaningfully
better than "never tested," not as "proven" — a real incident, especially
one under time pressure with a customer on the phone, is still a
different and harder test than a controlled drill.

Last reviewed: 2026-07-21 · Platform version: 1.2.0

---

## Current reality: who does this

Solo maintainer holds every role below today — Incident Commander,
Investigator, Communicator, and Approver are all the same person. This is
stated in `compliance/NIST_CSF_SELF_ASSESSMENT.md`'s GV.RR gap and is not
papered over here either. The role names exist so the runbook scales when
a team does, not to imply a team exists now.

---

## Detection sources — where an incident is first noticed

| Source | What it catches |
|---|---|
| Prometheus alert rules (`grafana/prometheus/alert-rules.yml`) | Error rate spikes, guardrail block-rate anomalies, trust score degradation, drift alerts, webhook failure spikes |
| `GET /api/audit/verify` | Tampering with the audit log — a broken hash chain link is itself an incident, not just a data-integrity check |
| `pip-audit` CI findings (`.github/workflows/ci.yml`) | Newly disclosed vulnerabilities in dependencies |
| External vulnerability report (`SECURITY.md` inbox) | Anything a third party finds and discloses responsibly |
| Customer report | A customer notices something wrong first — treat this as at least as credible as internal detection, don't dismiss it pending "our own confirmation" before starting Phase 1 |
| Manual observation | Anything caught by chance during normal work — log it the same way as an automated detection, don't let it go undocumented because it wasn't "official" |

None of these sources auto-create an incident record today — detection
always requires a human to recognize it as one and start Phase 1 below.
There is no automated bridge from a Prometheus alert to an incident ticket
yet; that's a real gap, not hidden.

---

## Severity classification

Aligned with `SLA.md`'s P1–P4 scale so severity means the same thing
across both documents, with security-specific definitions:

| Severity | Definition | Initial response target | Examples |
|---|---|---|---|
| **P1 — Critical** | Confirmed unauthorized access to customer data, active exploitation, credential compromise with confirmed misuse | Immediate — drop other work | Database breach, leaked API keys being actively used, RCE being exploited in the wild |
| **P2 — High** | Confirmed vulnerability with a clear exploitation path but no confirmed active exploitation yet; suspected but unconfirmed data exposure | 4 hours | A disclosed CVE in a dependency with a known working exploit, unusual audit log activity suggesting possible unauthorized access |
| **P3 — Medium** | Vulnerability with no immediate exploitation path, or a security-relevant bug with limited blast radius | 1 business day | A hardening gap found during self-review (like the CSP/HSTS gap found while writing the CAIQ), a dependency vulnerability confirmed non-exploitable in this codebase's usage |
| **P4 — Low** | Theoretical or best-practice gaps with no realistic near-term risk | 3 business days | Documentation gaps, defense-in-depth suggestions with no active threat |

When in doubt, classify one level higher and downgrade after triage
(Phase 1) rather than the reverse — the cost of over-reacting to a P3 is
much lower than under-reacting to what's actually a P1.

---

## Phase 1 — Detect & Triage

1. Confirm the report/alert is real, not a false positive — but don't let
   "confirming" become an excuse to delay starting the clock. The clock
   starts at detection, not at confirmation.
2. Classify severity using the table above.
3. **Create an incident record via the `rai_incident_log` MCP tool — every
   time, even for a P3/P4 that turns out to be a non-issue.** No server-
   side persistence endpoint exists yet (tracked as a known gap; the
   tool's own `persist_instructions` field says so explicitly rather than
   pointing at a URL that 404s), so capture the returned record yourself
   — paste it into a tracked note, ticket, or file. **Caught by this
   runbook's own tabletop drill**: the real `nltk` PYSEC-2026-597 finding
   (the P3 example in the table above) was triaged and resolved without
   ever creating one of these records. Documenting the decision in a CI
   comment was good; skipping the incident record meant there's no
   queryable trail of "how many P3s have we triaged and what was the
   pattern." Don't repeat that — the step is cheap and the record is what
   makes Phase 6 possible later.
4. If P1/P2: stop other work. If P3/P4: continue but schedule this within
   the response target above — don't let it silently slip past due date.
5. **Fast path for a confirmed non-issue** (e.g., a CVE scan hit that
   turns out to be unreachable in this codebase's actual usage, like the
   `nltk` example): after step 3's record is created, it is fine to skip
   directly to Phase 6 rather than mechanically stepping through Phases
   2–5 for something that was never actually exploitable. Note the
   "no action needed, here's why" reasoning in the incident record itself
   so the decision is auditable later — don't just close it silently.

---

## Phase 2 — Contain

Goal: stop the incident from getting worse, before investigating root
cause in full. Containment first, root cause second — don't let curiosity
about "how did this happen" delay stopping active harm.

- **Compromised credentials**: revoke immediately via
  `DELETE /api/orgs/{id}/keys/{key_id}` or the equivalent OIDC-side
  revocation at the identity provider. Don't wait for investigation to
  finish before revoking — a revoked-then-reissued key costs far less
  than continued exposure.
- **Active exploitation of a known vulnerability**: if a patch exists,
  apply it immediately following the standard deploy path (`DEPLOY_RUNBOOK.md`),
  even out of the normal release cadence. If no patch exists yet, consider
  disabling the affected feature/endpoint entirely until one does —
  availability loss is preferable to continued exploitation.
- **Suspected data exposure**: identify the exact scope (which org_ids,
  which data types) using `GET /api/audit/export` and the audit hash
  chain — the multi-tenant `org_id` isolation described in
  `ENTERPRISE_SECURITY.md` means a real breach should be scopeable to
  specific tenants, not assumed to be "everyone" by default. Confirm the
  actual scope before over- or under-scoping the notification in Phase 5.
- **Malicious use of platform infrastructure**: rate-limit or block the
  offending org/key via `PlanRateLimiter` or a manual firewall rule at
  the reverse proxy, depending on where the abuse is happening.

---

## Phase 3 — Eradicate

- Identify and fix the root cause — not just the symptom. If a
  vulnerability was in a dependency, confirm the fix version and update
  `pyproject.toml`; if it was a code defect, write a regression test
  before considering it closed (per this project's own established
  practice — see the auto-migration bug fix and the plan-rate-limiter bug
  found during this session's earlier work as examples of "fix + test",
  not "fix and hope").
- Re-run `pip-audit`, the full test suite, and mypy before considering
  the fix verified — don't ship an incident fix without the same
  verification bar as any other change.
- If the incident involved a credential or secret, rotate it — don't
  just revoke the compromised one; audit whether related secrets
  (webhook HMAC keys, OIDC client secret, Stripe keys) need rotation too.

---

## Phase 4 — Recover

- Restore normal operation. If data was affected, restore from backup
  (`scripts/restore-postgres.sh`) only after confirming the vulnerability
  that caused the incident is actually fixed — restoring into a still-
  vulnerable system just repeats the incident.
- Verify recovery: `/api/health`, `/api/support/status`, and
  `GET /api/audit/verify` should all be clean before declaring the
  incident resolved.
- Confirm with affected customers (if any were identified and notified in
  Phase 5) that service is restored and the specific issue is closed.

---

## Phase 5 — Notify

**Stated honestly, matching `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`'s
disclosed caveat**: there is no committed, attorney-reviewed
breach-notification SLA yet (e.g., GDPR's 72-hour requirement to a
supervisory authority). This phase describes the internal *process* for
deciding whether and how to notify — it does not itself create a legal
commitment to a specific timeframe. Don't promise a specific hour count to
a customer or regulator based on this document alone; that commitment
needs to come from the DPA once attorney-reviewed.

1. **Determine who must be notified**: affected customers (identified in
   Phase 2's scoping), and — only if legally required and only after
   confirming with counsel — a regulatory body (e.g., a GDPR supervisory
   authority). Do not skip the legal-requirement question by assuming
   "we're small, this doesn't apply" — confirm it, even informally, don't
   guess.
2. **Draft the notification** — state plainly: what happened, what data
   was affected (be specific, not vague), what's been done to contain and
   fix it, what the customer should do (rotate their own credentials if
   relevant). Do not minimize or use passive-voice hedging ("mistakes were
   made") — this project's whole compliance posture is built on plain
   statements of fact, and an incident notification is not the moment to
   abandon that.
3. **Update the public status page** (`/status`) if the incident had
   customer-visible impact, even briefly, alongside the direct
   notification — don't rely on direct notification alone if the incident
   was visible.
4. **Timing**: notify as soon as the scope is actually known (end of
   Phase 2/early Phase 3), not after full remediation — a customer would
   rather know early with an update to follow than learn everything at
   once after the fact.

---

## Phase 6 — Post-incident review

Within a week of resolution (not "eventually"):

1. Write up what happened: timeline, root cause, what worked, what didn't.
2. **Update this runbook** if any step didn't work as written — a runbook
   that doesn't get corrected after its first real test is decoration,
   not process.
3. If the incident revealed a gap in automated detection (e.g., something
   a customer found before Prometheus alerted on it), add or tune an
   alert rule in `grafana/prometheus/alert-rules.yml` so the same class of
   incident is caught automatically next time.
4. If the incident is disclosure-worthy under `SECURITY.md`'s responsible
   disclosure practice (e.g., it affected a reporter's finding), credit
   them per that policy.

---

## What this runbook does not yet cover

- A process tested against a *real* incident — one tabletop drill is done
  (see the honesty note at the top), which is meaningfully more than
  nothing but still not the same test as a real event under real pressure.
  Consider a second drill periodically (e.g., each time a new phase or
  detection source is added) rather than treating one drill as sufficient
  forever.
- A specific, committed breach-notification timeframe — that's a DPA/legal
  question, tracked in `compliance/DPA_ATTORNEY_SCOPE_BRIEF.md`.
- Multi-person escalation paths — not applicable at current team size;
  revisit the moment a second person joins with any operational access.
- Automated bridging from detection (Prometheus alerts) to incident
  ticket creation — currently manual; a real gap worth closing before
  relying on this runbook under real production load.
