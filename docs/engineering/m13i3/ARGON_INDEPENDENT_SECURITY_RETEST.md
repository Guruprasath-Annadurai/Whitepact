# Argon independent security retest

Fetched exact PR #212 HEAD `e6af2f86931e5f527768b9c22bf1f0795eb80923`. Its changes after `d0041e4f...` are docs and removal of one unused test import; backend enforcement is unchanged. It descends from I1. Existing PRs and Argon's active branch/directory are untouched.

Preserved original production-origin counterexamples from signed `d1fe6964...` are unchanged on isolated review child `ce41f20487a5e4c4ac6d6932bb665ac1b2c9b667`, tree `33a40b1c35b69f3a744716613284f58028f2e975`. Fresh rerun:1passed/2failed2.83s. Production `_svc` still accepts explicit HTTP and missing-origin fallback. These are constructor/configuration tests with a stub engine, not an authentication exploit or customer journey.

Actual fresh PostgreSQL/Chromium attempt additionally reaches genuine browser credential generation, then registration fails403 assurance. No seeded authority or forged authenticator response. Fresh original+extended execution: **238passed, zero skips,2warnings,430.50s**. The original scope includes real PostgreSQL migrations/concurrency; many extended tests use SQLite/seeded service fixtures. The total is not a claim that all238 exercise live PostgreSQL or a customer authority lineage.

Warnings were retained: existing legacy-key deprecation and an `aiosqlite` background `_connection_worker_thread` reporting `RuntimeError: Event loop is closed`, surfaced during `test_matrix_v9_proxy_environment_variables_prevented`. Assertions passed, but clean resource teardown is not qualified by that result. No warning filter or original test was changed; lifecycle ownership/root cause remains unresolved.

Exact reviewed security HEAD tree `6085aebd3bc7a0c4c2445af944b3344f1a321a97`, parent `90acd672b8fd0b03eb54808d4cec36c05b6cc186`. Review childce41f204 differs only by preserved counterexample tests. Their Git blob `7f1a3646c7d86d1b1831582dc10c28c2dea6a5ea` is identical to the original d1fe6964 counterexample. Clean-source preflights pass original8reproducer preservation, not security acceptance.

Previously identified capability consent/policy/root-expiry, client validation and atomic application-disable/concurrent-registration guarantees remain unqualified because implementation has not changed. Existing3 application tests use SQLite/ASGI fixtures; that historical result is not a new PostgreSQL authority proof. No unqualified security implementation is integrated.

Corrections and exact commits must be independently reviewed before integration. New blocker handoff lives in PR #213/reports; PRs #206–#212 are not modified by I3.
