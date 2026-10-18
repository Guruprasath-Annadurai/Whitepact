# M13 runtime containment reconciliation

Status: PARTIAL; native final-head validation pending.

Dead worker is not dead container. Immutable test_kill_esrch_unlinks_dead_worker_tracking remains unchanged and failing against safer retention. Maintainer disposition must require authoritative containment confirmation; PID-only deletion is rejected.

Tracking corrections: exact-string domain-separated digest filenames, atomic no-replace publication, owned/non-world-writable directory checks, rejection of symlink records, payload/digest checks, corrupted/partial record uncertainty, preservation of original callback on duplicate execution ID, separate rejected-attempt identity and termination, and no removal of another writer's record following persistence failure.

Unattributable legacy records remain unresolved, are never silently deleted, and block admission. This can deny service; the directory must be application-owned and not writable by unrelated tenants. Operator reconciliation/quarantine policy remains required. Same-UID malicious processes and unsupported network filesystems are not qualified by these unit tests.

Original owner Unicode normalization assertion remains failing: the database uses exact identifier strings, so NFC-equivalent distinct database identifiers must not share tracking names. No mathematical SHA-256 injectivity claim.

Actual Docker/Linux evidence from38f3ceb0 is historical (19 PASS per interpreter); no final integrated native PASS is claimed. Filesystem and subprocess-injected tests are labeled unit fault injection.

Local working-tree qualification:23 PASS in8.54sec for ten independent convergence counterexamples plus tests/test_in_flight_revocation.py, including real subprocess revocation and explicit retry cleanup. /private/tmp/m13-convergence-registry-green.log. An additional inherited gap was reproduced: callback None counted as termination confirmation. Both termination and retry now require literal True; confirmed retries remove their own durable record. Original protected dead-worker and owner NFC assertions remain unchanged, with explicit specification conflicts.

Further final corrections: canonical epoch scope only; registration-specific cleanup; shared bounded POSIX ownership lock prevents comparison/unlink ABA races. The forced interleaving test failed before locking and passed after. Symlink lock files are refused, lock contention times out without publishing authority, and ambiguous legacy records are preserved.16 focused tracking cases PASS locally. No claim that arbitrary same-UID malicious writers, mixed incompatible runtime binaries or network filesystems honor this locking contract.

Exact de9c2d1e PostgreSQL reproduction returned2 FAIL in24.04sec: canonical floor stays2 rather than7, and a real approval→runtime-request FK prevents restore deletion. These are inherited backup blockers on the actual candidate, not fixed by rejecting FORTRESS's incompatible implementation. Public restore/deployment acceptance remains BLOCKED pending security-owner correction.

Final precommit affected-runtime scope:39 PASS in13.68sec, covering16 independent tracking cases, neighboring in-flight revocation and corrected ordinary container-branch fixtures. /private/tmp/m13-convergence-precommit-runtime.log. No original immutable assertion was edited. The final committed-head native/PG matrix remains authoritative over this working-tree result.
