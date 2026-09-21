# Known limitations (DRAFT — pending combined V1 RC)

Evidence-based inventory for release handoff. Not a certification statement.

| Limitation | Status | Evidence |
|------------|--------|----------|
| Authenticated live MCP handshake | PENDING | No scoped monitor credential in prep environment |
| MCPBeat historical uptime | UNRESOLVED | Auth/probe mismatch hypothesis; not proven fixed post-deploy |
| NLTK PYSEC-2026-3740 / CVE-2026-81726 | OPEN upstream | Opt-in `[sentiment]` only; limited legacy reachability |
| Combined RC migration head vs Sovereign | PENDING | RC P0 @ `0060`; `0061+` expected after Sovereign merge |
| Go parity / external provider validation | INCOMPLETE | Per existing project docs |
| Policy-at-T partial semantics | VERIFY on combined RC | Re-validate on exact SHA |

Do not remove items without new evidence.
