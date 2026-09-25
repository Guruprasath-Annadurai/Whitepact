# API contract / OpenAPI compatibility (v1.3.1 addendum)

| Field | Value |
|-------|-------|
| Current HEAD export | FastAPI `TestClient` → `GET /api/openapi.json` |
| HTTP status | **200** |
| Payload size | ~229 KB |
| **Path count** | **245** |
| OpenAPI version | 3.1.x (from live export) |
| Baseline tag | `v1.3.0-rc-final` (git tag present) |

## Machine diff vs v1.3.0

**NOT COMPLETED** in this closure VM: exporting OpenAPI from the tagged tree in the same runtime environment was not executed. A field-level diff (removed endpoints, renamed fields, new required fields, enum changes) requires a dual-export job in CI or a release engineer checkout.

## Classification (manual policy)

| Change class | Status |
|--------------|--------|
| Intentional breaking changes | **UNKNOWN** until diff is run |
| Accidental breaking changes | **UNKNOWN** until diff is run |
| Documented stable prefixes (`/api/v1/*` rewrite) | **STATICALLY VERIFIED** in `app.py` middleware |

## Verdict

**PARTIAL** — current contract captured; v1.3.0-rc-final comparison **pending automated diff**.
