# M13 real provider integration readiness

## Architecture

The development adapter remains `HmacVerificationProvider` (`hmac-reference`). It creates a local session id and checks an HMAC. A valid signature does not mean a human completed proofing. Production policy rejects it.

`HttpCallbackIdentityProvider` (`src/responsibleai/enterprise/identity_provider_http.py`) is the provider-independent production shape:

- `from_env()` requires `WHITEPACT_IDENTITY_PROVIDER_NAME`, `WHITEPACT_IDENTITY_PROVIDER_BASE_URL`, `WHITEPACT_IDENTITY_PROVIDER_API_TOKEN`, and `WHITEPACT_IDENTITY_PROVIDER_WEBHOOK_SECRET`.
- Missing values, the name `hmac-reference`, a non-HTTPS URL, or `WHITEPACT_IDENTITY_PROVIDER_ALLOW_INSECURE=1` in production raise `PROVIDER_NOT_ENROLLED`.
- `start_session` POSTs `{subject_id, return_url}` with a bearer token and requires the provider to return `session_id` and `hosted_url`. It does not mark the subject verified.
- `verify_webhook` checks HMAC-SHA256 over `payload + timestamp` and the same 300-second window as the reference adapter. Session correlation and assurance policy still run in `VerificationService`.

No vendor credentials are committed. The default process does not select this adapter. The local test stands up an HTTP server only to prove the client binds the provider-issued session id.

## Founder decision record

This document does not enroll, purchase, or prefer a paid contract. Prices below are published or secondary summaries retrieved on 27 October 2026 (Asia/Calcutta) and can change. The security owner must confirm the live price, region, data-processing terms, and the exact assurance string the adapter will store.

| Option | What it publicly offers | Indicative cost | Sandbox | Fit for the current adapter |
| --- | --- | --- | --- | --- |
| Veriff self-serve | Hosted verification, document coverage claimed across 230+ countries, webhook-style session results | Essential $0.80 per verification with a $49 monthly minimum; Plus $1.39 / $99; Premium $1.89 / $209. Source: https://www.veriff.com/pricing | 15-day trial advertised, no card | Hosted redirect plus a signed callback matches `HttpCallbackIdentityProvider` after a thin field mapping |
| Stripe Identity | Hosted or modal document-and-selfie checks; webhooks for completion and retry | Stripe's page states $1.50 when a user completes verification and that the first 50 are free. Availability is limited by Stripe account country. Source: https://stripe.com/identity | Test mode does not perform a real check | Same session-and-webhook shape. Test mode must not be mapped to `IDENTITY_VERIFIED` |
| Persona | Inquiry workflows, hosted or embedded, webhooks | Third-party summaries say Essential from $250 per month on a 12-month term, with a sandbox trial. Confirm on Persona's own quote. | Sandbox is not production proofing | Usable, with more workflow configuration before the normalized outcome |

Recommended question for the founder, not a selection: authorize one hosted document-and-biometric vendor, name the approved provider id, and name the approved assurance token that vendor's decision will carry (for example a vendor decision name the owner accepts as the production standard). Until that pair is present in `WHITEPACT_IDENTITY_APPROVED_PROVIDERS` and `WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS`, issuance stays closed.

Privacy requirements for whichever vendor is authorized: process the minimum document and biometric data on the provider host, store only the provider reference and decision in WhitePact, keep webhook secrets outside the repository, and refuse to log raw provider bodies.

## External dependency

A real customer identity still requires the founder to enroll the vendor, supply the four configuration values, and set the two approval variables. This branch does not do that.

## Verdict

ENGINEERING IMPLEMENTED AND TESTED for the fail-closed adapter and the local HTTP session contract.

EXTERNAL PROVIDER AUTHORIZATION REQUIRED for a live vendor.
