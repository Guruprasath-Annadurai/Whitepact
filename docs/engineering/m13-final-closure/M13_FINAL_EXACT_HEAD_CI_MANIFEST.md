# M13 exact-head CI manifest — engineering candidate, OPEN

Last published baseline:bff5f143933d518e921592361f0171d7cf7ff6ef,
tree146e459f08eb685331c0f07f6f0bec090d95e0ce. Previous full matrix39414578546
is red and remains immutable evidence, not the result of the current correction.

New workflow:.github/workflows/m13-absolute-final-containment.yml.
It runs on the dedicated Codex branch push with exact github.sha checkout,
Python3.11/3.12, digest-pinned PostgreSQL16 and real native Linux Docker.
The runtime image is built locally on the disposable runner and executed by ID.
It records HEAD/tree/parent and always retains JUnit artifacts, including failures.
Unit, SIGKILL/deleted-or-corrupt metadata and original native/soak phases are distinct.
No missing environment or skipped native case qualifies as PASS.

Actionlint, pinned-action checks, scoped Ruff and full source mypy passed locally
during implementation. Final exact source, run IDs, artifact hashes, broader matrix
and coverage must be appended through the publication/CI receipt, not invented in
advance or copied from an earlier SHA. No production/release job is dispatched.
