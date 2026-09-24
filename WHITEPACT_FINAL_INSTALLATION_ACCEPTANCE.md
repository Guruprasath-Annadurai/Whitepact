# Installation acceptance

| Path | Status | Notes |
| --- | --- | --- |
| Editable `pip install -e ".[dev]"` | **PASS** | Agent VM |
| `alembic upgrade head` resolution | **PASS** | `resolve_alembic_ini` tests |
| `npm ci` + `web` build | **PASS** | lint + 57 vitest |
| Docker image build | **NOT RUN** this campaign | Dockerfile label aligned to 1.3.1 |
| Helm render | **PASS** | `helm lint` |

Fresh-engineer doc-only install from zero without repo clone: **BLOCKED** — requires published wheel + environment secrets doc pass.
