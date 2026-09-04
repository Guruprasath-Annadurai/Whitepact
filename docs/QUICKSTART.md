# WhitePact five-minute quickstart

This path uses the published `1.2.6` package, needs no provider API key, and
produces a real governance decision locally.

## 1. Install in a clean environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install "rai-governance-platform[mcp]==1.2.6"
```

For current source instead:

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact.git
cd Whitepact
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[mcp]"
```

## 2. Run the local runtime-authority demo

From a source checkout:

```bash
python examples/09_runtime_authority_demo.py
```

The real deterministic gateway returns `REQUIRE_APPROVAL`; the example does
not execute the proposed payment and prints an `EvidenceRecord` summary with
the reason code. No output is prerecorded.

## 3. Discover the MCP server

Start the MCP Inspector against the installed stdio command:

```bash
npx -y @modelcontextprotocol/inspector whitepact-mcp
```

In the Inspector, connect, run `tools/list`, and call the read-only
`rai_health` tool with `{}`. For WhitePact `1.2.6`, expect **30 tools** and
**20 advertised resources** (10 underlying resources under both `whitepact://`
and legacy `rai://` URIs).

The Inspector step requires Node.js. From a source checkout, the same protocol
check can be run without a browser:

```bash
python scripts/mcp_stdio_smoke.py
```

It initializes the real stdio server, lists tools and resources, and calls only
`rai_health`. Otherwise configure any MCP client to launch `whitepact-mcp` using
the configuration in [`docs/mcp/README.md`](mcp/README.md).

## What this proves

- the package imports and the runtime gateway makes a real five-way decision;
- the proposed action is held before execution;
- an evidence object explains the decision without storing argument values;
- an MCP client can initialize the local server, discover its capabilities,
  and invoke a safe tool.

It does not prove production deployment, provider-specific UI compatibility,
or external certification. Those boundaries are tracked in the
[`compatibility matrix`](integrations/PLATFORM_COMPATIBILITY.md) and
[`trust status`](../compliance/WHITEPACT_TRUST_STATUS.md).
