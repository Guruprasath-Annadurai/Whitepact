# Exact-head CI matrix

Review PR: https://github.com/Guruprasath-Annadurai/Whitepact/pull/211 .

Initial signed checkpoint: `7b2c84f31220216c68c222c2655a8ae8215a8f69`; tree `9466dceca5be17739d5998d4fbaca39f2c4536e2`; parent `8cb692b99fb4b1fa894e07d432105209f430b0f7`.

CI path selection now includes I2 reports, harness/tests and console changes. Existing independent original/extended security suites, actual Linux/container probes, real-customer failure, full lint and DCO gates remain enabled. The DCO range deliberately retains the inherited security checkpoint even when this draft is stacked on I1.

Initial exact-head independent review: [run 38805855458](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/38805855458). Both Python security jobs and the native Linux/container job passed; real customer journey, inherited lint and retained DCO failed. See `SECURITY_INDEPENDENT_RETEST.md` for fresh test counts. These results apply to the initial checkpoint only.

No pending result is a pass. Final source checkpoint, run/job URLs and outcomes will be recorded after integration. The PR supplies the exact final document commit and tree to avoid self-referential hash claims.
