# WhitePact Global Entity & Trust Graph (Global Directory)

## Doctrine

Global Directory supplies **evidence-backed identity and relationship intelligence** to humans, agents, and governance policy. It does **not** supply execution authority.

`KNOWLEDGE != AUTHORITY`

## Architecture

- **Storage:** PostgreSQL relational graph (`global_directory_*` tables, migration `0062`)
- **Resolution:** `GlobalDirectoryService.resolve_entity` — normalization → identifier extraction → local lookup → bounded fixture/public discovery
- **Claims:** Atomic predicates with `EvidenceState` (VERIFIED_FACT, INFERRED_SIGNAL, CONFLICTING_EVIDENCE, STALE, UNKNOWN)
- **Provenance:** Sources → claim evidence → claims → entities
- **Governance bridge:** `build_governance_context` returns risk posture only
- **MCP:** Eight read-only `global_directory.*` tools (production registry count +8)
- **HTTP:** `/api/v1/global-directory/*`

## Privacy & security

- Global scope: `GLOBAL_PUBLIC_EVIDENCE` only in V1 persistence path
- Suppression hooks: `global_directory_suppressions`
- External fetch uses `net.egress` fail-closed validation
- Discovery budgets in `discovery/budgets.py`

## Live discovery

Without configured external search providers, non-catalog queries return `LIVE DISCOVERY EXTERNAL DEPENDENCY`. Integration tests use `fixtures/demo_catalog.json` through the same pipeline.
