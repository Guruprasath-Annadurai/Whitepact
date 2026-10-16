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

## Completed final product source receipt

Exact source commit `6e2363cfbaa12a62ef94f04313ea16a8eb6c1b39`, tree `47c5bb324a1ac166b11270d350c7a4d76511f54c`, parent `0015f343e06fa27bc61d4289c2cd23b2d4a671b7`: **26 completed checks, 23 passed, 3 failed, zero pending**. This receipt is committed afterward as documentation only; the PR identifies that document commit and its own exact-head checks separately. No implementation or test result is inferred from a different commit.

| Final source workflow | Actual result |
| --- | --- |
| [Independent review 38858654917](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858654917) | Python3.11 original36passed1warning40.62s +extended202passed1warning80.87s; Python3.12 original36passed1warning41.73s +extended202passed1warning78.72s; zero-skip guards passed |
| Same independent review, native Linux/container | 15passed, zero skips, 115.67s |
| Same independent review, actual customer | Six evidence tests passed3.20s; actual22confirmed phases, passkey origin mismatch BLOCKED, exit2; not a green customer gate |
| Same independent review, inherited lint/DCO | Both FAILED:101 inherited errors and unsigned39619c4 checkpoint; no policy exceptions |
| [Product review 38858654938](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858654938) | All3jobs passed:289frontendtests/31files,363backend/SDK/schema tests each Python version,53TypeScripttests each matrix,3browserwrappers78.46s with3deprecation warnings; lint/type/build/assets passed |
| [Installed SDK consumers 38858654983](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858654983) | Both Python3.11/3.12 +Node22 jobs passed |
| [MCP/frameworks 38858655047](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858655047) | All4jobs passed |
| [Enterprise 38858655073](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858655073) | All3jobs passed |
| [M12-P 38858655011](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858655011) | All4jobs passed including Go |
| [M11 38858655222](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38858655222) | All4jobs passed including infrastructure |

The three failures are mandatory unresolved gates. The actual source candidate remains NO-GO even though unrelated product/compatibility regressions pass. ATLAS production-origin failures are preserved on a separate review branch and its implementation is not in this source.
