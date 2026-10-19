# IRONCLAD CPU performance

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Current exact-source evidence

Exact-source [39243112392](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39243112392), Docker CLI28.0.4, five fresh processes per version/source, original `<3s` bound unchanged. Baseline d9:10/10 FAIL; candidatecc:10/10 PASS. Python3.11 candidate seconds `[1.427050327,1.124825284,1.174813025,1.125735987,1.793024208]`, p50=1.174813025,p95=1.793024208; baseline p50=4.349919371,p95=4.383738115. Python3.12 candidate `[1.176080512,1.177045138,1.124938159,1.126205844,1.127660326]`, p50=1.127660326,p95=1.177045138; baseline p50=4.320645762,p95=4.410740228. p95 is nearest rank/max for n=5, not a production SLO. Baseline26rm+26inspect per sample; candidate2rm+2inspect. Candidate host-process CPU ranges3.11 .009634–.010548s,3.12 .009033–.009450s; excludes Docker daemon/container CPU. Cleanup wall time is included in the original outcome. Matching installed CLI create/run source and SHA256 are in artifacts: create acknowledgment writes CID before ContainerStart of that same ID. Known acknowledgment permits immediate authoritative absence; interrupted unknown creation retains the original bounded observation and UNRESOLVED. Same immutable image within each comparison:3.11 `sha256:1c8ffaa9d1a83cb2b0fb7d1146e4f6777b331ac71c8a18d6a0cb63978096e4da`;3.12 `sha256:90c72c771fa07cb9bfdf610c5954770a571a41faf2ae956d263df75bb5bfa86a`. Same-UID host and trusted daemon/CLI remain explicit trust boundaries.

## Diagnosed timing conflict

Original `7939341f` Linux busy-loop test measured4.226132292 s on3.11 and4.190629838 s on3.12 against unchanged3.0 s limit. Source operation includes1 second execution timeout followed by compulsory3 second stable-absence observation when execution is incomplete, then assigns outcome duration after cleanup. Thus current timing cannot satisfy the bound; no evidence supports calling this flaky or pure CPU saturation.

No threshold increase, time subtraction, clock manipulation or cleanup weakening is accepted. Current checkpoint changes no performance or containment code.

## Safe design investigation

A potential fast path needs daemon-confirmed creation/identity, successful removal of that exact daemon-issued containerID, then authoritative absence for ID and generated name. Any inspect error, mismatch, failed removal, unknown/incomplete creation or cancellation uncertainty must retain original late-creation observation and unresolved tracking. Attacker-writable cidfile is not proof. Separate create/start is stronger but more invasive.

Required new controls: absent→late-created daemon race, delayed start after confirmed creation, wrong name/ID, inspect/plugin errors, removal failure, repeated cancellation and unresolved admission. Existing cancellation/stability tests do not directly prove absent→late-created safety. Actual pinned Linux profile must separate execution/cleanup/Docker command/wall/processCPU timing and report genuine repeated measurements only. No p50/p95 invented. Performance gate remains FAIL pending safe implementation and measurement.

## Added measurement instrumentation

m13_ironclad_cpu_profile.py executes five fresh-process repetitions of the unchanged original CPU test. It records exact Git provenance, original outcome duration, execution/cleanup wall time, host Python process/threadCPU, and Docker rm/inspect timings/counts without command arguments or output. CPU excludes CLI/daemon/container usage; overlapping intervals are not additive. Original assertion failure propagates. Missing, skipped, timed-out or stale receipts are not PASS.

Seven instrumentation contract tests PASS on local Python 3.11; these synthetic observations provide no Docker performance measurements. Local Python 3.12 attempt did not collect because sklearn was absent; NOT_EXECUTED. Actual two-version Linux profiling is added to the next targeted workflow and remains pending. Host-private daemon-acknowledged CID ownership is under design review as a possible safe optimization; current workspace-writable CID is not trusted proof.

## Candidate ownership-based optimization

Source47fc55a1 moves the receipt out of the workload mount, validates it strictly, and uses authoritative exact-ID/name cleanup immediately only after acknowledged creation (or successful completed CLI execution). Outcome duration still includes all cleanup. Unknown interrupted creation retains the bounded cleanup attempt and remains unresolved afterward; the3-second observation is not treated as proof that a delayed creation cannot arrive.

Docker's official create.go writes its daemon response ID after successful ContainerCreate, and run.go subsequently starts that same identity without another create. Delayed start cannot resurrect a removed exact ID. This is a conditional source-contract argument; the workflow records actual Docker version, downloads the matching CLI tag source, and preserves its hashes for independent review. No claim of universal compatibility with arbitrary CLI/daemon replacements is made.

The successor workflow profiles five actual RED baseline repetitions at preserved d9ddf44a and five candidate repetitions on each Python version using the same immutable runtime image ID. It preserves underlying original assertion failures and verifies baseline controls, rather than calling them passing CPU tests. Candidate timing must pass the unchanged original test. Actual measurements remain pending.
