# Sales Targeting — Who to Sell to Before SOC2, Who to Wait On

Not a document fix — a targeting fix. The compliance artifacts in this
folder (CAIQ, NIST CSF, Trust Center) unblock a real segment of buyers.
They will not unblock all of them. Chasing the wrong segment first wastes
cycles arguing about a certificate you don't have instead of closing deals
that don't require one.

Last reviewed: 2026-07-23

---

## The honest segmentation

| Segment | Typical requirement | Sell now? |
|---|---|---|
| Seed/Series A startups | Usually none, or a filled-out security questionnaire (CAIQ satisfies this) | **Yes — target first** |
| Series B/C startups, mid-market SaaS | CAIQ or a vendor security review; SOC2 often "nice to have," rarely a hard blocker pre-contract | **Yes** |
| Digital-native mid-size companies (non-regulated industry) | Vendor security review, sometimes SOC2 "in progress" acceptable | **Yes, with the roadmap framing** |
| Regulated industries (healthcare, finance, insurance) — any size | SOC2 Type II and/or HIPAA/PCI attestations, usually a hard gate | **No — don't spend cycles here yet** |
| Fortune 500 / large enterprise | SOC2 Type II mandatory, often ISO 27001 too, formal vendor risk management process | **No — don't spend cycles here yet** |
| Public sector / government | FedRAMP or equivalent, far beyond SOC2 | **No — not a near-term target at all** |

**The mistake to avoid:** treating "enterprise-grade" as synonymous with
"sell to enterprises." The product can be built to enterprise engineering
standards (RBAC, SSO, audit integrity, multi-tenancy — all already true
here) without yet being *sellable* to enterprises that gate procurement on
a certificate. Those are two different claims. Conflating them is how a
solo founder spends six months in security-review purgatory with a
Fortune 500 prospect who was never going to sign without SOC2 regardless
of how good the actual product is.

---

## The hosting provider decision changes the pitch, not just the infra

**Updated 2026-07-23**: there is now a genuinely **live** hosted instance
at `https://responsibleai-dashboard.onrender.com` — not a plan, an actual
running deployment. It's not a single-VM architecture; it's three
managed vendors: **Render** (compute), **Supabase** (Postgres), **Upstash**
(Redis). Both Oracle Cloud's and Google Cloud's signup flows required a
payment card the founder didn't have — these three vendors' free tiers
don't. This changes the pitch from the prior OCI/GCP-based analysis, kept
honest rather than silently edited:

- **Render and Supabase both have real, strong, independently verifiable
  certifications you can cite** — Render is SOC 2 Type II compliant and
  ISO 27001 certified; Supabase is SOC 2 Type II, ISO 27001, HIPAA, and
  PCI DSS certified (see `compliance/VENDOR_RISK_ASSESSMENT.md` for
  sources). When a mid-market prospect's vendor review asks "is your
  infrastructure provider certified," the honest answer is yes, cited for
  two of the three vendors — even though *this platform* isn't certified
  yet.
- **Upstash's certification status is not independently verified** —
  stated honestly rather than glossed over. If a prospect's review digs
  into sub-processor certifications specifically, this is the one gap to
  flag proactively rather than let them discover.
- **This is now a genuinely multi-vendor infrastructure story, not a
  single-provider one.** A prospect's vendor-risk review may ask about
  each of three sub-processors separately (Render, Supabase, Upstash)
  rather than one — more surface area to disclose, but also three
  separate SOC 2/ISO 27001 answers to point to for two of them.
- **No dated credit-expiry clock** (unlike the GCP plan this replaced) —
  Render, Supabase, and Upstash's free tiers don't have a known fixed
  expiration the way GCP's $300/90-day credit did. This removes a real
  operational deadline that would have needed tracking.
- **Real capacity limits still apply and should still be disclosed
  honestly**: Render's free tier has no persistent local disk and shared
  CPU; Supabase and Upstash both have standard free-tier resource caps.
  Don't pitch multi-region redundancy or high-concurrency guarantees on
  this infrastructure yet (see `DEPLOY_RUNBOOK.md`'s live-architecture
  note and `SLA.md`'s capacity section).
- **The "target smaller first" segmentation from the table above is
  unchanged** — the certificate gap (this platform's own SOC2/pentest
  status) still says don't chase Fortune 500/regulated industries yet,
  independent of which infrastructure vendors are underneath.

---

## Where the CAIQ/Trust Center actually move the needle

- **Series A-C startups and mid-market SaaS companies** run informal or
  semi-formal vendor security reviews. A filled-out CAIQ often *is* their
  entire bar, because their own security team is small and reuses the same
  standardized questionnaire across all vendors. This is the single
  highest-leverage use of the CAIQ document — hand it over proactively in
  the sales conversation, don't wait to be asked.
- **The Trust Center page** does the pre-qualification work for you: a
  security-conscious buyer checks it before they even talk to you, and
  self-selects in or out. Link it from the pricing page, the README, and
  the first email in any outbound sequence.
- **"SOC2 in progress" is a real, usable claim once true** — but only once
  actually true (auditor engaged, timeline set). Do not say it before it's
  real; a prospect who asks "what stage" and gets a non-answer trusts you
  less than if you'd said "not started."

---

## Where they don't move the needle — don't waste the pitch

- A Fortune 500 security team asking for SOC2 Type II will not accept a
  CAIQ as a substitute, no matter how thorough. Don't spend a sales cycle
  trying to convince them otherwise — that's a "closed until certified"
  door, not a "convince them" door.
- Healthcare (HIPAA) and financial services (SOC2 + often additional
  frameworks) buyers have compliance requirements this platform doesn't
  yet meet regardless of documentation quality (see `ENTERPRISE_SECURITY.md`'s
  stated gaps — no field-level encryption, no formal BAA process). Don't
  pursue these verticals until those gaps are actually closed.
- Government/public sector is off the table entirely at this stage —
  FedRAMP is a different order of magnitude from SOC2, not a next step
  from it.

---

## Practical playbook for the next 90 days

1. **Lead with the Trust Center link in every outbound message to a
   security-conscious buyer** — don't wait for them to ask. Proactive
   transparency reads as more credible than reactive disclosure.
2. **Attach the CAIQ document the moment a security review is mentioned**,
   before they send their own questionnaire. Answering their form from
   scratch costs a week; handing over a document that already answers 90%
   of it costs nothing.
3. **Qualify out regulated/enterprise prospects early in the sales
   conversation**, not after a month of back-and-forth. A direct "we're
   not SOC2 certified yet — here's our roadmap and current posture" in the
   first call saves both sides time if it's a hard blocker for them.
4. **Track how often the CAIQ actually closes a deal vs. how often SOC2
   comes up as a hard blocker.** That data point tells you when it's
   actually time to spend real money on the certificate — don't guess,
   measure it against real sales conversations once there are some to
   measure.
5. **Cite Render's and Supabase's SOC 2/ISO 27001 certifications
   proactively when infrastructure comes up**, disclose Upstash's
   unverified certification status honestly if asked, and be upfront
   about the current instance's real capacity ceiling (shared CPU, no
   persistent local disk on Render's free tier) if a prospect asks about
   scale or redundancy — before they find out under load, not after.
