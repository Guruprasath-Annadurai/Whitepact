# M13-I1 actual customer journey

**INCOMPLETE / BLOCKED. GLOBAL PRODUCTION NO-GO.**

Runner: `WHITEPACT_ENV=development PYTHONPATH=src:. /Users/ag/Whitepact/.venv/bin/python scripts/engineering/m13i1_customer_journey.py`. It creates a disposable PostgreSQL database with normal migrations, starts the real application over loopback HTTP and an authenticated local email webhook, and submits real requests. It does not call identity/root/consent/delegation repositories to seed success, mock authentication/provider responses, synthesize WebAuthn bytes, or execute a fixture-only action. The local email webhook receives the genuine backend-generated verification URL in memory; no external email is sent and external delivery is not qualified.

The initial command omitted `.` from `PYTHONPATH` and exited before execution with `ModuleNotFoundError: tests`. The corrected command completed the following attempt and exited **2**, not success:

| Step | Observed independent result |
| --- | --- |
| Fresh PostgreSQL | Normal Alembic upgrade to head completed; disposable DB cleaned up |
| Signup | Actual register endpoint HTTP 202; development-token response disabled |
| Email verification | Genuine generated token delivered through local provider and submitted to actual verify endpoint; HTTP 200 |
| Password login | Actual endpoint HTTP 200 and real session/CSRF cookies |
| Organization onboarding | Actual endpoint HTTP 200; no workspace repository seed |
| Owner membership | Actual session endpoint HTTP 200 confirms OWNER and organization |
| Root status and agent inventory | Actual organization-scoped GETs HTTP 200; reads confer no execution authority |
| Passkey registration challenge | Actual authenticated/CSRF-protected endpoint HTTP 200 |
| Passkey completion | **BLOCKED**: expected origin `http://localhost`; served application origin `http://localhost:52819` |
| Consent and root authority | **NOT EXECUTED / BLOCKED**; no fabricated consent, root or bootstrap completion |
| Application ownership/capability creation | **BLOCKED**: no integrated application contract |
| Agent registration/delegation/approval | **NOT EXECUTED / BLOCKED** behind genuine authority prerequisites |
| One real controlled action and evidence | **NOT EXECUTED / BLOCKED**; no fixture action accepted as customer proof |
| Authority revocation | **NOT EXECUTED / BLOCKED** |
| Session revocation as safe separate cleanup | Actual logout HTTP 200, subsequent session GET HTTP 401; not authority revocation |

`enterprise/security/router.py:_svc` constructs `IdentitySecurityService` with default RP/origin; its dataclass defaults are `localhost` / `http://localhost`. The enrollment challenge therefore differs from this real app's origin including its port. This review does not declare an exploit or bypass that control. Antigravity must supply/review the deployment-origin binding and a supported real authenticator enrollment path. A virtual/software credential inserted into SQL would not resolve this actual journey gate.

The runner always emits BLOCKED and exits 2 because it is an explicitly bounded attempt, not an implementation of the unavailable downstream journey. A future completed golden-journey runner must genuinely implement and prove all downstream steps; changing only an exit code or using seeded fixture authority is prohibited. CI preserves the nonzero gate. Full logs are retained with the standalone validation evidence, without passwords, mail URLs or verification tokens printed by the runner.
