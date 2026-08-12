# The honest, near-zero-budget path: legal entity, penetration test, SOC 2

Last reviewed: 2026-08-12 · Author: Guruprasath Annadurai

**Why this document exists**: the constraint is real — funds exist for
development and scaling, not for a $10-50K SOC 2 audit, a $5-15K
third-party penetration test, or professional incorporation fees. This
document is what's actually legitimate and buildable under that
constraint, for each of the three items, stated honestly. It does not
pretend any free/cheap substitute *is* the paid original — that would
be exactly the kind of fabricated claim this project's own rules
prohibit, and the kind of thing a real enterprise security or legal
reviewer catches immediately and now distrusts everything else you've
told them.

The short version: two of these three have a real, honest, low-cost
path today. One (a genuine independent penetration test) fundamentally
requires paying an independent third party — that's what "independent"
means — but there's a legitimate, honest interim step that isn't
nothing.

---

## 1. Legal entity — the one item with no free substitute, but a cheap real one

A contract needs a real counterparty. This is not a compliance
nice-to-have; it's what makes a signed customer agreement, an OEM deal,
or a DPA enforceable at all. Continuing as a sole proprietor (the
current assumed structure per `FOUNDER_ACTION_CHECKLIST.md` Section 8)
is itself a legal way to contract, but it means signing with personal,
unlimited liability, and a real fraction of enterprise procurement
teams simply won't sign with an individual regardless of how good the
product is.

**This repo's own test fixtures use INR-denominated amounts** (e.g.
`tests/test_approval_execution_binding.py`'s `amount_inr` argument),
which suggests an India-based founder — the guidance below assumes
that; **say so if it's wrong** and the specifics change, though the
underlying principle (a solo-founder entity is dramatically cheaper
than SOC 2/pentest, not free) holds everywhere.

**If India-based**: a One Person Company (OPC) is the structure built
specifically for a solo founder who wants limited liability without a
second shareholder (unlike a Private Limited Company, which needs two).
Filed via the MCA's SPICe+ integrated web form. Approximate real cost
if self-filed with only statutory government/stamp fees: roughly
₹6,000-15,000 depending on state (stamp duty varies by state) and
authorized capital; with a CA/CS handling the filing (recommended —
digital signature certificate, DIN, and MOA/AOA drafting are easy to
get wrong self-filed), commonly ₹15,000-30,000 all-in. Ongoing
compliance (annual ROC filing, one mandatory board meeting/year, a
statutory auditor) adds a modest recurring cost — worth pricing before
committing, since it's the real ongoing cost, not the one-time
incorporation fee. **These are 2026-era approximate ranges, not
quoted prices — verify current MCA fee schedules and a CA's quote
before committing; fee schedules and stamp duty change.**

**If US-based (or want a US entity for US customers)**: a single-member
LLC in a low-fee state (Wyoming and New Mexico are the commonly cited
cheapest, no state income tax on the LLC itself, no residency
requirement) — state filing fees in the ~$50-200 range, plus a
registered-agent service (~$50-125/yr if you don't have a physical
address in-state). Materially cheaper and faster than incorporation in
most other jurisdictions, which is exactly why it's the default
recommendation for a non-US solo founder who specifically wants a US
contracting entity for US enterprise deals — note that doesn't replace
a home-country entity if you're also operating and paying yourself
domestically; get a real accountant's read on the cross-border tax
picture before treating a US LLC as your only entity.

**Either way**: this decision gates `TERMS_OF_SERVICE.md`,
`PRIVACY_POLICY.md`, `compliance/DPA_TEMPLATE.md`, and
`compliance/OEM_LICENSING.md`, all of which currently assume sole
proprietor (`FOUNDER_ACTION_CHECKLIST.md` Section 8 already flags
this) — once an entity exists, those four documents need a real
attorney pass to update the counterparty, not just a name find-replace.

---

## 2. Penetration test — no free substitute for "independent," a real interim step

Stated plainly: nothing free is a penetration test. "Independent"
third-party testing is the entire point of the exercise — an
adversarial specialist who didn't write the code, paid specifically to
try to break it, with no incentive to be gentle. There is no honest way
to claim a self-conducted scan is equivalent, and this document will
not pretend otherwise.

**What's real, free, and a legitimate interim step**, built into this
repo today:

- **`.github/workflows/security-scan.yml`** (added alongside this
  document) — a recurring, weekly + on-push, automated Bandit (Python
  SAST — the same class of static-analysis tool a real pentest
  engagement often runs as a first pass) and `pip-audit`
  (known-vulnerability dependency scan) run, with reports uploaded as
  build artifacts. This is what makes "self-conducted security review"
  a real, dated, reproducible claim instead of a one-time manual run
  someone did once and never repeated — anyone can check the Actions
  history and see it actually ran, on schedule, for months.
- **Today's actual run** (2026-08-12, ahead of this workflow's first
  scheduled run): Bandit against `src/responsibleai/` — **1 finding**,
  medium severity/medium confidence, `B104` ("possible binding to all
  interfaces") at `mcp/server.py`'s `main_http()`, where the hosted
  HTTP server binds `0.0.0.0` by default. Reviewed and accepted, not a
  bug: a hosted server that needs to accept external connections (in a
  container, behind a load balancer) has to bind all interfaces; the
  actual access control is the Bearer-auth layer in front of it
  (`mcp/server.py`'s `_authenticate`), not the bind address. Zero
  high-severity findings.
- `pip-audit` could not complete in this session's sandboxed network
  environment (PyPI's vulnerability-feed API timed out) — this is
  exactly why the recurring CI job matters more than a one-off local
  run: `.github/workflows/dependency-review.yml` already checks every
  PR's new/changed dependencies, and the new scheduled job re-audits
  the *entire* dependency set weekly from an unrestricted CI network,
  not just PR diffs.
- **A real precedent this process already caught something**: the
  nltk `PYSEC-2026-597` fix documented in `CHANGELOG.md` came from
  exactly this kind of dependency-scanning discipline, not from a paid
  pentest — concrete evidence the free tooling has already found and
  fixed a real vulnerability, not just a claim that it theoretically
  could.
- `compliance/INTERNAL_SECURITY_REVIEW.md` and `THREAT_MODEL.md` — the
  manual, structured review work (STRIDE-based threat modeling,
  documented invariants like the ones this session's v3 authority-layer
  work added tests for) that a pentest would otherwise spend its first
  day reconstructing from scratch.

**How to honestly present this to a buyer**: "self-conducted, automated
SAST and dependency scanning, running weekly since [date], zero
high-severity findings to date — full scan history available on
request — with a contractual commitment to commission an independent
penetration test within [N] months of [funding/revenue milestone]."
That is a true, checkable claim. "We've been pentested" is not, and
must never be said.

---

## 3. SOC 2 — already has its own document

See **`compliance/SOC2_ALTERNATIVE_PATH.md`** (built earlier this
session) for the full picture: OpenSSF Scorecard (live), SBOM +
Sigstore provenance (live), branch protection (live), and the one
remaining founder action — submitting `compliance/CAIQ_SELF_ASSESSMENT.md`
to the CSA STAR Registry, Level 1, which is free to submit and free to
maintain, and is a real registry enterprise security teams check. That
document's own rule applies here too: never describe any of this as
"SOC 2 compliant" or "audited."

---

## What to tell a skeptical enterprise buyer, honestly, right now

> We're a small, security-focused team without a completed SOC 2 report
> or independent penetration test yet — here's what we do have: an
> OpenSSF Scorecard rating you can check yourself, signed SBOM/
> provenance on every release, a public threat model, a documented
> internal security review, and a weekly automated security scan with a
> clean history. We commit to [CSA STAR Level 1 listing / an
> independent pentest] once [milestone]. Here's a security addendum
> with audit rights and breach-notification terms for the contract in
> the meantime.

That is a defensible, honest position a real number of mid-market and
early-stage-friendly enterprise buyers accept, especially paired with
contractual protections (audit rights, breach SLA, and cyber liability
insurance if it becomes affordable — see
`compliance/INSURANCE_PARTNERSHIP_PITCH.md`). It will not satisfy every
buyer — some enterprise procurement teams have a hard SOC 2 requirement
with no exception process, and no amount of honest alternative
documentation changes that. Knowing which kind of buyer you're talking
to early saves everyone's time.
