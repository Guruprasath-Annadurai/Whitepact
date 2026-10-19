# Patched MCP transport dependency

The candidate previously locked MCP1.29.1, affected by
[GHSA-84m7-p3x7-pcfv](https://github.com/advisories/GHSA-84m7-p3x7-pcfv):
stateful Streamable HTTP sessions can accumulate without bound. Authentication
does not cap the number of sessions an authorized client can create. This
advisory was retrieved directly from GitHub's advisory API on2026-10-19.

Raise all project MCP minimums to1.30.0, retain the `<2.0.0` compatibility bound,
and lock the patched1.30.0 release. PyPI release metadata for1.29.1 and1.30.0
has identical `requires_dist` sets and the same Python minimum. Source and wheel
URLs, SHA256 digests, sizes and timestamps were verified against PyPI1.30.0
metadata. Correct the lock's pre-existing root MCP specifier metadata to match
the project. No unrelated dependency versions were changed.

`uv lock --check` resolved210packages without a lock rewrite. Local installed
environment dependency validation passed147packages. A first pip attempt failed
because the existing development venv has no pip; uv installed the actual
patched wheel successfully. A first test launch lacked pytest-timeout and
failed argument parsing; the plugin was installed before bounded rerun. Neither
setup failure is a test PASS.

This update does not claim session retention is zero, that every deployment's
resource budget is adequate, or that the remaining NLTK advisory is resolved.
The advisory's defaults still need deployment-specific resource review before
any future production authorization. Current production authorization remains
absent. M13 OPEN. GLOBAL PRODUCTION NO-GO.
