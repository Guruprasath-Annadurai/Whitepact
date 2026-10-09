# Phase 4 — Owner go required

Staging deployment is **not authorized** by engineering.

Before any operator continues past `terraform plan`:

1. Owner writes approval against `PHASE_03_INFRASTRUCTURE_OWNER_APPROVAL.md`.
2. Owner names one full git SHA.
3. That SHA's GitHub Actions run is complete and green.
4. Antigravity has reviewed that SHA, including memory-scope attenuation and the action-pin checker.
5. Secrets exist in the staging CI environment and are not printed in logs.
6. The cost cap of 35.95 EUR/month ex VAT for mandatory staging, plus any optional items the owner listed, is still acceptable.

Absent any item, the action is to stop.

This file does not contain the phrase that the workflow treats as acknowledgement, as an instruction to type it. The workflow's expected phrase is documented in `.github/workflows/deploy-staging-manual.yml` for the owner to supply deliberately.

## Gate

BLOCKED.
