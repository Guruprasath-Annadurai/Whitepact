# Ruff scope

Mandatory formatting and lint are `src/`, `tests/`, and `sdk/python/`.
CI runs:

```bash
ruff check src/ tests/ sdk/python/
ruff format --check src/ tests/ sdk/python/
```

Ruff 0.16 formats Python fences inside Markdown when the path is `.`.
Documentation, the wiki, and compliance notes are not Python source.
`pyproject.toml` excludes `*.md`, `docs/`, `wiki/`, and `compliance/`
so that command does not rewrite prose.

`migrations/` is historical Alembic source. Reformatting it would change
column alignment and nothing else. It is outside the mandatory gate.
`examples/` and `scripts/` were already outside that gate.

`ruff format --check src/ tests/ sdk/python/` passes on this candidate.
That does not mean `ruff format migrations/` is clean.
