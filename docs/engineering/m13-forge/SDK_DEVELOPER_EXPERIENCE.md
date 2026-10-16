# Developer experience

Forge does not change SDK APIs or package names. Fresh TypeScript tarball installation passed for external ESM and CommonJS consumers. Fresh Python wheel build/install/import and negative insecure-transport test passed in an isolated environment (`--noconftest` excludes unrelated application fixtures). Initial Python attempts failed because the shared interpreter lacked build and the isolated interpreter lacked unrelated numpy fixtures; these were environment failures, not passes. Go and optional framework qualification remain NOT EXECUTED locally on Forge. No packages published.

Next: inspect public quickstarts against supported consumer contracts, execute isolated consumers, preserve actual dependency skips as SKIPPED/UNVERIFIED, and repair source-backed product-owned mismatches.
