# Stage 0 — Infrastructure readiness (disposable Cloud Agent VM)

**Recorded:** 2026-09-28 UTC  
**Executor:** Cursor Cloud Agent (`bc-2e65f4bd-5ea5-436c-abfe-405e12f7f7a9`)

## Immediately available (zero incremental cost)

| Resource | Status | Notes |
|----------|--------|--------|
| Git / GitHub API | OK | PR and CI inspection |
| Python 3.12 + dev deps | OK | `pip install -e '.[dev]'` |
| PostgreSQL (test harness) | OK | B4 enterprise DR @ `6210358` |
| Docker | OK | `sudo docker` when socket denied |
| kind `v0.26.0` | Installed | Control plane bootstrap **fails** |
| kubectl client `v1.31.0` | OK | No stable cluster |
| CPU / RAM | 4 vCPU, ~15 GiB RAM | Marginal for 3-replica soak |
| Helm | OK | Chart lint in CI |
| CI runners (GitHub) | OK | Long pytest jobs (~45 m) |

## Environment-blocked for representative enterprise staging

| Requirement | Blocker | Evidence |
|-------------|---------|----------|
| Multi-replica K8s qualification | `kubeadm wait-control-plane` | `artifacts/production/kind-bootstrap-diagnostics.json` |
| In-cluster B9 soak / per-replica metrics | No cluster | `scripts/cell_b/kind_b9_b10_qualification.sh` ready |
| Live B10 Helm rollback | No cluster | Same |
| TLS ingress / external DNS | Not authorized | **OWNER_ACTION_REQUIRED** |
| Paid cloud control plane | Not authorized | **OWNER_ACTION_REQUIRED** |
| External IdP (OIDC) staging tenant | Not configured | **OWNER_ACTION_REQUIRED** |
| Independent stranger onboarding | Separate human user | **INDEPENDENT_VALIDATION_REQUIRED** |

## Owner authorization stops (do not proceed without approval)

- Cloud account provisioning (EKS/GKE/AKS or equivalent).  
- Production-connected secrets, DNS, or registry.  
- Real payments / billing provider live mode.  
- Merging PRs #121, #124, #125 into `main` or creating integration branch.

## Reproducible next step on approved hardware

1. Machine with ≥8 GiB free RAM, working Docker, kind or managed K8s.  
2. `scripts/cell_b/kind_bootstrap_diagnostics.sh` — must reach **PASS**.  
3. `CELL_B_B9_DURATION=120 CELL_B_B9_WORKERS=8` + mandatory auth env:  
   `CELL_B_B9_API_KEY`, `CELL_B_B9_ORG_ID`, `CELL_B_B9_PEER_ORG_ID`  
4. `scripts/cell_b/kind_b9_b10_qualification.sh`
