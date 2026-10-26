# Wave 1 local package-install qualification

Base: `f338556baf9984ab485f2d4758179fb87e8baa4d` (preserved PR #198).
Branch: `codex/whitepact-wave1-package-install`.
Owned files: new package-install test, nonsecret external Go consumer fixture,
and this evidence document. No SDK implementation or package metadata changes.

## Actual consumer boundaries

- Python: build a real `rai-client` wheel from a temporary source copy; create a
  fresh venv; install the wheel with its declared HTTPX dependency; run `pip check`;
  import the installed SDK outside the source tree; reject insecure bearer URL.
- TypeScript: locked dependency install, `tsc` production build, real `npm pack`,
  local tarball install into an external consumer; execute ESM imports and Node
  26 `require` interoperability; verify UNKNOWN, DENIED, PENDING and FAILED cannot
  be classified as completed by the installed package.
- Go: external module with an explicit local `replace`, using pinned Go 1.22
  container image `sha256:1cf6c45ba39db9fd6db16922041d074a63c935556a05c5ccb62d181034df7f02`.
  Compile/run an external consumer that rejects insecure bearer transport, then
  run the SDK's existing tests. Docker network is disabled. Source mount read-only.

Consumer subprocesses receive only PATH/HOME/temp/locale/platform environment
variables: no inherited application credentials or PYTHONPATH. All generated
artifacts remain in pytest temporary directories. Nothing is published.

## Fresh commands and versions

```sh
PYTHONPATH=src:. python -m pytest tests/test_wave1_package_install.py -q --no-cov --tb=short
ruff check tests/test_wave1_package_install.py
ruff format --check tests/test_wave1_package_install.py
git diff --check
```

Observed local runtimes: Python 3.11.15, Node 26.0.0, npm 11.12.1, pinned Go 1.22
container. Final hermetic rerun: **3 passed, 0 failed, 0 skipped**, 45.90 seconds;
no pytest warning summary. Ruff lint/format and diff checks passed. The preceding
non-hermetic run also passed all three in 49.74 seconds; it is not substituted for
the final result. An initial strict-offline npm attempt failed because the isolated cache
lacked `undici-types`; this was an environment failure, not an SDK failure.
`--prefer-offline` permits resolving missing locked public dependencies. Python
wheel dependency installation likewise needs available public dependencies.

## Scope and limits

Three package-level pytest cases are separate from the nested Go test execution;
do not count the wrapper plus nested tests as independent release proof. No
Node 18/20/22, Python 3.12, published registry resolution, cross-platform package
retrieval, or production qualification is claimed by this local run. The observed
Node 26 require behavior is not a promise of separate CommonJS distribution.

Initial metadata inspection from the canonical repository (rather than the target
worktree) suggested an absent `.cjs` export. Target-f338 inspection and installed
consumer execution disproved that suspicion; no unnecessary package fix was made.

No core/security/workflow source edits, package publication, merge, deployment,
or cloud mutation. Exact-head GitHub CI and independent Antigravity qualification
remain integration-owner gates. Production remains NO-GO.
