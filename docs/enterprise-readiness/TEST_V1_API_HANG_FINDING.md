# Known Issue — `test_v1_api.py` Hang, Confirmed Pre-Existing

Found while running the full suite to verify Phase 6/9/21/22/24/31/
32-33/supply-chain-pinning work. Documented, not fixed in this pass —
scope and root cause below.

## What was observed

`tests/test_v1_api.py::TestAPIVersionEndpoint::test_v1_prefix_routes_to_version`
hangs indefinitely (not just slow — no progress, no timeout, no error)
when run after `test_v1_prefix_routes_to_health` in the same process.
In a full-suite run this surfaces as a `TimeoutError` from
`asgi_lifespan`'s own internal guard (`LifespanManager`'s 5-second
startup timeout catches it); run in isolation with no such guard
racing it, it hangs past that and just sits.

## Confirmed pre-existing, not caused by this session's work

Verified directly with `git stash` (stashing every tracked change this
session made — all of Phase 6/9/21/22/24/31/32-33/supply-chain-pinning)
and re-running `tests/test_v1_api.py::TestAPIVersionEndpoint` against
the unmodified `HEAD`: **the hang reproduces identically with none of
this session's changes present.** The stash was fully restored
afterward (`git stash pop`) — nothing from this session's work was
lost or altered by this investigation.

This rules out every file this session touched, including the new
`AuthFailureLimiter` (Phase 6) and the `aiosqlite`/`asyncpg` logging
level cap (Phase 9) — both were suspected first, both are innocent.

## What's known about the hang itself

- Occurs specifically between two consecutive tests that each build a
  fresh `LifespanManager(app)` via the file's function-scoped `client`
  fixture — the hang is in app startup or shutdown machinery between
  test N and test N+1, not in the `/api/v1/version` endpoint's own
  logic (a trivial handler).
- Not reproducible from a cold, low-test-count run — needed roughly 20
  prior tests in the same process to manifest, consistent with this
  session's other finding (`TEST_SUITE_ORDERING_FRAGILITY_INVESTIGATION.md`)
  that this codebase's test suite has real, unresolved fragility around
  cumulative resource/state in a single long-running pytest process —
  though this specific hang's exact mechanism was not root-caused
  further given time constraints, and may be a different underlying
  cause than that investigation's settings-singleton race.

## Disposition

Recorded honestly as a real, open, pre-existing issue — not silently
worked around, not misattributed to this session's changes (confirmed
negative via `git stash`, not assumed), and not left undocumented for
the next person to rediscover from scratch. A dedicated investigation
(the same rigor `TEST_SUITE_ORDERING_FRAGILITY_INVESTIGATION.md`
applied) is a reasonable follow-up, out of scope for this session
given the volume of substantive work already completed.
