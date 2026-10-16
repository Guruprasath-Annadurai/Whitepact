# Immutable migration evidence

Status: original PRESERVED; upstream change REVIEWED_CHANGE; manifest replacement
not accepted for APEX. This does not qualify the complete security implementation.

Original test path: `tests/independent_m13r2/test_m13r_migration_roundtrip.py`.
Original Git blob: `f4d5731e9b2792b18a69e1fcfd475164ee4f0898`.
TITAN40e43440 blob: `071cbecd44d8e965c694f9c857bf8d96fdc79fc3`.

The upstream change replaces `upgrade head` with `upgrade0064`. It preserves
constraint/index/FK/downgrade assertions for the historical0064 revision but no
longer tests latest-head upgrade at that point. Thus it makes the scope revision
specific and removes implicit latest-head coverage; it is not byte-identical
independent evidence. The accompanying `scripts/engineering/m13p4_security_acceptance.py`
manifest substitutes the new blob hash for the original. APEX retains the old
test and manifest unchanged; no hash was changed to manufacture a green preflight.

Protected verification checkout: clean detached
`/private/tmp/whitepact-apex-immutable-evidence`, commit
`9fc9f94873d645ce36239e44eef6919a8604bdc7`, tree
`61393e3e6a9128c0e4dbd51e533a0f023f840e5c`. Protection means isolated, unchanged
checkout plus verified Git blob identity; no filesystem immutability is claimed.
Original migration tests:2PASS,50.76seconds, actual disposable PostgreSQL.

Against candidate40e43440 the original broader36-assertion suite records35PASS,
1FAIL, zero skips. The same original migration assertion observes0065 where it
requires0064. Preserve that failure; later downgrade assertions in that test
were not reached. Separate new forward/data-retention probe supplements it,
without replacing or editing the protected original.
