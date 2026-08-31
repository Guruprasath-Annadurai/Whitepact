# Dependency lock maintenance

`pyproject.toml` remains the source of truth for WhitePact runtime and optional
dependencies. The small `.in` files select the closure needed by each controlled
environment; `uv` generates the corresponding universal, hash-locked output.

| Input | Generated lock | Consumer |
|---|---|---|
| `requirements-build.in` | `requirements-build.lock` | package build, Twine, CycloneDX tooling |
| `requirements-ci.in` | `requirements-ci.lock` | lint, type checking, tests, provider integrations, pip-audit |
| `requirements-container.in` | `requirements-container.lock` | dashboard/MCP production image and SBOM environment |
| security tool input recorded in the lock header | `requirements-security.lock` | Bandit and pip-audit scanner executables |

Regenerate the first three locks with the exact commands recorded in their
headers. Review the dependency diff and advisory impact, then verify each output
in a clean Python 3.12 environment:

```bash
python3.12 -m venv /tmp/whitepact-lock-check
/tmp/whitepact-lock-check/bin/python -m pip install \
  --require-hashes -r requirements-ci.lock
```

Repeat for the build and container locks. Build distributions with
`python -m build --no-isolation`, audit each closure, and run
`python scripts/check_scorecard_regressions.py`. Never edit generated versions
or hashes manually. A range change in `pyproject.toml` is incomplete until every
affected lock is regenerated and validated.
