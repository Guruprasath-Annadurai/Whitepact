# Hostile input boundaries

Target: `http://127.0.0.1:18765`

| case | result |
|---|---|
| huge_json | HTTP_422 |
| long_string | HTTP_405 |

**Verdict:** **PARTIAL** — sample rejects; not exhaustive max-body characterization.
