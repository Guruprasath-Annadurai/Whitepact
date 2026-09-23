# Global Directory — architecture audit (base `acddae1`)

## Existing primitives (reuse, do not duplicate)

| Area | Location | Relationship to Global Directory |
| --- | --- | --- |
| Trust Index / passports | `db/passport_repository.py`, `/api/trust-index/*` | Open citability standard for models; **not** entity resolution |
| Trust Fabric principal directory | `trust_fabric/directory.py` | **Tenant-scoped** IAM identifiers; not global public graph |
| Trust Fabric authority graph | `trust_fabric/authority_graph.py` | **Execution authority**; Global Directory supplies **evidence only** |
| Public incident reports | `db/public_incident_repository.py` | Global security incidents; linkable as trust signals |
| Supply chain scanner | `supplychain/scanner.py` | Package advisories; complementary to `SOFTWARE_PACKAGE` entities |
| Safe egress / SSRF | `net/egress.py` | **Required** for all discovery HTTP |
| Governance gateway | `governance/gateway.py` | Consumes risk context; directory bridge is read-only input |
| MCP tool registry | `mcp/tools.py` | New read-only `global_directory.*` tools appended with updated counts |
| Sovereign simulation | `sovereign/*` | Zero-effect; directory is separate durable global evidence layer |

## New capability

`responsibleai/global_directory/` — provenance-aware **Global Entity & Trust Graph** with PostgreSQL storage (migration `0062`), HTTP API, MCP tools, and dashboard UI **Global Directory**.

**Invariant:** `KNOWLEDGE != AUTHORITY` — directory lookups never mint grants or bypass policy.
