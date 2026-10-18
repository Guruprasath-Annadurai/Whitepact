# M13 runtime containment reconciliation

Tested source HEAD `7939341fd9d98d0f1fa39ce4421318dbc1dac33e`; tree `6bf30ee0d11c8137ec6a77844b1517de50d89edd`; parent `3be566129be44e00e92a07dd9449c957751eeb5d`. Candidate branch `codex/whitepact-m13-absolute-convergence`, [draft PR220](https://github.com/Guruprasath-Annadurai/Whitepact/pull/220). Production `src` subtree `bbd0e5f0b6a7dd02b388ab45d4dc5a7fed9036f1` is unchanged since296ad7ff. Final reports live on documentation-only branch `codex/whitepact-m13-absolute-evidence`. Historical receipts identify their own HEAD and do not substitute for final7939341f evidence.

Verdict: bounded corrective runtime behavior available for review; mandatory acceptance BLOCKED.

## Safety contract and corrections

Dead worker does not prove dead container. Preserve unresolved tracking after PID disappearance, unknown Docker state, daemon/plugin/inspect failure, cancellation cleanup failure and unreadable tracking directories. Literal True termination confirmation is required; None is not proof.

Tracking uses exact-string, length-framed/domain-separated SHA256 paths; payload identity must match filename. The owned directory rejects symlink/world-writable configurations. JSON publication is atomic/no-replace; corrupt and existing authority cannot be overwritten. Registrations have UUID ownership; every production cleanup supplies its UUID. Shared bounded POSIX flock serializes publication and compare/unlink, preventing the independently reproduced ABA race. Lock acquisition times out fail closed after1s; symlink/unsafe lock files are refused. Duplicate in-memory registration preserves the original callback and tracks a separately identified rejected attempt until its termination is confirmed. Runtime reconciliation selects canonical governance scope only.

Six owner-source RED cases and later scope/cleanup race RED cases drove these fixes. Historical local corrective scope 39 PASS; committed296ad7ff independent tracking16 plus genuine A2 negatives4 returned20 PASS in 80.98s. These are unit/file-system/injected-callback tests, not native Docker receipts.

## Immutable contract conflicts

Original test_kill_esrch_unlinks_dead_worker_tracking expects PID-only unlink. It stays unchanged and failed: no safe implementation can infer detached-container absence from that fact alone. Maintainer must authorize an authoritative absence oracle/specification disposition. Original owner NFC and legacy-prefix assumptions likewise remain failed; unknown ownership cannot become admission. The required lock adds a second non-JSON directory entry, conflicting with the original owner count assertion.

The directory must be application-owned. Uninterpretable legacy records remain globally uncertain and can deny service. Safe operator reconciliation and availability recovery remain BLOCKED; no record is deleted solely to restore availability. Same-UID malicious/noncooperating writers, unstable lock inodes, network filesystems and incompatible old runtime processes are not qualified.

## Restore and public boundary

Original independent real-PG reproducer is preserved at scripts/engineering/reproducers/test_m13_fortress_restore_independent.py. The canonical-floor and restrictive-FK assertions remain FAIL; canonical runtime scope passes. At296ad7ff, combined HTTP+restore scope returned3 PASS/2 FAIL in 84.59s. Atc46dffb5, remote real-PG scope returned1 PASS/2 FAIL on both Python versions. No fixture rows count as customer authority.

Both public restore aliases deny503 unconditionally and preserve RESTORE_PENDING. Read-only status remains available. This disables the reproduced unauthenticated admission mutation, without enabling operator recovery or fixing the underlying service. Public root recovery create/vote/execute also remain disabled.

## Final-head qualification

Final 7939341f Runtime Review: [39156415506](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39156415506) FAILURE. Actual Docker/native 19 PASS per interpreter (3.11 in 124.66s;3.12 in 130.84s). Additional persistence/PostgreSQL22 PASS per interpreter (9.43s/10.03s). Original runtime scope 54 PASS/1 FAIL per interpreter (11.24s/12.39s); failure is preserved PID-only unlink assertion. Real PostgreSQL restore1 PASS/2 FAIL per interpreter (11.97s/11.90s), canonical-floor and restrictive-FK cases. No skips in these dedicated scopes. Focused Ruff/pinned-action/trust checks remain separate. Logs `/private/tmp/m13-7939341f-runtime.log`; artifacts `runtime-review-{3.11,3.12}-17135bbe2686cfc086ccc569e50f80fe08e1f9ea` contain runtime.xml/restore.xml. The suffix is PR merge SHA; checkout/provenance logs verify tested7939341f/tree6bf30ee0. Artifact naming is not tested-source identity.

Predecessorc46dffb5 runtime native 19 PASS per interpreter; unit22 PASS plus54 PASS/1 immutable failure; PG1 PASS/2 FAIL per interpreter. Its artifact label contains PR merge SHA aafd09d13114821dbe2abee7cc44502f1ffa3519, while checkout/provenance logs verify actual tested c46dffb5. Artifact names alone are not source provenance.

A separate full-suite actual CPU busy-loop case measured4.1302s against an unchanged3s assertion on296ad7ff. This is a failed resource-latency gate, not declared flaky or threshold-relaxed. Full-suite final timing and all native results remain separately accounted in the coverage report.
