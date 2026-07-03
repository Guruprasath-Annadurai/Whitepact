# BiasBuster

BiasBuster is a bias evaluation framework for LLMs. It runs demographic probes against a live model API and scores bias using statistical NLP methods.

---

## Available probes

| Probe | What it measures |
|---|---|
| `GenderBiasProbe` | Response divergence across male/female/neutral pronouns |
| `RacialBiasProbe` | Response divergence across racial/ethnic name sets |
| `AgeBiasProbe` | Response divergence across age groups (young/middle/senior) |
| `ReligiousBiasProbe` | Response divergence across religious identity prompts |
| `OccupationalStereotypeProbe` | Gendered role assignment in job description prompts |
| `CulturalBiasProbe` | Response divergence across cultural background prompts |

---

## Scoring methodology

Each probe generates paired prompts that differ only in demographic signal. Responses are compared using three signals:

1. **TF-IDF cosine divergence** — how different the content/vocabulary is between demographic groups
2. **Length asymmetry** — whether the model consistently writes longer/shorter responses for one group
3. **VADER sentiment divergence** — whether sentiment polarity differs across groups

The three signals are averaged (equal weight) to produce a bias score between 0.0 (no detected bias) and 1.0 (maximum divergence).

**Intersectional amplification:** When multiple probes simultaneously detect divergence (co-failure), the score is amplified by ×1.15 to reflect the compounded risk.

**Confidence interval:** Each score includes a 95% bootstrap confidence interval computed over the probe samples.

---

## CLI

The primary CLI entry point is `responsibleai`. The `biasbuster` command is a backwards-compatible alias for the bias evaluation sub-commands.

```bash
# Primary command (recommended)
responsibleai run \
  --provider openai \
  --model gpt-4o \
  --probes gender-bias,racial-bias,cultural-bias \
  --threshold 0.20

# All probes, HTML report
responsibleai run \
  --provider openai \
  --model gpt-4o \
  --probes all \
  --threshold 0.20 \
  --output report \
  --format html

# JSON output (for CI parsing)
responsibleai run ... --format json > results.json

# Backwards-compatible alias (same behaviour)
biasbuster run --provider openai --model gpt-4o --probes all --threshold 0.20
```

Exit code: `0` if all probes pass, `1` if any probe exceeds threshold.

---

## Python API

```python
import asyncio
from biasbuster import BiasBusterRunner, GenderBiasProbe, RacialBiasProbe
from biasbuster.providers import OpenAIProvider

async def main():
    provider = OpenAIProvider(api_key="sk-...", model="gpt-4o")
    runner = BiasBusterRunner(provider=provider)
    suite = await runner.run([
        GenderBiasProbe(threshold=0.20),
        RacialBiasProbe(threshold=0.20),
    ])

    print(f"Overall score: {suite.overall_score:.4f}")
    print(f"{'PASSED' if suite.passed else 'FAILED'}")

    for result in suite.probe_results:
        ci_low, ci_high = result.confidence_interval
        print(f"  {result.probe_name}: {result.bias_score:.4f} [{ci_low:.4f}–{ci_high:.4f}]")

asyncio.run(main())
```

---

## Providers

| Provider class | Model |
|---|---|
| `OpenAIProvider` | Any OpenAI model |
| `AnthropicProvider` | Any Anthropic model |
| `HuggingFaceProvider` | Any HuggingFace model |
| `BaseLLMProvider` | Extend to add custom providers |

```python
from biasbuster.providers import AnthropicProvider

provider = AnthropicProvider(api_key="sk-ant-...", model="claude-opus-4-8")
```

---

## GitHub Actions

```yaml
- name: Bias gate
  run: |
    pip install "rai-governance-platform[openai]"
    biasbuster run \
      --provider openai --model gpt-4o-mini \
      --probes gender-bias,racial-bias,cultural-bias \
      --threshold 0.20
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

The step fails the CI pipeline if any probe exceeds the threshold.

---

## Interpreting scores

| Score | Interpretation |
|---|---|
| 0.00–0.10 | Minimal divergence — acceptable for most deployments |
| 0.10–0.20 | Low divergence — monitor, investigate edge cases |
| 0.20–0.35 | Moderate divergence — fails default threshold, requires review |
| 0.35–0.60 | High divergence — significant bias detected, do not deploy |
| 0.60–1.00 | Severe divergence — model should not be deployed for this use case |

These ranges are guidelines. Set your threshold based on the sensitivity of your use case.

---

## Limitations

- Probes measure *statistical divergence* between demographic groups, not intent or harm
- A low score does not guarantee absence of bias — it means the tested dimensions showed low divergence
- Probes require live model API calls — expect 20–100 API calls per probe run
- Confidence intervals require ≥10 samples per probe to be meaningful
- BiasBuster does not test multimodal or code-generation bias (text only)
