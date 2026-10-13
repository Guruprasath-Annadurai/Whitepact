# Cell B — Clean-room operator runbook (SELF_REHEARSED baseline)

**Qualified engineering SHA:** see `artifacts/production/launch-evidence.json`  
**Independent human sign-off:** required before enterprise production declaration.

## 1. Preconditions

- PostgreSQL reachable (`DATABASE_URL` / `WHITEPACT_DATABASE_URL`)
- `python -m responsibleai.operations.config_validate` (production overlay)
- `python -m responsibleai.operations.helm_validate helm/rai-governance/values-production.yaml`
- `python -m responsibleai.operations.operator_status` (no secrets on stdout)

## 2. Enterprise disaster recovery (B4)

```bash
python scripts/cell_b/b4_enterprise_dr_rehearsal.py
```

Artifact: `artifacts/production/b4-enterprise-dr-rehearsal.json`

## 3. Kubernetes staging (B9/B10)

```bash
bash scripts/cell_b/kind_b9_b10_qualification.sh
```

Artifacts: `b9-kind-http-load.json`, `b10-kind-helm-rollback.json`, transcript log.

## 4. Zero-to-launch (B12)

```bash
bash scripts/cell_b/b12_zero_to_launch_rehearsal.sh
```

## 5. Rollback (production cluster)

See `docs/production/B10_ROLLBACK_PROCEDURE.md` — requires owner Kubernetes access.
