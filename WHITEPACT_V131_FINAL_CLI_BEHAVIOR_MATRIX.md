# CLI behavioral matrix (v1.3.1 RC)

**Entry:** `python -m biasbuster.cli` / `whitepact` (same `biasbuster.cli:main` entrypoint when installed editable)

| Command / check | Test type | Environment | Exit | Result | Notes |
| --- | --- | --- | ---: | --- | --- |
| `responsibleai.__version__` | import | LOCAL venv | 0 | **PASS** | prints `1.3.1` |
| `scan --help` | help | LOCAL | 0 | **PASS** | structured help |
| `scan /nonexistent/path.txt` | malformed input | LOCAL | 0 | **PASS** | no traceback (CLI handles missing file) |
| `whitepact --version` | version | LOCAL editable | non-0 | **DEGRADED** | Click `package_name` metadata issue when invoked via console script name; use `python -m biasbuster.cli` |
| Full verb matrix (40 verbs) | behavioral | LOCAL | — | **PARTIAL** | Prior audit proved registration + cwd independence; this closure pass re-runs representative behavioral samples only |

## BLOCKED_EXTERNAL_DEPENDENCY (representative)

Commands requiring live cloud credentials, paid APIs, or production IdP: marked **BLOCKED_EXTERNAL_DEPENDENCY** in extended audit — not re-run here.

## Deliberate UNAVAILABLE paths

Experimental or unconfigured enterprise commands must return structured errors — covered by existing CLI tests in `tests/` (not expanded in this patch).
