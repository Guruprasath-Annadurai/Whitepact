# Launch Cell B — security-state & distributed staging remediation

## B4 security-state restoration

- **Historical DR evidence:** `artifacts/production/b4-enterprise-dr-rehearsal.json` (100k+ row restore) remains valid for the SHA recorded in that file.
- **Security-state evidence:** `artifacts/production/b4-enterprise-dr-security-state.json` — adversarial fixtures (consumed nonce, revocation epoch, denied approval, expired grant validation, cross-tenant HTTP denial) verified **after** logical restore.
- **Run:** `CELL_B_ENTERPRISE_DR=1 python3 scripts/cell_b/b4_enterprise_dr_rehearsal.py`

## B9 distributed workload (Kubernetes)

- **In-cluster load:** `scripts/cell_b/k8s_b9_load_job.yaml` + `scripts/cell_b/b9_in_cluster_load.py` target the Service (not `kubectl port-forward`).
- **Per-replica proof:** `/api/health` includes `instance_id` from `WHITEPACT_INSTANCE_ID` (pod name in kind values).
- **Orchestration:** `scripts/cell_b/kind_b9_b10_qualification.sh` (configurable `CELL_B_B9_DURATION`, `CELL_B_B9_WORKERS`).
- **Diagnostics:** `scripts/cell_b/kind_bootstrap_diagnostics.sh` → `artifacts/production/kind-bootstrap-diagnostics.json`

## B10 Helm rollback

Same script performs known-good deploy → faulty DB URL upgrade → `helm rollback` → in-cluster `readyz` check, with Helm history captured in `artifacts/production/b10-kind-helm-rollback.json`.

## Environment status (disposable VM)

When `kind` fails at `kubeadm wait-control-plane`, mark B9/B10 `ENVIRONMENT_BLOCKED` and run the qualification script on an owner-approved staging cluster with sufficient CPU/memory (≥3 replicas, in-cluster load job).
