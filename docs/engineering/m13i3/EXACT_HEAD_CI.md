# Exact-head CI

Draft PR: https://github.com/Guruprasath-Annadurai/Whitepact/pull/213 . Baseline product `e049cc0d7a30d75fffc82a82b11a9cc25ecbb64e`; baseline security implementation `e6af2f86931e5f527768b9c22bf1f0795eb80923`, not integrated.

First actual-browser implementation `a298c970fdaff2477ac85b211d93e9f171c1609f`, tree `98dbb9cda04f53937bc0cd0113531b275749ffde`, parent product baseline. CI checkpoint `9ab14321a80062ac7a2426f8ff3e8f8a0b27128a`, tree `f31baa4f58149965861a8abb859df286cf21cf8b`, adds real Chromium/PG acceptance and redacted evidence retention, preserving full existing lint/DCO/original/extended/native gates.

Every workflow checks out exact PR HEAD. Customer acceptance remains a failed gate when incomplete; the structured report uploads even on failure. No continue-on-error, weakened skip assertion or governance exception. Final full HEAD/tree/parent and completed job/run evidence are recorded on the draft PR and external final handoff to avoid self-referential document hashes. Pending checks are not passes.

## Completed product implementation receipt

Source HEAD `223c74e442784b6a7acb3d44a2294ebbc1c770dc`, tree `f9745341c07e54f71f335a8cff83822b6091a1d1`, parent `9ab14321a80062ac7a2426f8ff3e8f8a0b27128a`: **26completed checks:23passed/3failed/zero pending**.

| Workflow | Measured outcome |
| --- | --- |
| [Independent38862077287](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077287) | Original36/extended202 each Python version passed; Py3.11 timings37.31s/77.95s, Py3.12 29.89s/70.77s;1warning per pytest invocation; zero-skip guards passed |
| Same run, native Linux/container | 15passed115.61s,zero skips |
| Same run, actual customer |13evidence tests passed3.43s; real Chromium/customer attempt BLOCKEDat RP/origin, exit2; redacted artifact retained |
| Same run, lint/DCO | FAILED101inherited diagnostics and unsigned39619c4; no waiver |
| [Product38862077345](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077345) |301frontendtests,363backend/SDK/schema tests each Python,4browserwrappers86.96s/4warnings, lint/type/build/assets all passed |
| [Installed consumers38862077302](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077302) |Both matrices passed |
| [MCP/frameworks38862077283](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077283) |All4jobs passed |
| [Enterprise38862077317](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077317) |All3jobs passed |
| [M12-P38862077308](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077308) |All4jobs passed,includingGo |
| [M11 38862077322](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38862077322) |All4jobs passed,includinginfrastructure |

This evidence-only document commit follows the measured source and changes no implementation/tests. Its separate exact-head checks are recorded in PR #213/final handoff; these timings are not substituted for that later HEAD. The three failed gates still prevent milestone acceptance.
