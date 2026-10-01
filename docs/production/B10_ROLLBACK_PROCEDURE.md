# B10 — Release and Rollback Procedure (staging / production)

**Evidence artifact:** `artifacts/production/b10-release-rollback-rehearsal.json`

## Immutable release record

Record on every deploy:

- Git `source_sha` and `tree_sha`
- Helm chart `version` / `appVersion`
- Container image digest (not tag alone)
- Alembic `version_num` after migration Job
- SBOM / reproducible-build CI run id

## Known-good deploy

```bash
python -m responsibleai.operations.helm_validate helm/rai-governance/values-production.yaml
helm upgrade --install rai helm/rai-governance/ -f helm/rai-governance/values-production.yaml \
  --set image.tag=<sha-short> --wait
kubectl rollout status deployment/rai-governance
curl -fsS https://<host>/readyz
```

## Deliberately bad release (must be blocked pre-deploy)

Production values with `authEnabled: false` **must** fail `helm_validate` before any cluster apply.

## Rollback (requires Kubernetes — not executed in Cell B zero-cost VM)

```bash
helm history rai-governance
helm rollback rai-governance <revision>
kubectl rollout status deployment/rai-governance
curl -fsS https://<host>/readyz
```

If schema migrated forward and is not reversible, use **forward-fix** or **restore from logical backup** per `BACKUP_RESTORE_RUNBOOK.md` — application-only rollback does not recover incompatible schema.
