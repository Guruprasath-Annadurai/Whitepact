# M13 runtime containment reconciliation

Status: PARTIAL; native final-head validation pending.

Dead worker is not dead container. Immutable test_kill_esrch_unlinks_dead_worker_tracking remains unchanged and failing against safer retention. Maintainer disposition must require authoritative containment confirmation; PID-only deletion is rejected.

Tracking corrections: exact-string domain-separated digest filenames, atomic no-replace publication, owned/non-world-writable directory checks, rejection of symlink records, payload/digest checks, corrupted/partial record uncertainty, preservation of original callback on duplicate execution ID, separate rejected-attempt identity and termination, and no removal of another writer's record following persistence failure.

Unattributable legacy records remain unresolved, are never silently deleted, and block admission. This can deny service; the directory must be application-owned and not writable by unrelated tenants. Operator reconciliation/quarantine policy remains required. Same-UID malicious processes and unsupported network filesystems are not qualified by these unit tests.

Original owner Unicode normalization assertion remains failing: the database uses exact identifier strings, so NFC-equivalent distinct database identifiers must not share tracking names. No mathematical SHA-256 injectivity claim.

Actual Docker/Linux evidence from38f3ceb0 is historical (19 PASS per interpreter); no final integrated native PASS is claimed. Filesystem and subprocess-injected tests are labeled unit fault injection.

Local working-tree qualification:23 PASS in8.54sec for ten independent convergence counterexamples plus tests/test_in_flight_revocation.py, including real subprocess revocation and explicit retry cleanup. /private/tmp/m13-convergence-registry-green.log. An additional inherited gap was reproduced: callback None counted as termination confirmation. Both termination and retry now require literal True; confirmed retries remove their own durable record. Original protected dead-worker and owner NFC assertions remain unchanged, with explicit specification conflicts.
