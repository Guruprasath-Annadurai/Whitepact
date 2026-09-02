# `test_v1_api.py` Hang — Root-Caused and Fixed

Found while running the full suite to verify Phase 6/9/21/22/24/31/
32-33/supply-chain-pinning work; initially documented as an open,
pre-existing issue (see git history for that version of this doc).
Root-caused and fixed in a follow-up pass.

## What was observed

`tests/test_v1_api.py::TestAPIVersionEndpoint::test_v1_prefix_routes_to_version`
hung indefinitely (not just slow — no progress, no timeout, no error)
when run after `test_v1_prefix_routes_to_health` in the same process.
In a full-suite run this surfaced as a `TimeoutError` from
`asgi_lifespan`'s own internal guard; run in isolation with no such
guard racing it, it hung past that and just sat.

## Confirmed pre-existing (not caused by this session's earlier work)

Verified with `git stash` (stashing every tracked change from the
Phase 6/9/21/22/24/31/32-33/supply-chain-pinning commit) and
re-running `tests/test_v1_api.py::TestAPIVersionEndpoint` against the
unmodified prior `HEAD`: the hang reproduced identically with none of
that work present. Ruled out `AuthFailureLimiter` (Phase 6) and the
`aiosqlite`/`asyncpg` logging level cap (Phase 9) as the cause.

## Root cause, found on the follow-up pass

`tests/test_v1_api.py`'s `client` fixture never overrode the shared
`Settings` singleton — every other test file building a `client`
fixture in this suite explicitly monkeypatches
`db_path=":memory:"`/`auto_migrate=False` before touching the app;
this file had neither.

`Settings`' real, unpatched defaults (`dashboard/config.py`) are
`db_path` = `~/.responsibleai/data.db` (a real file in the real user
home directory, **not** `:memory:`) and `auto_migrate=True`. With no
override, every one of this file's ~40 tests using the `client`
fixture triggered a full, real application startup against that real
path — including a real `alembic upgrade head` **subprocess spawn**
(`db/migrate.py` shells out to `sys.executable -m alembic`) on every
single test, sequentially, dozens of times in a row against one shared
on-disk SQLite file.

**Confirmed as a genuine side effect, not just theorized**: after a
run of this file, `~/.responsibleai/data.db` existed on disk (1.16 MB,
real migration history) — this test file was quietly writing to real,
persistent state in the actual user's home directory on every run.
Piling up that many real subprocess spawns and real file-lock
acquisitions against one shared file in a tight loop is consistent
with the observed hang; the exact failure point (subprocess contention
vs. SQLite file-lock contention vs. accumulated OS resource pressure)
was not narrowed further once the actual root cause and fix were
identified, since the fix removes the real state entirely rather than
requiring that level of detail.

## Fix

Added the same `_default_test_settings` autouse-fixture pattern
`test_dashboard_api.py`/`test_redteam_audit_billing_api.py`/
`test_signup.py` already use: `monkeypatch.setattr()` the shared
`settings` singleton to `db_path=":memory:"`, `auto_migrate=False`,
`auth_enabled=False` (matching what every test in the file already
implicitly assumed — none of them expect a 401). Also corrected the
`client` fixture to bind `AsyncClient` to `manager.app` (the
lifespan-wrapped app `asgi_lifespan` actually manages) instead of the
raw `app` reference, matching the established convention in every
other file's `client` fixture.

Cleaned up the stray `~/.responsibleai/data.db` (and the empty
`~/.responsibleai/` directory left by the *first* ever `get_settings()`
call in a session, a separate, harmless, one-time side effect) created
during this investigation.

## Verification

- `tests/test_v1_api.py` in isolation: **48 passed in 2.49s** (was:
  indefinite hang). No `~/.responsibleai/data.db` created by the fixed
  run — confirmed the real-state leak is gone, not just the symptom.
- `ruff check` clean.
- A subsequent full-suite run reached 2636 tests passed with zero
  test failures before an unrelated environment issue (the host
  machine's disk running critically low, ~840 MB free) crashed
  pytest's own output-capture machinery mid-run — an infrastructure
  constraint on this development machine, not a test failure, and not
  something this fix (or any prior phase's work) caused. A clean full
  run should be re-attempted once disk space is available; every test
  observed before the crash passed.

## Disposition

**Closed.** Root cause identified with direct evidence (the real file
on disk), fixed with the same pattern already established elsewhere in
this suite, and verified both by the fix working and by confirming the
side effect it was causing is gone.
