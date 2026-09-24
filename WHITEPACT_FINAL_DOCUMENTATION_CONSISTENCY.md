# Documentation consistency (v1.3.1)

| Item | Canonical value | Action |
| --- | --- | --- |
| Application version | `1.3.1` | `pyproject.toml`, `responsibleai.__version__`, `web/package.json` |
| MCP production tools | **30** | README updated; plugins/compliance historical “27” preserved where historical |
| Alembic head | **0061** | 61 migration files — see `FINAL_HARDENING_BASELINE.md` |
| Repository URL | `Guruprasath-Annadurai/Whitepact` | Helm chart home/sources |
| Gate B / Phase7A | Off | Unchanged |
| Trust outage semantics | Fail-closed `passes` | `TRUST_CHECK_AUTHORITY_IMPACT_ANALYSIS.md` |

Historical release records (v1.2.6 provenance, SLSA) intentionally retain period-accurate versions.
