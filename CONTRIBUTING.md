# Contributing to WhitePact

WhitePact (package name `rai-governance-platform`, repository still hosts the
original `biasbuster`/`privacylabel`/`responsibleai` packages plus the new
`whitepact` alias — see `MIGRATION_WHITEPACT_V2.md`) is an AI governance and
runtime-authority platform: trust scoring, guardrails, compliance mapping,
bias evaluation, a governance decision engine (ALLOW / ALLOW_WITH_REDACTION /
REQUIRE_APPROVAL / DENY / QUARANTINE), and an MCP server exposing all of it as
27 tools. Contributions are welcome — bug reports, new probes/checks, provider
integrations, documentation fixes, governance-policy improvements, anything
that makes the platform more correct or more honest about what it does.

By participating, you're expected to follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
See [GOVERNANCE.md](GOVERNANCE.md) for how decisions get made — this is
a founder-led project (Guruprasath Annadurai), not a claim of a committee
that doesn't exist.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Repository Layout](#repository-layout)
- [Running Tests](#running-tests)
- [Engineering Principles](#engineering-principles)
- [Writing a New Bias Probe](#writing-a-new-bias-probe)
- [Adding a Provider](#adding-a-provider)
- [Working on the Governance Core](#working-on-the-governance-core)
- [Working on the MCP Server](#working-on-the-mcp-server)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Style](#code-style)
- [Questions](#questions)

---

## Getting Started

Fork the repository and clone your fork:

```bash
git clone https://github.com/<your-username>/Whitepact.git
cd Whitepact
```

Set the upstream remote so you can pull future changes:

```bash
git remote add upstream https://github.com/Guruprasath-Annadurai/Whitepact.git
```

---

## Development Setup

The project uses [hatch](https://hatch.pypa.io/) for builds but a plain
virtual environment is fine for development.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

This installs the package in editable mode together with all development
dependencies (pytest, coverage, ruff, mypy, etc.). To pick up the NLTK data
used for BiasBuster's sentiment scoring:

```python
import nltk
nltk.download("vader_lexicon")
```

---

## Repository Layout

| Path | What lives there |
|---|---|
| `src/biasbuster/` | Bias evaluation probes, CLI, provider adapters |
| `src/privacylabel/` | Federated differential-privacy labeling |
| `src/responsibleai/` | The governance platform: dashboard, MCP server, trust/compliance/guardrails engines, governance decision core, DB layer |
| `src/responsibleai/governance/` | `WhitePactRuntimeGateway`, risk tiering, policy engine, evidence hash chain, approval workflow — see `SPEC.md` Sections 4-8 |
| `src/responsibleai/mcp/` | MCP server: tool/resource definitions, transports (stdio, Streamable HTTP, legacy SSE), OAuth/OIDC resource-server auth |
| `src/responsibleai/supplychain/` | MCP trust/supply-chain scanner (typosquat detection, description scanning, incident cross-reference) |
| `src/whitepact/` | Thin alias package re-exporting `responsibleai` under the new name — see `MIGRATION_WHITEPACT_V2.md` Section 3 |
| `tests/` | All tests, one file per module roughly mirroring `src/` |
| `compliance/` | Self-assessments, methodology docs, DPA/SLA templates — treat as living documents, not marketing copy |
| `helm/` | Kubernetes Helm chart for the dashboard and hosted MCP transport |

`SPEC.md` is the current architecture contract. `MIGRATION_WHITEPACT_V2.md` is
the active, phase-by-phase migration log — read it before touching anything
that looks like a rename or a compatibility shim, so you don't duplicate or
contradict prior decisions.

---

## Running Tests

```bash
pytest                          # full suite with coverage report
pytest tests/test_scoring.py    # single file
pytest -k "gender"              # keyword filter
pytest tests/test_mcp_server.py # MCP server tests
```

Coverage is measured automatically. As of this writing the suite is
1,538 tests at 85% coverage — new code should ship with tests that keep
coverage at or above the current level, not just "some tests."

---

## Engineering Principles

These are non-negotiable for any PR touching `src/responsibleai/` or
`src/biasbuster/`, not just guidance:

1. **Inspect before changing.** Read the current code and, if relevant, the
   corresponding section of `SPEC.md`/`MIGRATION_WHITEPACT_V2.md` before
   modifying it.
2. **Never fabricate status.** Don't write comments, docs, or commit
   messages claiming something is "production-ready," "SOC 2 compliant," or
   "penetration tested" unless there's a real artifact in the repo backing
   that claim.
3. **Backward compatibility over breaking changes.** Renames get an alias
   (env var, package, CLI entry point, REST route, MCP resource URI) — see
   `MIGRATION_WHITEPACT_V2.md` Section 4 for the deprecation-timeline
   pattern already in use.
4. **Every functional change needs a test.** Every migration or rename needs
   a line in `MIGRATION_WHITEPACT_V2.md` and, where relevant, `CHANGELOG.md`.
5. **Don't weaken a security control to make CI green.** Auth, RBAC, tenant
   isolation, encryption, input validation, and audit logging are not
   negotiable line items — fix the real problem instead.
6. **Prefer deterministic checks over LLM-based ones** where a deterministic
   check can do the job — see `DETERMINISTIC_VS_PROBABILISTIC.md`.
7. **Don't invent enterprise process that doesn't exist.** No fake team
   roles, no fake steering committee — see `GOVERNANCE.md`.

---

## Writing a New Bias Probe

All probes live in `src/biasbuster/probes/`. The minimum contract is defined
in `core/base_probe.py`.

### 1. Subclass `BaseProbe`

```python
from biasbuster.core.base_probe import BaseProbe
from biasbuster.core.result import ProbeResult, TemplateResult, VariantResponse
from biasbuster.core.scoring import compute_combined_score, bootstrap_confidence_interval
from biasbuster.providers.base import BaseProvider

class MyBiasProbe(BaseProbe):
    name = "my-bias"
    description = "Detects X bias in LLM responses."
    default_threshold = 0.20

    DEFAULT_TEMPLATES: list[str] = [
        "Write a summary about {variant_token}.",
    ]

    async def run(self, provider: BaseProvider) -> ProbeResult:
        ...
```

### 2. Define your variants

A *variant* is one demographic substitution per template (e.g., different
names, ages, or group labels). Collect `VariantResponse` objects, score them
with `compute_combined_score`, and wrap everything in a `TemplateResult`.

### 3. Neutralize before scoring

Strip any surface-form demographic tokens from responses before computing
TF-IDF divergence. See `probes/_utils.py` and the per-probe
`_neutralize_*` functions for the pattern.

### 4. Expose via the public API

Add the import and `__all__` entry in `src/biasbuster/__init__.py` and
register the probe in `src/biasbuster/cli.py`.

### 5. Write tests

Create `tests/test_<probe_name>.py`. Aim for at least:

- A `TestNeutralize*` class covering the neutralizer edge cases.
- An integration test with a biased mock provider that should fail.
- An integration test with a neutral mock provider that should pass.
- Shape tests confirming the number of template results and variant responses.

---

## Adding a Provider

Provider adapters live in `src/biasbuster/providers/`. Each must implement
`BaseProvider`:

```python
class BaseProvider:
    @property
    def name(self) -> str: ...
    @property
    def model_name(self) -> str: ...
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
```

The `CompletionRequest` carries `prompt`, optional `system_prompt`,
`max_tokens`, and `temperature`. `CompletionResponse` carries `text`, `model`,
`provider`, `input_tokens`, and `output_tokens`.

Guard the third-party import so users who haven't installed that SDK get a
clear `ImportError`:

```python
try:
    from some_sdk import AsyncClient
except ImportError:
    AsyncClient = None  # type: ignore[assignment, misc]

class MySdkProvider(BaseProvider):
    def __init__(self, api_key: str, ...):
        if AsyncClient is None:
            raise ImportError("Install the SDK: pip install some-sdk")
        self._client = AsyncClient(api_key=api_key)
```

Write unit tests using `unittest.mock.AsyncMock` — see
`tests/test_openai_provider.py` or `tests/test_anthropic_provider.py` for
the pattern.

---

## Working on the Governance Core

`src/responsibleai/governance/` implements the ALLOW /
ALLOW_WITH_REDACTION / REQUIRE_APPROVAL / DENY / QUARANTINE decision model
described in `SPEC.md` Sections 4-8:

- `risk.py` — `TOOL_RISK_TIERS`, a hardcoded, tested-against-drift table
  mapping each MCP tool to a risk tier. If you add or rename an MCP tool,
  update this table and its drift test (`tests/test_governance_risk.py`) in
  the same PR.
- `policy.py` — first-match-wins policy rules (`ALLOW`/`DENY`/
  `REQUIRE_APPROVAL` effects only — don't add new effects without a real,
  tested reason, per `SPEC.md`'s decision-model contract).
- `evidence.py` / `db/evidence_repository.py` — hash-chained
  `EvidenceRecord`. Never store raw argument values here, only field-name
  keys — this is a deliberate privacy boundary, not an oversight.
- `approval.py` / `db/approval_repository.py` — race-safe approval
  resolution. Any change to the `PENDING → APPROVED/DENIED` transition needs
  a concurrency test, not just a happy-path one.
- `WhitePactRuntimeGateway.evaluate()` is deterministic — no LLM call in the
  decision path itself. If a change would require calling out to a model to
  decide, stop and read `DETERMINISTIC_VS_PROBABILISTIC.md` first.

---

## Working on the MCP Server

`src/responsibleai/mcp/` supports three transports: stdio, Streamable HTTP
(`/mcp`), and legacy HTTP+SSE (`/sse` + `/messages/`, kept for older clients).
When adding or changing a tool:

1. Update `tools.py`'s `TOOL_DEFS` (structured input/output schema).
2. Update `governance/risk.py`'s `TOOL_RISK_TIERS` if the tool is
   governance-relevant.
3. Update `server.json`'s `_meta` tool count and `tests/test_server_json.py`
   if the total tool count changes.
4. Add integration tests under `tests/test_mcp_server.py` or the relevant
   transport-specific test file.
5. Update the tool table in `README.md`.

---

## Pull Request Guidelines

1. **One concern per PR.** A new probe, a bug fix, a governance-policy
   change, a documentation update — keep them separate.
2. **Tests are required.** PRs that reduce coverage will be asked to add
   tests before merging.
3. **Keep the diff small.** Refactors that touch many unrelated files are
   harder to review. If you want to clean something up, open a separate PR.
4. **Describe the change.** Your PR description should explain *why* the
   change is needed, not just what it does.
5. **CI must be green.** The GitHub Actions workflow runs the full test
   suite, `ruff check`, and `mypy`. Fix any failures before requesting
   review.
6. **No new governance feature unless required.** Don't add a new decision
   type, a new tool, or a new compliance claim just because it's easy to
   plug in — every governance-relevant addition should trace back to a real
   requirement, per `SPEC.md`.

---

## Code Style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and
formatting. Run it before committing:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Type annotations are required for all public functions. `mypy` is configured
in `pyproject.toml`:

```bash
mypy src/responsibleai src/biasbuster
```

No comments about *what* code does — identifiers should be self-explanatory.
Comments are reserved for non-obvious *why* decisions.

---

## Questions

Open a [GitHub Discussion](https://github.com/Guruprasath-Annadurai/Whitepact/discussions)
for design questions or feature proposals. Use
[Issues](https://github.com/Guruprasath-Annadurai/Whitepact/issues) for bugs
and concrete feature requests. Security vulnerabilities go to
[SECURITY.md](SECURITY.md)'s disclosure email, never a public issue.
