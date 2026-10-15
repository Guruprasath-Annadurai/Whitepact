# M13-P4 MCP regression results

GLOBAL PRODUCTION NO-GO. Local TCP uses disposable SQLite authority fixtures supplied by the repository, not customer bootstrap qualification.

All commands use `/Users/ag/Whitepact/.venv/bin/python`, `PYTHONPATH=src`, and `-o addopts='' --tb=short -q`. Local loopback tests require execution outside sandbox socket restrictions. Logs contain test-only generated fixture identifiers; no live credentials are used.

| Candidate / command selection | Result |
| --- | --- |
| Product baseline, the two named failing node IDs selected alone | 2 passed in 38.84s |
| Exact security baseline, full `tests/test_mcp_wave1_compatibility.py` | 5 passed in 28.09s; intermittent defect not triggered |
| Product baseline, same full file | 2 failed, 3 passed in 29.02s; incomplete HTTP responses |
| Exact security baseline, full file with observer printing only SSE shutdown state | 2 failed, 3 passed in 29.16s; global flag true after first TCP fixture |
| Before fix, `tests/test_m13p4_mcp_lifecycle.py` with prior shutdown forced | 2 failed in 12.65s; deterministic original symptom |
| After fixture-only fix, original full file plus lifecycle regression | 7 passed in 19.84s |
| Ruff check and format check for both changed test files | PASS |
| After correction, same original/new files plus HTTP transport, protocol matrix and modernization suites | 42 passed in 209.45s |

The observer plugin was kept outside the repository and did not alter transport behavior. The lifecycle fix changes only test-server initialization. No exception suppression, expected-failure mark, assertion removal or production behavior switch was introduced.

Neighboring transport/protocol validation and integrated CI results are recorded in `WHITEPACT_M13P4_TEST_AND_CI_MATRIX.md`; pending evidence is not counted as a pass. See `WHITEPACT_M13P4_MCP_ROOT_CAUSE.md` for the exact mechanism and baseline comparison.
