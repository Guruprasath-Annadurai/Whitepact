# Wave 1 installed SDK consumer integration

This branch is stacked on Go SDK PR #199 at
`fbdfee36dd31fec4d66c835eb08a47e3a0b946f5` (baseline PR #198 is preserved).
It incorporates package-only source lane `5ec6fb3157820c82c1db5794905747eb6bdf3eba`
with `cherry-pick -x`. No package implementation or shared security file is changed.

The external Go consumer now compiles the actual canonical governance methods,
rejects insecure bearer transport before mutation, and rejects non-success
completion. The underlying full Go suite runs against this branch's SDK, not the
older analytics-only ancestor. Local Go module replacement is **not** proof of
remote registry retrieval or a published module version.

Coordinator fresh result: **3 passed, 0 failed, 0 skipped**, 32.62 seconds.
Python 3.11.15, Node 26.0.0, npm 11.12.1 and pinned Go 1.22 image locally;
Ruff lint/format PASS. CI separately exercises Python 3.11/3.12 and Node 22.
Actual CI evidence must be inspected before claiming those environments passed.

Build/install subprocesses exclude inherited service credentials and PYTHONPATH.
Python global pip configuration is disabled. npm user/global configuration uses
distinct nonexistent temporary paths, avoiding inherited registry credentials.
An initial coordinator test run used `/dev/null` twice; npm correctly rejected
duplicate configuration loading (2 passed, 1 failed). The test harness—not the
package—was corrected, preserving credential isolation, and all three reran green.

The earlier source lane's offline npm cache miss and false lead from a different
working directory are disclosed in its evidence. No unsupported CommonJS build
fix was made: no target-SHA package defect was reproduced. Node 26 require/ESM
interoperability alone is not a guarantee for Node 18/20 or all historical clients.

This is installation and negative consumer qualification, not production authority,
release/signature/SBOM proof or publication. Antigravity retains P0 runtime/billing/
revocation/containment ownership. Production remains NO-GO.
