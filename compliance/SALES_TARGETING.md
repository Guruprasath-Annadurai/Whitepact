# Sales Targeting — Who to Sell to Before SOC2, Who to Wait On

Not a document fix — a targeting fix. The compliance artifacts in this
folder (CAIQ, NIST CSF, Trust Center) unblock a real segment of buyers.
They will not unblock all of them. Chasing the wrong segment first wastes
cycles arguing about a certificate you don't have instead of closing deals
that don't require one.

Last reviewed: 2026-07-21

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
