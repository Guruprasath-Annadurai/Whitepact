# Contributing to BiasBuster

Thanks for your interest in improving BiasBuster. Contributions are welcome — bug reports, new probes, provider integrations, documentation fixes, anything that makes the framework better.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Writing a New Probe](#writing-a-new-probe)
- [Adding a Provider](#adding-a-provider)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Style](#code-style)

---

## Getting Started

Fork the repository and clone your fork:

```bash
git clone https://github.com/<your-username>/ResponsibleAi.git
cd ResponsibleAi
```

Set the upstream remote so you can pull future changes:

```bash
git remote add upstream https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
```

---

## Development Setup

BiasBuster uses [hatch](https://hatch.pypa.io/) for builds but a plain virtual environment is fine for development.

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
```

This installs the package in editable mode together with all development dependencies (pytest, coverage, ruff, mypy, etc.).

To pick up the NLTK data used for sentiment scoring:

```python
import nltk
nltk.download("vader_lexicon")
```

---

## Running Tests

```bash
pytest                          # full suite with coverage report
pytest tests/test_scoring.py   # single file
pytest -k "gender"              # keyword filter
```

Coverage is measured automatically. The project targets 80 % overall; new code should ship with tests that keep coverage at or above the current level.

---

## Writing a New Probe

All probes live in `src/biasbuster/probes/`. The minimum contract is defined in `core/base_probe.py`.

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

A *variant* is one demographic substitution per template (e.g., different names, ages, or group labels). Collect `VariantResponse` objects, score them with `compute_combined_score`, and wrap everything in a `TemplateResult`.

### 3. Neutralize before scoring

Strip any surface-form demographic tokens from responses before computing TF-IDF divergence. See `probes/_utils.py` and the per-probe `_neutralize_*` functions for the pattern.

### 4. Expose via the public API

Add the import and `__all__` entry in `src/biasbuster/__init__.py` and register the probe in `src/biasbuster/cli.py`.

### 5. Write tests

Create `tests/test_<probe_name>.py`. Aim for at least:

- A `TestNeutralize*` class covering the neutralizer edge cases.
- An integration test with a biased mock provider that should fail.
- An integration test with a neutral mock provider that should pass.
- Shape tests confirming the number of template results and variant responses.

---

## Adding a Provider

Provider adapters live in `src/biasbuster/providers/`. Each must implement `BaseProvider`:

```python
class BaseProvider:
    @property
    def name(self) -> str: ...
    @property
    def model_name(self) -> str: ...
    async def complete(self, request: CompletionRequest) -> CompletionResponse: ...
```

The `CompletionRequest` carries `prompt`, optional `system_prompt`, `max_tokens`, and `temperature`. `CompletionResponse` carries `text`, `model`, `provider`, `input_tokens`, and `output_tokens`.

Guard the third-party import so users who haven't installed that SDK get a clear `ImportError`:

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

Write unit tests using `unittest.mock.AsyncMock` — see `tests/test_openai_provider.py` or `tests/test_anthropic_provider.py` for the pattern.

---

## Pull Request Guidelines

1. **One concern per PR.** A new probe, a bug fix, a documentation update — keep them separate.
2. **Tests are required.** PRs that reduce coverage will be asked to add tests before merging.
3. **Keep the diff small.** Refactors that touch many unrelated files are harder to review. If you want to clean something up, open a separate PR.
4. **Describe the change.** Your PR description should explain *why* the change is needed, not just what it does.
5. **CI must be green.** The GitHub Actions workflow runs the full test suite across Python 3.10, 3.11, and 3.12. Fix any failures before requesting review.

---

## Code Style

The project uses [ruff](https://docs.astral.sh/ruff/) for linting and formatting. Run it before committing:

```bash
ruff check src/ tests/
ruff format src/ tests/
```

Type annotations are required for all public functions. `mypy` is configured in `pyproject.toml`:

```bash
mypy src/
```

No external comments about *what* code does — identifiers should be self-explanatory. Comments are reserved for non-obvious *why* decisions.

---

## Questions

Open a [GitHub Discussion](https://github.com/Guruprasath-Annadurai/ResponsibleAi/discussions) for design questions or feature proposals. Use [Issues](https://github.com/Guruprasath-Annadurai/ResponsibleAi/issues) for bugs and concrete feature requests.
