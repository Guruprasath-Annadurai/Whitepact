# Didit sandbox computer-use execution report

29 Oct 2026, 11:15 AM IST. Draft PR #243. Source SHA `891549f48d3a003846280a656a1369acad738d5d`.

Stage 17 is not closed. No production identity change was made. No purchase was made.

## 1. What was actually done

The browser was opened to `https://business.didit.me`. It stopped on the sign-in page. Google sign-in was offered and was not completed. No password, MFA code, cookie, API key, or webhook secret was entered or copied from the browser. No sandbox application, workflow, API key, or webhook destination was created in the console. Try Webhook was not clicked.

Using the existing Live API key already present in the environment, the Live destination was read and then paused. It was not deleted.

## 2. Live isolation

| Item | Evidence |
| --- | --- |
| Destination | `bad947aa-97f8-4c89-bb82-97ef10aecab3`, label `Integration webhook` |
| URL before and after | `https://readily-packing-hamburg-kissing.trycloudflare.com/api/enterprise/identity/verification/didit/sandbox` |
| Enabled before | `true` |
| Enabled after | `false` |
| Deleted | no |

The destination pointed only at this temporary tunnel, so pausing it does not stop a separate customer integration. The Live application, the Live workflow `Whitepact KYC` (`b4abf391-38ee-4b84-a326-f53578a6af73`), the Live API key, and the existing In Review session were not deleted. No further Live verification session was created.

## 3. Sandbox application and workflow

Not created. The console requires the founder to sign in. Sandbox mode and payment requirements could not be inspected.

Application ID: not issued.

Workflow ID: not issued. The Live workflow id was not reused.

## 4. Webhook URL

The quick tunnel still answers. An unsigned POST during this run returned `401` `{"error":"signature_rejected"}` from:

`https://readily-packing-hamburg-kissing.trycloudflare.com/api/enterprise/identity/verification/didit/sandbox`

The process listens on `127.0.0.1:8766` only. The enterprise console is not on that port. No new tunnel was required. No Sandbox destination was registered, because there is no Sandbox application.

## 5. Genuine Didit delivery

None. The Live destination's delivery count was 0 before it was paused, and Try Webhook was not used. There is no delivery id and no vendor HTTP receipt.

## 6. Secrets

`DIDIT_API_KEY` and `DIDIT_WEBHOOK_SECRET` are present in the process environment. Both belong to the Live application and were not copied into the sandbox receiver, git, this report, or chat. The receiver is still bound to the local placeholder application id, not to a Didit Sandbox application. No new Sandbox signing secret exists.

## 7. Billing and eligibility

No card, balance, or subscription was added. Didit still prices `Whitepact KYC` at $0.20–$0.53 (`OCR + LIVENESS + FACE_MATCH + IP_ANALYSIS`), which is not the $0.33 four-feature free bundle. One Live session remains **In Review** on the draft workflow labeled Free KYC (`ab884975-6787-4c56-90fe-7f493fdda187`). That workflow is also priced at $0.20–$0.53. This report does not include a charge amount; the session was not opened again. A Live key cannot be used as Sandbox.

## 8. Tests and production authority

Local sandbox tests from SHA `891549f48d3a003846280a656a1369acad738d5d` remain the only automated evidence. They are not a Didit Console delivery.

`router.py` `_verification` still constructs only `HmacVerificationProvider`. The sandbox handler still refuses `environment` other than `sandbox` and still does not write `IDENTITY_VERIFIED`.

## 9. Second browser check, 29 Oct 2026, 11:19 AM IST

The account is not unsigned. The Live API key still reads the Live application. What failed is a different browser.

The only Chrome this agent can control is the computer-use window on this cloud VM: Google Chrome, user-data directory `/home/ubuntu/.config/google-chrome`, window about 1820 by 1100. Both of its tabs are the Didit sign-in page (`Welcome back`, Sign in with Google). There is no control channel to a Chrome window on the founder's own computer. Attaching to that signed-in session is unsupported.

No password, cookie, or token was requested. No Sandbox application was created in that second attempt. The Live destination remains paused. Production identity code was not changed.

## 10. Replacement credentials, 29 Oct 2026, 11:49 AM IST

The founder revoked the exposed credentials and saved replacements. The new API key is a sandbox key. A read-only session decision on that key returned `environment=sandbox`. It does not see the previous Live workflow.

| Item | Result |
| --- | --- |
| Sandbox workflow | `Free KYC` `b782819d-22ae-452d-81f1-f18a75eb9236`, published, version 1 |
| Enabled feature string | `OCR + LIVENESS + FACE_MATCH + IP_ANALYSIS` |
| Liveness method | `PASSIVE` |
| AML, NFC, database validation, KYB, document AI | disabled |
| Didit price on this workflow | minimum $0.20, maximum $0.53. The name does not make it free |
| Application UUID | not returned by the workflow, session, or destination APIs |
| Sandbox destination | `d236bf07-f2c3-40a8-9120-fafac79b3eb9`, enabled, V3, URL is the tunnel, events `status.updated` and `data.updated` |
| Destination signing secret | present and loaded into the receiver process. It matches the replacement environment secret. The value is not recorded here |
| Deliveries | 0 |
| Genuine Try Webhook | not sent. No console send-test API was found, and the VM browser is still signed out |

The receiver process was restarted with the sandbox workflow id and the replacement signing secret. The application id is not set, so a signature-valid event fails closed until that UUID is known. The tunnel again returns `401` `{"error":"signature_rejected"}` for an unsigned POST. No identity document and no decision body were stored. Production identity code was not changed.

One sandbox session exists in status **Not Started** on a different draft workflow, `45bf2dc2-9f79-40ed-bd70-1e5de6c41f61`. It was not started further and was not used as the approved workflow.

## 11. Remaining work before Antigravity qualification

1. Copy the non-secret Sandbox application UUID from the Didit application switcher into `WHITEPACT_DIDIT_SANDBOX_APPLICATION_ID`. Do not send the API key or the signing secret.
2. In Didit Console, run Try Webhook for a `status.updated` scenario on destination `d236bf07-f2c3-40a8-9120-fafac79b3eb9`. Remove `data.updated` from that destination if only session-status events should be accepted.
3. Accept the delivery only when the signed body has `environment=sandbox`, workflow `b782819d-22ae-452d-81f1-f18a75eb9236`, and that application UUID. Do not start a real KYC session: this workflow is priced at $0.20–$0.53.

PRs #238–#243 were not merged. PR #243 stays a draft.

M13 remains open. Production remains no-go. M14 is not authorized.
