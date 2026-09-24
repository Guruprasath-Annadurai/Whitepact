# Antigravity findings register (v1.3.1 hardening)

| ID | Title | Disposition | Evidence |
| --- | --- | --- | --- |
| WP-V1-FIND-001 | MCP input validation boundary | **FIXED** | `argument_validation.py` + `dispatch_tool`; `tests/test_mcp_argument_validation.py` |
| WP-V1-FIND-002 | Trust check fail-open on outage | **FIXED** | `TrustCheckResult.trust_status` / fail-closed `passes`; updated trust tests |
| WP-V1-FIND-003 | Alembic discovery depends on cwd | **FIXED** | `alembic_paths.resolve_alembic_ini`; `tests/test_alembic_ini_resolution.py` |
| WP-V1-FIND-004 | Helm product drift | **FIXED** (metadata) | `helm/rai-governance/Chart.yaml`; `helm lint` clean |
| WP-V1-FIND-005 | Container OCI version drift | **FIXED** | `Dockerfile` `ARG WHITEPACT_VERSION=1.3.1` + label |
| WP-V1-FIND-006 | Stale “27 tools” documentation | **FIXED** (current docs) | `README.md` → 30 tools; historical compliance docs unchanged |
| UX-01 | Purpose must be real intent | **FIXED** (guidance) | Hosted MCP error text + `docs/MCP_HOSTED_PURPOSE.md`; no synthetic purpose injection |
| UX-04 | FREE tier API key UX | **FIXED** | `ApiKeysPage` quota section; backend message retained |
| UX-05 | Pre-onboarding navigation | **FIXED** | `DashboardShell` redirect to `/onboarding` |
| UX-06 | Policy enum clarity | **FIXED** | `PolicyRuleCreateRequest` lists canonical effects incl. `QUARANTINE` |
| Async evidence ingestion | Performance suggestion | **REJECTED** | No fire-and-forget evidence; synchronous default preserved |
| Static vendor safe-list | Offline trust | **REJECTED** | See `TRUST_CHECK_AUTHORITY_IMPACT_ANALYSIS.md` |
