# WhitePact Record Retention and Deletion Procedure

**Status:** Adopted first-party operating procedure  
**Effective date:** 2026-09-13  
**Owner:** WhitePact maintainer / privacy contact

## Purpose

Turn WhitePact's published retention commitments into an auditable operating procedure while being explicit that policy/procedure alone is not proof that automated deletion is currently enforced for every category.

Canonical retention commitments remain in `PRIVACY_POLICY.md`. If this procedure and the Privacy Policy diverge, resolve the conflict before running deletion rather than silently choosing the more convenient rule.

## Principles

- Keep data only as long as necessary for the documented purpose, contractual need or legal obligation.
- Do not delete evidence subject to a legitimate legal/security hold until the hold is released.
- Do not retain customer data merely because deletion tooling is inconvenient.
- Record deletion outcomes without copying deleted content into audit evidence.
- Apply tenant isolation and least privilege during deletion/export operations.
- Backups require their own lifecycle; deleting active data does not imply immediate deletion from immutable backup media where the documented backup lifecycle differs.

## Baseline categories

Use the current `PRIVACY_POLICY.md` as the authoritative schedule. Key categories currently include:

- account/organization data;
- audit/security metadata;
- submitted evaluation content/result history where retained;
- MFA enrollment/security data;
- billing/accounting records handled partly by payment providers;
- security/privacy/support evidence;
- intentionally public registry/trust records with separately documented publication expectations.

## Scheduled review procedure

At least monthly while manual enforcement is required, and whenever an automated retention job reports failure:

1. Identify records that have reached the applicable retention threshold.
2. Check for active legal/security/contractual hold.
3. Confirm tenant/category and avoid cross-tenant bulk operations without safeguards.
4. Execute the approved deletion/anonymization mechanism.
5. Verify the operation completed and sample-check counts/state without restoring unnecessary personal data.
6. Record category, period, number/count where safe, date, operator, outcome and exceptions.
7. Investigate failures; do not mark the control successful when eligible records remain because of an unhandled error.

## Account termination / offboarding

On verified account termination:

- revoke active API keys/tokens and privileged access promptly;
- mark the account/organization for the post-termination retention period defined in policy/contract;
- identify customer-export obligations before irreversible deletion;
- after the retention period and any hold, delete/anonymize applicable Provider-controlled data;
- retain only records that have an explicit legal/security/accounting justification;
- record completion in the operating-evidence register.

## Privacy-right deletion requests

Before deletion:

- verify requester identity appropriately;
- identify applicable exceptions/retention obligations;
- search Provider-controlled in-scope systems;
- coordinate processor/subprocessor action where required;
- preserve evidence of request timing and completion without retaining the deleted material itself merely as proof.

If legal interpretation is uncertain, hold the request securely and obtain qualified advice rather than guessing.

## Backup handling

For backups:

- document the backup retention period and restoration implications;
- do not selectively rewrite immutable backups unless the architecture specifically supports it and doing so is safe;
- ensure deleted data is not intentionally reintroduced into active production through restore without reapplying post-backup deletion/tombstone logic as applicable;
- record backup/restore tests separately under `compliance/OPERATING_EVIDENCE_REGISTER.md`.

## Public records

Public AI incident/trust records may have different permanence/publication rules from private account data. Reporter contact/private fields must remain separable from public record content. Any removal/correction request involving an intentionally public record should be assessed against the published product policy and applicable law rather than automatically applying private-account retention logic.

## Automation status

WhitePact should prefer deterministic automated enforcement for categories where feasible. Until every applicable category is technically enforced, this manual procedure is the adopted compensating control.

The existence of this procedure must **not** be used to claim automated deletion exists when it does not.

## Evidence record

```text
Retention/deletion run date:
Operator:
Environment/system:
Category/categories evaluated:
Policy threshold applied:
Eligible record count (if safe):
Deleted/anonymized count (if safe):
Hold/exceptions:
Verification performed:
Failures/corrective actions:
Secure evidence location:
```

## Review triggers

Update this procedure after material privacy-policy changes, schema/data-category changes, new subprocessors, new backup design, new legal retention obligation, deletion incident or implementation of a new automated retention mechanism.
