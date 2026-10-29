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

## 10. Remaining work before Antigravity qualification

1. Founder signs in at `https://business.didit.me` (login, and MFA or CAPTCHA if Didit asks).
2. Create a separate Sandbox application named `WhitePact M13 Sandbox`. Stop if Didit requires a payment method.
3. Create `WhitePact KYC Sandbox` with only ID verification, passive liveness, 1:1 face match, and device/IP analysis.
4. Create a Sandbox V3 destination for the tunnel URL, subscribed only to `status.updated`, and store its signing secret in the environment, not in git or chat.
5. Bind that application id, workflow id, and secret to the receiver and run Didit Try Webhook. Keep the result only if the signed body matches that sandbox application, workflow, and `environment=sandbox`.

PRs #238–#243 were not merged. PR #243 stays a draft.

M13 remains open. Production remains no-go. M14 is not authorized.
