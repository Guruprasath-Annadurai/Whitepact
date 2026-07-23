# Privacy Policy — DRAFT

> ## ⚠️ This is a draft, not a binding legal document
>
> This has **not been reviewed by an attorney**, and — unlike most of this
> repository's other honest self-assessments — it also has **not been
> reviewed against a real data inventory**, because no hosted instance
> exists yet to inventory (see `SLA.md`). Do not publish this as your live
> privacy policy, link it from a signup flow, or represent it as accurate
> until: (1) counsel has reviewed it for your jurisdiction (GDPR, CCPA,
> and others impose different mandatory disclosures), and (2) it has been
> re-verified against whatever a live hosted instance actually collects,
> which may differ from what's described below once one exists.
>
> **Why this document exists even though `PRIVACY.md` already exists in
> this repository**: `PRIVACY.md` documents the differential-privacy
> mathematical guarantees of the `PrivacyLabel` federated-learning module
> specifically — it is technical documentation for one feature, not a
> general-purpose privacy policy describing how the platform as a whole
> handles personal data. The two documents cover different things and both
> are needed; this one does not replace that one.

Last reviewed: 2026-07-23 · Platform version: 1.2.0

---

## 1. Who this covers

This Privacy Policy describes how Guruprasath Annadurai, operating as the
ResponsibleAI project ("Provider," "we"), handles personal data in
connection with:

- A Provider-operated hosted instance of the Service, **if and when one
  exists** — as of this version, none does (see `SLA.md`'s Scope
  section). Most of this document is currently forward-looking for that
  reason, stated plainly rather than implied.
- Provider's own project-level touchpoints that exist today regardless of
  hosting status: the public Trust Leaderboard, the public Trust Index
  verification pages, and the public AI Incident Database, all described
  further below.

**Self-hosted deployments**: when Customer runs the platform entirely on
its own infrastructure, Provider does not collect, process, or have
access to any of Customer's data. This Privacy Policy does not apply to
that data — Customer is the one making privacy commitments to its own
end users in that mode, using its own privacy policy.

---

## 2. What we collect (hosted instance, once one exists)

| Category | Examples | Purpose |
|---|---|---|
| Account/organization data | Organization name, slug, billing contact email (via Stripe) | Providing the Service, billing |
| API key metadata | Key name, role, creation/last-used timestamps, SHA-256 hash of the key itself (never the raw key) | Authentication, access control |
| Audit log metadata | Endpoint, method, status code, timing, IP address (opt-in field-encrypted, see `db/encryption.py`) | Security, tamper-evident governance logging |
| Content Customer submits | Prompts, model outputs, or text submitted to guardrail/trust-scoring/hallucination-detection endpoints | Providing the Service's core evaluation functionality |
| MFA enrollment data | TOTP secret, hashed backup codes (opt-in field-encrypted) | Multi-factor authentication, if Customer's org enables it |

**We do not require personal data to operate the platform's core
functionality.** Content Customer submits for evaluation may incidentally
contain personal data (e.g., a prompt containing a name or email address)
— that is Customer's data, submitted at Customer's discretion, not data
Provider collects independently.

---

## 3. Public features — a different privacy posture

Three features are **intentionally public by design**, and submitting to
them is different from ordinary account data:

- **AI Incident Database** (`/incident-db`): reports are reviewed by a
  moderator before publication. Reporter name and contact are opt-in
  field-encrypted and never shown publicly; published incident details
  (title, description, affected model/provider) are public and permanent
  once published, matching a CVE-style public registry model. Do not
  submit anything you don't want public.
- **Trust Leaderboard** (`/leaderboard`) and **Trust Index verification
  pages** (`/verify/{passport_id}`): trust scores and the models/providers
  they're computed against are public by design — this is the point of
  an open, independently-checkable trust standard
  (`compliance/TRUST_INDEX_SPEC.md`). No personal data is expected here
  beyond whatever a self-assessing organization chooses to attribute a
  score to.

---

## 4. How we use data

Solely to provide and improve the Service: authenticating requests,
computing trust scores and guardrail results, maintaining the audit log,
processing payment (via Stripe, for hosted paid tiers), and responding to
support requests. We do not sell personal data. We do not use Customer's
submitted content to train models Provider operates, and do not share it
with LLM providers except where Customer's own configuration explicitly
routes it there (e.g., Customer's own OpenAI/Anthropic API key used for
cost tracking).

---

## 5. Sub-processors

See `compliance/DPA_TEMPLATE.md` Section 2 for the current, detailed
sub-processor list (Render, Supabase, and Upstash for hosting, Stripe for
billing, Customer's own chosen OIDC provider for SSO, and any LLM
providers Customer configures). That document is the source of truth;
this policy incorporates it by reference rather than duplicating a list
that will drift out of sync if maintained in two places.

---

## 6. Data retention

*(Placeholder — no hosted instance exists yet to set a real retention
policy against. A reasonable default to propose to counsel: account and
audit-log data retained for the duration of the account relationship plus
a defined post-termination window for legal/audit purposes; submitted
evaluation content not retained beyond what's needed to return the
result, unless Customer's plan tier includes result history. Confirm
against actual database retention behavior once implemented, not just
this document's aspiration.)*

---

## 7. Your rights

Depending on your jurisdiction (GDPR, CCPA, and others each grant
different specific rights), you may have the right to access, correct,
delete, or export your personal data, and to object to certain
processing. To exercise these rights, contact **milchcreamfoods@gmail.com**
(the same security/privacy contact published in `SECURITY.md` and
`SLA.md`).

**Self-hosted Customers**: your organization controls this data directly
and should handle these requests using your own systems — Provider has no
access to self-hosted data and cannot fulfill a request on your behalf.

*(Placeholder — specific response timeframes, e.g. GDPR's one-month
default, should be confirmed with counsel rather than assumed.)*

---

## 8. International data transfers

Data may be processed in the sub-processor locations listed in
`compliance/DPA_TEMPLATE.md` Section 2. Where this crosses a
data-protection boundary (e.g., GDPR's international-transfer rules), the
appropriate transfer mechanism must be confirmed by counsel for the
relevant jurisdiction — not assumed from this document, matching the same
caveat `compliance/DPA_TEMPLATE.md` Section 8 already states.

---

## 9. Security

Security measures are described in `ENTERPRISE_SECURITY.md` and
self-assessed in detail in `compliance/CAIQ_SELF_ASSESSMENT.md` and
`compliance/NIST_CSF_SELF_ASSESSMENT.md`. **Stated honestly**: no SOC 2 or
ISO 27001 certification exists as of this version, and no third-party
penetration test has been performed — only an automated baseline scan
(`scripts/security-scan.sh`) and an internal review
(`compliance/INTERNAL_SECURITY_REVIEW.md`). Encryption at rest for the
whole database is infrastructure-dependent (deployer's responsibility);
specific PII/secret columns (audit log IPs, incident reporter contact
info, webhook secrets, MFA seeds) use opt-in application-layer field
encryption via `RAI_FIELD_ENCRYPTION_KEY`.

---

## 10. Children's privacy

The Service is not directed at children and is not knowingly used to
collect personal data from children. *(Placeholder — the specific age
threshold, 13 (COPPA) vs. 16 (GDPR) vs. another figure, is
jurisdiction-specific; confirm with counsel.)*

---

## 11. Changes to this policy

Material changes will be reflected by an updated "Last reviewed" date at
the top of this document. *(Placeholder — the actual notice mechanism for
existing customers should be decided before this is relied upon, same as
`TERMS_OF_SERVICE.md` Section 14.)*

---

## Before using this document

1. Have an actual attorney review it against your jurisdiction and
   whatever a real hosted instance actually collects once one exists —
   this draft was written against the codebase's current data model, not
   a live system's observed behavior.
2. Do not publish this, link it from a signup flow, or represent it as
   accurate until that review is complete.
3. Fill in Section 6 (retention) and Section 7's response timeframe with
   real, counsel-approved terms — they are intentionally incomplete here.
4. Publish this alongside, not instead of, `TERMS_OF_SERVICE.md` — a
   privacy policy without matching terms of service (and vice versa) is
   an incomplete legal foundation.
