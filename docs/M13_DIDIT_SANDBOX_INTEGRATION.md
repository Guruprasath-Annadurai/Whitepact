# Didit V3 identity adapter

This integration is opt-in. It does not qualify a live provider, organization authority, real person, root authority or production deployment. Keep the existing frozen M13 candidates unchanged.

Backend configuration (inject secrets privately; never commit an actual environment file):

```text
WHITEPACT_IDENTITY_PROVIDER_ADAPTER=didit
WHITEPACT_DIDIT_ENVIRONMENT=sandbox
WHITEPACT_DIDIT_APPLICATION_ID=e31fb29a-6193-4ba7-94fc-79e2cf824b35
WHITEPACT_DIDIT_WORKFLOW_ID=b782819d-22ae-452d-81f1-f18a75eb9236
WHITEPACT_DIDIT_API_KEY=<existing sandbox application key>
WHITEPACT_DIDIT_WEBHOOK_SECRET=<existing destination signing secret>
```

Enrollment: authenticated, CSRF-protected `POST /api/enterprise/identity/verification/start`. Active membership is mandatory. The backend sends `workflow_id` and the opaque internal user UUID as `vendor_data` to `POST https://verification.didit.me/v3/session/`, using `x-api-key`. The application UUID is **not** a create-session request parameter. It authenticates application scope in signed callbacks. The returned `session_id` is the provider reference, never the internal subject ID. A durable init marker binds user, tenant, session and configuration before any callback can change authority. If local persistence fails after remote session creation, the orphan session cannot authorize identity; reconcile rather than infer success or automatically retry.

Callback: `POST /api/enterprise/identity/verification/webhook`. Use the destination's `X-Signature-V2` and `X-Timestamp`. Signature input is recursively sorted compact JSON, Unicode preserved and integral floats normalized; the whole event is authenticated. The header timestamp must equal the signed integer body timestamp and fall within 300 seconds. Application/environment/workflow/type/event UUID are checked. Simple/deprecated partial-field signatures and browser redirects never qualify identity.

The service fetches the authenticated `/v3/session/{session_id}/decision/` and compares session/workflow/vendor_data/status with the event. Approved requires successful document, liveness and face-match checks. Existing provider/assurance allowlists remain mandatory. A sandbox-only test deployment may explicitly configure `WHITEPACT_DIDIT_SANDBOX_ASSURANCE_ENABLED=1`, provider `didit-sandbox` and assurance `didit_sandbox_id_liveness_face` in the existing approved-provider/assurance variables. This is a deliberate nonproduction test policy, never enabled by default; production rejects sandbox even if those variables are set. Do not change the canonical production policy to manufacture acceptance.

Evidence hashes, provider event UUIDs and ordering markers commit in the same database transaction as identity state and audit. No raw identity documents or decision JSON are retained. PostgreSQL locks the init marker to serialize callbacks, with unique event admission and conditional state updates. Identical retries may refresh dispatch timestamp; their semantic digest excludes only that timestamp. Changed payloads under an existing event UUID, conflicting same-time events and older decisions fail closed. There is no approval or execution-nonce reset in this adapter.

Try Webhook samples are recorded separately as `TEST_RECEIPT_ONLY`; they never create a user/session binding or elevate an identity. The test header can only reduce authority. A locally signed test fixture is not evidence of a delivery from Didit.

Reconciliation: authenticated, CSRF-protected `POST /api/enterprise/identity/verification/{session_id}/reconcile` requires the original user and tenant. It retrieves the provider status read-only and requests a genuine signed event for an authoritative transition. It cannot restore a suspended identity or establish organization authority. Provider outages return sanitized 503; webhook evidence-write failure returns sanitized 503 and rolls back the transaction. No synthetic definitive persistence claim is returned.

Current deployment status: PRIVATE LOCAL IMPLEMENTATION ONLY. No permanent receiver exists and public exposure is not approved. Do not reuse the old Quick Tunnel as proof. Provider credentials/session creation, genuine delivery, production provider eligibility, retention policy and real-person verification remain separately unqualified. The proposed HTTPS deployment package is outside source, in the user-facing outputs.

Tests use local fixtures. Run the durability suite with `WHITEPACT_DIDIT_TEST_BACKEND=postgresql` and an explicitly disposable `WHITEPACT_TEST_PG_ADMIN_URL` for real PostgreSQL. `test_m13_didit_postgres.py` requires PostgreSQL and errors if unavailable; it does not skip. The new PR workflow preserves existing checks and records exact checked-out SHA/tree, JUnit, coverage and zero-skip receipts. It is not yet hosted evidence.

Official contracts: https://docs.didit.me/sessions-api/create-session and https://docs.didit.me/integration/webhooks (checked 29 October 2026).
