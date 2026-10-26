# M13 identity PostgreSQL and CI qualification

Baseline: `d9f80ebf06ee18cdf282987d8ed185b76a14ed82` on PR #235.

Hosted I1 run still in progress when inspected: https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40384692097 (head `d9f80ebf`). Job `inherited-policy-gates` (`121789743972`) had already failed. Job `real-customer-journey` (`121789744084`) had already failed. Job `introduced-dco` (`121789744102`) had already failed. Logs were not downloadable while the run was still in progress. The 14 Ruff errors were reproduced locally with `ruff check src/ tests/ sdk/python/` and match that job's command (`ruff==0.17.0` in `.github/workflows/m13i1-integration.yml`).

## Lint, before

14 errors, all introduced by the unused imports and assignment left after the reference-contract helper change:

- `tests/test_enterprise_branch_campaign_batch9.py`: unused `hashlib`, `hmac`, `json`, `UTC`, `datetime`, `HmacVerificationProvider`, `VerificationService` (7)
- `tests/test_enterprise_saas_layer1.py`: unused local `verification` (1)
- `tests/test_web_platform.py`: unused `hashlib`, `hmac`, `UTC`, `datetime`, `HmacVerificationProvider`, `VerificationService` (6)

After the deletions, `ruff check src/ tests/ sdk/python/` reports no errors and `ruff format --check` is clean for the edited files. No per-file exclusion and no `continue-on-error` was added.

## Security concerns

Regression tests were added and run on `d9f80ebf` before the repairs. Three failed, which confirmed the defects. One passed, which disproved that concern.

| Concern | Result on `d9f80ebf` | Repair |
| --- | --- | --- |
| `web_users.verification_status = IDENTITY_VERIFIED` with no `identity_verifications` row | Confirmed. `get_human_status()` returned `IDENTITY_VERIFIED`. | A column value alone now projects `UNVERIFIED`. Issuance stays `IDENTITY_VERIFICATION_REQUIRED`. |
| New `REVIEW_REQUIRED` session after suspension, then a valid callback | Confirmed. `start_human_verification()` succeeded and did not raise. | Start is refused with `VERIFICATION_SUSPENDED`. A callback that still targets a session created while suspended cannot write `IDENTITY_VERIFIED` (`VERIFICATION_TRANSITION_DENIED`). |
| Individual `get_org_status()` after human expiry | Confirmed. An older `ORGANIZATION_VERIFIED` row was returned. | Individual workspace status follows the current human projection. Expired or missing proof yields `UNVERIFIED`. Suspended yields `SUSPENDED`. The stored organization row is not authorization. |
| Removing an approved assurance level | Disproven as a defect. Eligibility flipped to denied immediately because policy is read on each status check. The regression remains. | No code change required. |

Concurrent duplicate callbacks were then run on PostgreSQL 16.15 (`PostgreSQL 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)`), not only SQLite. One transaction committed `IDENTITY_VERIFIED` and the other returned `PROVIDER_REPLAY`.

`HttpCallbackIdentityProvider` still speaks a local HMAC-and-JSON contract only. It is not a claim of compatibility with Persona, Stripe Identity, Veriff, or any other vendor API. Redirects are rejected so the bearer token is not forwarded. The call has a bounded timeout and runs through `asyncio.to_thread` from verification start. Provider session references are unique per provider (`uq_identity_verification_provider_session`, migration `0068`). No provider was enrolled.

The canonical journey script does not set `WHITEPACT_IDENTITY_REFERENCE_CONTRACT`. The reference-contract helper remains limited to software tests and is restored away by the autouse fixture.

## Local commands and results

PostgreSQL 16.15 was installed and started locally. CPython 3.12.3 (`/tmp/wp`) and CPython 3.11.11 (`/tmp/wp311`, uv) were used. Admin URL: `postgresql://wp:wp@127.0.0.1:5432/postgres` via `WHITEPACT_TEST_PG_ADMIN_URL`.

- CPython 3.12.3: `python -m pytest tests/test_m13_identity_trust_boundary.py -q --tb=line -o addopts=` → 15 passed, including `test_concurrent_callback_on_postgresql`.
- CPython 3.11.11: the same file plus `tests/test_sso_identity_elevation.py` → 17 passed.
- Ruff on `src/`, `tests/`, and `sdk/python/`: passed.

The unchanged customer-journey command was attempted:

`PYTHONPATH=/workspace python scripts/engineering/m13_apex_customer_journey.py --authorized-disposable-bootstrap --report /tmp/m13-journey.json`

It stopped at import with `IsolationBackendUnavailableError` because Docker is not available in this environment. The hosted job does not set `WHITEPACT_ALLOW_UNISOLATED_EXECUTION`, so that flag was not used to force a local receipt. No 25-stage browser evidence was produced here. The journey script was not modified and still has no reference-contract opt-in, so a real run remains `BLOCKED` at credential issuance until an approved provider exists.

Hosted I1 for this follow-up commit is the pull-request workflow on PR #235. The prior run above is the before-evidence for `d9f80ebf`. `introduced-dco` on that run is the existing historical DCO gate. It was not waived and history was not rewritten.

## Verdict

ENGINEERING IMPLEMENTED AND TESTED for the lint repair, the three confirmed status defects, assurance-policy invalidation, and the PostgreSQL 16 duplicate-callback case on CPython 3.11.11 and 3.12.3.

INDEPENDENT REVIEW PENDING.

EXTERNAL PROVIDER AUTHORIZATION REQUIRED.

CANONICAL CUSTOMER JOURNEY BLOCKED.

M13 remains open. Production remains no-go.
