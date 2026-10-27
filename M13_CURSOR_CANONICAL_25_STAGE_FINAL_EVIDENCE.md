# M13 canonical 25-stage evidence

## Baseline

PR #232 head `07be76a55913e1e201a281f3e316bd3c35929659` is the source this work continued from. The previous handoff on that line of work recorded the default journey as acceptance `BLOCKED`, stop `judgment`, 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED / 0 FAIL, with `POST /api/web/api-keys` returning 403 `IDENTITY_VERIFICATION_REQUIRED`.

This environment does not have PostgreSQL 16, CPython 3.11, or a browser qualification run of `scripts/engineering/m13_apex_customer_journey.py`. This document does not replace that receipt and does not claim a new 25-stage execution.

## What this change does to the journey

The default configuration still has no approved provider and no approved assurance level. `hmac-reference` cannot write effective `IDENTITY_VERIFIED` unless someone explicitly sets `WHITEPACT_IDENTITY_REFERENCE_CONTRACT=1` and the process is not production. The customer-journey script does not set that switch. Reusable credential issuance still calls `CredentialIssuancePolicy`, which still returns `IDENTITY_VERIFICATION_REQUIRED` when the effective status is not `IDENTITY_VERIFIED`.

Stages after judgment stay unexecuted on the canonical path:

1. Genuine human approval
2. Short-lived execution grant issuance
3. Controlled tool execution
4. Evidence-chain verification
5. Agent revocation
6. Post-revocation execution refusal
7. Post-revocation approval-execution denial

No database row, mock callback, or reference-contract event was used to mark those stages passed.

## Local contract tests versus the journey

`tests/test_m13_identity_trust_boundary.py` passed 10 cases on CPython 3.12.3 and SQLite. Those cases prove denial and state-machine behavior. They are not canonical customer acceptance. The reference contract inside them is labeled as a software fixture.

## Verdict

CANONICAL CUSTOMER JOURNEY BLOCKED.

CANONICAL CUSTOMER JOURNEY PASS is not claimed.
