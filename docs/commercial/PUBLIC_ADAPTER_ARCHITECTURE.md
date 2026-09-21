# Public marketplace adapter architecture

```
CONTROLLED CORE (hosted API / MCP, authenticated)
        ↓
THIN PUBLIC ADAPTER (manifest, auth config, client wrapper, docs)
        ↓
EXTERNAL MARKETPLACE (ChatGPT, Claude, Cursor, Gemini — submission frozen until V1 gate)
```

Adapters MUST NOT embed future private enforcement logic. They call the same Bearer-authenticated `/mcp` surface documented in `distribution/platform-metadata.yaml`.
