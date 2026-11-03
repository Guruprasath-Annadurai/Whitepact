# Antigravity Independent Qualification Instructions — A005 Community Core

## Candidate under audit

- **Package:** `whitepact-community==0.1.0a1`
- **Path:** `packages/whitepact-community/`
- **Engineering branch:** `cursor/track-a-community-core-a005-0e59`
- **Parent baseline:** Public WhitePact PR #2 head `19f8d4b6b570d03baa87845867e5f9b268b6d6e6`
- **Private internal PRs #251/#254 / Issue #252:** not readable from this agent environment; re-verify against `whitepact-internal` when access is available.

## Required exact-head checks

1. Confirm git ancestry: community commits descend from the reviewed OSS candidate, not from an overwritten newer head.
2. Build wheel + sdist from `packages/whitepact-community` only.
3. Inspect **archive members**, not merely `pyproject.toml`.
4. Run `python scripts/verify_package_boundary.py dist/*.whl dist/*.tar.gz` — must exit 0.
5. Install into a clean venv (Python 3.11 and 3.12).
6. Prove:
   - `import whitepact_community` succeeds without importing `responsibleai`/`stripe`/`biasbuster`
   - `wpc version` / `wpc --help` succeed
   - `wpc run-local` completes a genuine ALLOW path
   - `wpc deny-demo` exits 3 with DENY
   - MCP `initialize` + `tools/list` + authorized `wpc_local_echo` + unauthorized policy evaluate
   - Expired/revoked authority denial
   - Authorization replay denial
   - Evidence chain verifies
   - Enterprise capability calls return unavailable (exit 4), never success
7. Confirm default-deny exporter refuses empty allowlist export.
8. Confirm denylist fails closed if a private module is injected into an archive.
9. Do **not** treat GitHub Actions as green if jobs never ran (account spending limit).
10. Do **not** expand publication allowlist.

## Pass criteria for Cursor verdict endorsement

Only endorse `TRACK_A_COMMUNITY_ENGINEERING_READY_FOR_INDEPENDENT_QUALIFICATION` if all of the above pass on the exact candidate SHA.

Otherwise return `TRACK_A_REMEDIATION_REQUIRED` with exact failing command evidence.
