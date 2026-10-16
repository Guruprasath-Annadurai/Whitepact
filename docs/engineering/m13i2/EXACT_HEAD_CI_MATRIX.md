# Exact-head CI matrix

Review PR: https://github.com/Guruprasath-Annadurai/Whitepact/pull/211 .

Initial signed checkpoint: `7b2c84f31220216c68c222c2655a8ae8215a8f69`; tree `9466dceca5be17739d5998d4fbaca39f2c4536e2`; parent `8cb692b99fb4b1fa894e07d432105209f430b0f7`.

CI path selection now includes I2 reports, harness/tests and console changes. Existing independent original/extended security suites, actual Linux/container probes, real-customer failure, full lint and DCO gates remain enabled. The DCO range deliberately retains the inherited security checkpoint even when this draft is stacked on I1.

Initial exact-head independent review: [run 38805855458](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38805855458). Both Python security jobs and the native Linux/container job passed; real customer journey, inherited lint and retained DCO failed. See `SECURITY_INDEPENDENT_RETEST.md` for fresh test counts. These results apply to the initial checkpoint only.

No pending result is a pass. Final source checkpoint, run/job URLs and outcomes will be recorded after integration. The PR supplies the exact final document commit and tree to avoid self-referential hash claims.

## Integrated console and harness checkpoint

Commit `29918a9cccdea1b36a5800289aa1bdf284906985`, tree `bc443f7464445ca7f36dfd12b15d8273bd3d8456`, parent `36e60bb999599b014ae8e3459ffee45db46716a4`: **26 completed checks, 23 passed, 3 failed, zero pending**. This is a completed intermediate I2 checkpoint; later organization/harness extensions need a new exact-head receipt.

| Scope | Run / outcome |
| --- | --- |
| Original/extended security and native Linux/container | [38806689920](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806689920), three jobs passed |
| Real customer journey | Same run, failed intentionally after five evidence tests passed; actual passkey origin mismatch remains BLOCKED |
| Inherited lint and DCO | Same run, both failed; 101 inherited lint errors and unsigned security checkpoint remain gates |
| Product console and contract/browser tests | [38806690006](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806690006), all passed |
| Actual MCP/framework consumers | [38806689850](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806689850), four matrix jobs passed |
| External installed SDK consumers | [38806690092](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806690092), Python 3.11/3.12 with Node 22 passed |
| Enterprise / prior product workflows | [38806689768](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806689768), [38806690038](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806690038), [38806690098](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38806690098), all reported jobs passed including Go |

The historical TypeScript hanging-body timeout failure remains **not reproduced, not proven resolved**. Fresh package/transport passes do not erase it. Full lint, DCO and actual customer failures remain visible; no continue-on-error or exclusions were added.
