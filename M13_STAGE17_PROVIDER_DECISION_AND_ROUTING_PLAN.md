# Stage 17 provider decision and routing plan

Prepared 29 Oct 2026. Didit successor added the same day after the documentation-stage review of PR #242. No provider account was opened, no live document was submitted, and no charge was made. This plan does not change production authority. Draft PRs #238, #239, #240, and #241 were not modified.

Stage 17 is not passed. The canonical 25-stage journey is not passed.

## 1. Provider comparison

List prices and coverage below are what the vendors published on the cited pages when this note was written. They are not a quote for the founder's legal entity. A dashboard price can differ by country, volume, and contract. None of these marketing claims is, by itself, NIST IAL2 or eIDAS Substantial/High evidence.

| Question | Veriff | Persona | Sumsub | Stripe Identity | Didit |
| --- | --- | --- | --- | --- | --- |
| Official pages read | [Pricing](https://www.veriff.com/pricing), [countries](https://www.veriff.com/supported-countries), [webhooks](https://devdocs.veriff.com/docs/webhooks-guide) | [Pricing](https://withpersona.com/pricing), [IAL2 help](https://help.withpersona.com/articles/QC1OAt4zLihlELoVNJ5jmK/), [webhooks](https://docs.withpersona.com/webhooks-best-practices) | [Pricing](https://sumsub.com/pricing/), [FAQ](https://docs.sumsub.com/page/faq), [webhooks](https://docs.sumsub.com/docs/webhook-manager) | [Use cases](https://docs.stripe.com/identity/use-cases), [checks](https://docs.stripe.com/identity/verification-checks), [pricing](https://stripe.com/pricing), [webhooks](https://docs.stripe.com/webhooks) | [Free plan](https://help.didit.me/getting-started/free-plan) (help center, updated 19 Aug 2026), [credits](https://help.didit.me/billing-credits/how-pricing-and-credits-work), [pricing](https://didit.me/pricing.md), [account](https://help.didit.me/getting-started/create-your-account), [documents](https://help.didit.me/documents-coverage/supported-documents-and-countries) (15 Sep 2026), [webhooks](https://docs.didit.me/integration/webhooks) |
| Published price | Essential $0.80, Plus $1.39, Premium $1.89 per verification. Monthly minimums $49, $99, and $209. Enterprise is custom. | Essential from $250 per month, 12-month minimum. Higher plans are volume-priced. Startup program is an application, not an automatic grant. | Basic $1.35 with $149 monthly minimum. Compliance $1.85 with $299 monthly minimum. Charged for successful verifications. Custom above about 1,000 per month. | Listed $1.50 per completed ID-document and selfie verification. $0.50 per ID-number lookup, and that lookup is described as US SSN only. | Help center: 500 completed checks per month, per feature, for exactly four features — ID verification, passive liveness, 1:1 face match, and device/IP analysis — only when those features run inside a workflow. Unused checks do not roll over. After 500, the published workflow rates are $0.15, $0.10, $0.05, and $0.03, summing to $0.33 for all four. No card, contract, or monthly minimum on the free plan. Prepaid credits, not a post-paid invoice. Marketing pages that say "500 full KYC forever" are the same four-feature allowance, not a larger pool and not a fifth feature. |
| Trial | Self-serve page says 15 days, no credit card, Premium features during the trial. | Not a public free trial on the pricing page. Evaluation is by contacting Persona. | 14 days and 50 checks. | A Stripe test-mode integration exists. The pricing page read here did not state a standing free live quota. | Ongoing free allowance above, not a calendar trial. Standalone API calls are billed even for the four free features. AML, NFC, active liveness, proof of address, database validation (India UIDAI Aadhaar listed at $0.25), KYB (India tiers from $2), and every other module bill from the first completed check. |
| Documents and geography | Marketing: 230+ countries and territories, 12,500+ document specimens, passports, national IDs, driving licences, residence permits. | Government ID for 200+ countries and territories, plus selfie, database, and NFC checks. | FAQ: documents from 220+ countries and territories and 14,000+ types. The customer chooses which documents a level accepts. | Document checks for a published country list of government IDs, described as 120+ countries. Field extraction does not support Arabic, Chinese, Cyrillic, Greek, Hebrew, Korean, Tamil, or Thai script. | Help center: customer documents from 220+ countries. The India solutions page markets Aadhaar, PAN, and Voter ID as documents a customer can present. That is end-user document coverage. It is not a statement that an India-incorporated business may open an account. |
| Business eligibility | Not stated as a closed country list on the pages read. A self-serve account still requires Veriff to accept the business. | Not stated as a closed country list. Public-sector and Kantara material is separate from a commercial KYC contract. | Not stated as a closed country list. Credit card is the published payment method for the listed plans. | Generally available only for businesses in Japan, the United Kingdom, and the United States. Self-serve public beta adds a published list that includes much of the EEA, Switzerland, Australia, Canada, and New Zealand. Industry restrictions also apply. | The public signup page does not list an India exclusion. It also does not state that an India-incorporated legal entity is contractually accepted. The India marketing page is about verifying Indian end-user documents, not about onboarding an Indian business. India data residency is described as Enterprise. Eligibility of the founder's entity remains unknown. |
| Webhook | Decision webhook is required for document and selfie IDV. `X-HMAC-SIGNATURE` over the raw body with a shared secret. | `Persona-Signature` is `t=<unix>,v1=<hmac>` over `timestamp.body`, SHA-256. Multiple secrets can be present during rotation. Events can arrive out of order. | `x-payload-digest` plus `X-Payload-Digest-Alg`. Default for a new webhook is `HMAC_SHA256_HEX`. SHA-512 is available. Older webhooks can still be SHA-1 until edited. Secret verification is optional in their dashboard and must be required by us. | `Stripe-Signature` over the raw body and the endpoint secret. Replay protection is part of Stripe's documented signature scheme. | Prefer `X-Signature-V2`, HMAC-SHA256 over a canonical JSON form of the body. `X-Signature` is HMAC over the raw bytes. `X-Signature-Simple` is deprecated and does not authenticate the decision body. It must not be the acceptance path. The payload includes `workflow_id` plus vendor strings `assurance` (`documentary`, `data_match`, `cryptographic`) and `level_of_assurance` (example value `substantial`). |
| Assurance claim that is actually relevant | UK DIATF is a named product in the webhook guide. The pricing page does not say a default Essential decision is NIST IAL2 or eIDAS High. | Kantara approval for IAL2 proofing, assessed under NIST SP 800-63A revision 3, identity proofing only. Persona says its IAL2 templates are not fully compliant out of the box and the customer remains responsible. eIDAS is named as a separate regional standard, not as something the template automatically meets. | The pages read describe ID, liveness, face match, and optional AML. They do not claim NIST IAL2 or eIDAS Substantial/High for the Basic plan. | Document, selfie, and data checks for fraud and KYC support. The pages read do not claim NIST IAL2 or eIDAS. | Didit does not, on the pages read, offer a contract or a configuration certificate that a named workflow meets NIST IAL2 or eIDAS Substantial/High. SOC 2, ISO 27001, iBeta Level 1, and a Spain government attestation are general security or biometric-test claims. They are not NIST IAL2. The payload fields `assurance` and `level_of_assurance` are vendor strings. They are not WhitePact's assurance decision. |

Ordinary login, email OTP, and a vendor "verified" badge are not IAL2. IAL2, in NIST SP 800-63A, is remote or in-person proofing that binds a person to evidence at that level. eIDAS Substantial and High are EU assurance levels for electronic identification. A document-and-selfie product can be configured toward those levels. Buying the cheapest plan does not establish that it has been.

## 2. Business eligibility unknowns

These are blocking, and they are not assumed:

- The founder's legal entity, its country of incorporation, and the countries where customers will be proofed.
- Whether that entity is in a prohibited industry for the chosen vendor.
- Whether Stripe Identity's business-location rule excludes the entity. If the entity is outside the generally available and public-beta lists, Stripe Identity is not an eligible candidate until Stripe says otherwise.
- Whether Didit will contract with an India-incorporated entity. Public signup does not forbid it and does not confirm it. India data residency, if required, is an Enterprise term and is outside the free plan.
- Which customer documents must work on day one, including non-Latin scripts Stripe says it does not extract.
- Whether the required assurance is fraud-screening document checks, NIST IAL2, eIDAS Substantial, or eIDAS High.
- Data-processing role, retention, subprocessors, and whether EU or India data residency is required. Persona lists EU hosting as a higher-plan option. Didit describes India data residency as Enterprise. The others need a data-processing addendum before production.
- Who may sign the vendor contract and who may hold the API secret.
- Sanctions and age rules for the customer population.

Until those are answered, no vendor is selected.

## 3. Existing routing defect

`src/responsibleai/enterprise/router.py` function `_verification` always does this:

```python
secret = identity_webhook_secret_from_env()
return VerificationService(get_enterprise_engine(), HmacVerificationProvider(secret))
```

It never reads `WHITEPACT_IDENTITY_APPROVED_PROVIDERS`, `WHITEPACT_IDENTITY_PROVIDER_NAME`, or `HttpCallbackIdentityProvider.from_env`. The same hard-wiring appears in `EnterpriseIAM.create_api_key`, `service.py` around the other `HmacVerificationProvider` constructions, and the webhook secret helper path.

`HmacVerificationProvider.name` is `hmac-reference`. `identity_assurance_accepted` rejects that name in production and rejects it in development unless `WHITEPACT_IDENTITY_REFERENCE_CONTRACT=1`. So a live Veriff, Persona, Sumsub, or Stripe webhook cannot become `IDENTITY_VERIFIED` through this constructor: the signature check is the reference HMAC, not the vendor signature, and the stored provider name would be the reference name.

That is a fail-closed gap, not a production identity proof. It is also the wrong place to "just set the reference switch". The reference switch is a development contract. It must not be treated as a commercial provider.

`HttpCallbackIdentityProvider` already refuses `hmac-reference` and refuses insecure production URLs. It is a generic HTTP client. It is not a Veriff, Persona, Sumsub, or Stripe signature adapter, and it must not be relabelled as one.

## 4. Proposed fail-closed implementation

Do not apply this until the founder names a provider and the CTO accepts the contract.

Selection, in order:

1. If the process is production, ignore `hmac-reference` and ignore `WHITEPACT_IDENTITY_REFERENCE_CONTRACT`.
2. If the approved-provider set is empty, refuse session start and webhook intake with the existing not-enrolled error. Do not construct a provider.
3. If the only approved provider is `hmac-reference`, allow `HmacVerificationProvider` only outside production and only when the reference switch is on.
4. If the approved set contains exactly one commercial name, construct that vendor's adapter. The adapter's `name` must equal that approved name. An unknown name, or two commercial names, refuses.
5. The vendor adapter verifies the raw body with that vendor's header and algorithm, checks the timestamp window, and returns one canonical event: `event_id`, `subject_id` equal to the pending WhitePact session, vendor session id, decision, the vendor `workflow_id` (or the equivalent policy id), and the feature results WhitePact will judge. For Didit the signature must be `X-Signature-V2` over the documented canonical body. `X-Signature-Simple` is never sufficient, including when the other headers are absent.
6. Assurance is accepted only when all of the following hold. A vendor string such as `level_of_assurance=substantial`, `assurance=cryptographic`, `GREEN`, or `verified` does not satisfy any of them.
   - The provider name is the one approved name.
   - The workflow or policy id in the signed body equals the exact id in `WHITEPACT_IDENTITY_APPROVED_WORKFLOW_ID` for that provider. A different workflow on the same account is a rejection.
   - The signature covers the decision body, not a reduced summary.
   - WhitePact's own policy map, pinned to that workflow id, accepts the feature results. The map is WhitePact configuration. It is not a copy of the vendor's assurance field.
7. Existing `VerificationService` rules stay: pending session required, approved provider and level required, replay key on the provider event, expiry, suspension, and no elevation from a column write alone.
8. A vendor "approved" or `GREEN` or `verified` status maps to `IDENTITY_VERIFIED` only when step 6 accepted the workflow and the policy map. Otherwise the outcome is `REVIEW_REQUIRED` or `REJECTED` and credential issuance stays closed. The stored assurance value is the WhitePact level named for that workflow, never the vendor's adjective.

Files that would change after approval, and not before:

- `src/responsibleai/enterprise/router.py` — `_verification` only.
- `src/responsibleai/enterprise/service.py` — the three `HmacVerificationProvider` call sites, to call the same selector.
- `src/responsibleai/enterprise/identity_providers/` — one new module per approved vendor. No module in this plan.
- `tests/test_m13_identity_provider_selection.py` — new tests listed below.

The selector must not add `hmac-reference` to the production allowlist and must not mark a user verified in the adapter.

Proposed negative tests, to be added with the selector, not before:

- Production plus `WHITEPACT_IDENTITY_PROVIDER_NAME=veriff` and a valid reference HMAC still does not verify.
- An approved name with no registered adapter returns not-enrolled and writes no `IDENTITY_VERIFIED` row.
- A vendor payload whose signature is valid but whose session id does not match the pending row is rejected and the row stays pending.
- A payload signed with `X-Signature-Simple` only, or signed for a workflow id other than the approved id, is rejected even if `level_of_assurance` is `substantial`.
- A replay of an accepted `event_id` does not create a second verification.
- Two approved commercial names fail closed.

### Zero-spend controls, if Didit is later named

These are configuration requirements for a future adapter. They are not enabled now, and no Didit workspace is to be created from this plan.

- No payment method and no prepaid credit balance on the workspace. Didit's own rule is that free allowances apply while the balance is not negative, so a credit balance is what turns the next check into spend.
- The approved workflow contains only the four free features. AML, NFC, active liveness, proof of address, database validation, and KYB are forbidden nodes. A webhook that shows one of those nodes ran is not success.
- Standalone feature APIs are forbidden. Didit bills those calls even for the four features that are free inside a workflow.
- A local counter stops new session creation at 500 completed checks per feature in the calendar month. The adapter does not rely on Didit to refuse the 501st call. Past the quota, session start fails closed.
- A paid-module price appearing on a decision is a rejection, not a verification.

## 5. Privacy and assurance requirements

- The webhook endpoint stores the vendor event id, decision, and assurance level. It does not need the document image in the WhitePact database. Prefer vendor-hosted images and a short retention setting in the vendor account.
- Sign a data-processing agreement before any real end-user document is sent.
- Biometric consent must be explicit where the customer's law requires a non-biometric alternative. Stripe's own go-live notes say this for some jurisdictions.
- Assurance configuration is an allowlist of WhitePact levels bound to one provider and one workflow id, not a vendor adjective. Suggested values to choose from, not to enable now: `document-selfie-vendor`, `nist-ial2`, `eidas-substantial`, `eidas-high`. Only the value the founder and CTO name may be stored, and only for the approved workflow.
- Didit cannot currently supply contractual, configuration-specific evidence that a named workflow meets NIST IAL2 or eIDAS. SOC 2, ISO 27001, iBeta, and government marketing do not fill that gap. If the required level is NIST IAL2 or eIDAS, Didit stays in the fraud-screening column until Didit issues that evidence for the exact workflow.
- Kantara or UK DIATF evidence, if it is the requirement, must be the vendor's current certificate for the exact flow we enable, not a blog post.

## 6. Minimum real-provider acceptance test

After approval, in the vendor's test or sandbox environment, with no production WhitePact traffic:

1. Create one pending WhitePact session for a disposable test user.
2. Complete the vendor's sandbox flow with the vendor's synthetic document, not a real passport or national ID.
3. Deliver the signed sandbox webhook once. The stored provider name equals the approved vendor, the assurance level equals the approved level, and the status becomes `IDENTITY_VERIFIED` only for that session.
4. Replay the same webhook. No second row and no second issuance.
5. Send a webhook with a bad signature, a stale timestamp, a different subject, and an unapproved assurance string. Each leaves the user unverified.
6. Attempt credential issuance before the webhook and after a rejected webhook. Both fail with the existing identity gate.
7. Confirm production configuration still rejects `hmac-reference`.

Sandbox success is not Stage 17 closure. Closure still needs the founder-approved entity, the signed contract, and a recorded assurance decision.

## 7. Recommendation ranking

This ranks the five vendors for a later founder choice. It does not select one and it does not authorize an account.

Ranked on zero recurring cost, then long-term sustainability, then legitimate assurance, then integration security:

1. **Didit, only as a zero-spend fraud-screening candidate.** It is the only vendor here with a published ongoing free allowance and no monthly minimum, and only for the four workflow features under the controls in section 4. Sustainability is the weak point: the allowance is use-it-or-lose-it, standalone calls and every other module bill immediately, and a credit balance enables spend. Legitimate NIST IAL2 or eIDAS evidence for a named workflow was not found. Integration security is acceptable only on `X-Signature-V2` plus an exact `workflow_id` allowlist. India business eligibility is unconfirmed.
2. **Persona, if the requirement is published IAL2 and the minimum is approved.** Kantara IAL2 proofing under NIST SP 800-63A revision 3 is the strongest assurance statement in this set, and Persona still says the customer must finish the template. Cost is from $250 per month on a 12-month minimum, so it fails zero recurring cost. Webhook signatures are documented and rotatable.
3. **Veriff, if a named UK DIATF product is the requirement.** DIATF is a named product, not the default Essential plan. Recurring minimums start at $49. `X-HMAC-SIGNATURE` is a clear raw-body check. No NIST IAL2 claim was found for Essential.
4. **Stripe Identity, if the business location is inside the published GA or public-beta list.** Signatures and replay protection are the clearest of the set. There is no IAL2 claim and no standing free live quota on the pages read. The business-location gate can remove it before price matters.
5. **Sumsub.** A 14-day, 50-check trial, then a $149 minimum. No IAL2 or eIDAS claim was found for Basic. Signature verification is optional in their dashboard unless WhitePact requires it, which is a weaker default than the others.

No row above is an activation. The founder still names the legal entity, the customer countries, the assurance level, and one vendor. The CTO still accepts the contract before any adapter is written.

## 8. Founder decisions required

1. Legal entity and country.
2. Customer countries and the document types that must work.
3. Required assurance level: vendor document-and-selfie, NIST IAL2, eIDAS Substantial, or eIDAS High.
4. One provider to take to contract. This plan does not choose one.
5. Approval to pay that vendor's minimum and per-check price, or, for Didit, written acceptance of the zero-spend controls and of the fact that the free plan is not NIST IAL2.
6. Approval of the data-processing terms and retention period.
7. The DCO choice in section 9, if hosted DCO must go green before Stage 17.

## 9. DCO decision for `39619c4b`

Commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` is `docs(security): publish WhitePact M13-S4 enterprise security qualification and Codex handoff suite`, authored by Techezz Infos `<Techezzinfos@gmail.com>` at 15 Oct 2026, 6:41 PM IST. The message has no `Signed-off-by` trailer. The hosted I1 DCO job fails on that commit. A later commit with a trailer does not repair it, because the check walks every commit in the range.

Choices, none of which is done here:

- The author adds a `Signed-off-by` trailer for that commit. That rewrites history and needs the author's and the repository owner's agreement. It is not done from this agent.
- Replace the range with a new history in which that commit's tree is reused under a properly signed commit. That is also a history rewrite and needs the same agreement.
- The founder records an explicit, narrow exception for this one SHA in the DCO workflow. That is an owner policy change. It is not a silent skip, and it is not implemented in this change.
- Leave the job red until one of the above happens.

No exception was added and no commit was rewritten.

## 10. Verification of this note

This change is a document. It does not alter `router.py`, the assurance allowlist, or Stage 19. Reviewers can confirm the defect by reading `_verification` and the `HmacVerificationProvider` constructor call sites named above.

M13 remains open. Production remains no-go. M14 is not authorized.
