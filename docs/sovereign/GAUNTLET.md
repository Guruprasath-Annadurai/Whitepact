# Sovereign Gauntlet

The Sovereign Gauntlet is a developer-facing adversarial surface distinct from
`tests/test_whitepact_gauntlet.py` (live MCP/runtime gauntlet).

`run_sovereign_gauntlet` executes in-process checks and reports:

- `test_id`, `attack`, `expected_control`, `observation`, `PASS`/`FAIL`, duration, refs.

PASS is awarded only from observed controls (e.g. tenant isolation rejection), never self-declared.
