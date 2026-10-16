# Exact-head CI

Draft PR: https://github.com/Guruprasath-Annadurai/Whitepact/pull/213 . Baseline product `e049cc0d7a30d75fffc82a82b11a9cc25ecbb64e`; baseline security implementation `e6af2f86931e5f527768b9c22bf1f0795eb80923`, not integrated.

First actual-browser implementation `a298c970fdaff2477ac85b211d93e9f171c1609f`, tree `98dbb9cda04f53937bc0cd0113531b275749ffde`, parent product baseline. CI checkpoint `9ab14321a80062ac7a2426f8ff3e8f8a0b27128a`, tree `f31baa4f58149965861a8abb859df286cf21cf8b`, adds real Chromium/PG acceptance and redacted evidence retention, preserving full existing lint/DCO/original/extended/native gates.

Every workflow checks out exact PR HEAD. Customer acceptance remains a failed gate when incomplete; the structured report uploads even on failure. No continue-on-error, weakened skip assertion or governance exception. Final full HEAD/tree/parent and completed job/run evidence are recorded on the draft PR and external final handoff to avoid self-referential document hashes. Pending checks are not passes.
