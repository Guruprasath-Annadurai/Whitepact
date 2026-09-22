# NLTK (PYSEC-2026-3740) — production scope

## Dependency path

- Optional extra only: `[project.optional-dependencies] sentiment = ["nltk>=3.10.0"]` in `pyproject.toml`.
- Not included in default `[dashboard]` or core install.

## Production artifact check

```bash
pip install .
pip show nltk  # must report "Package(s) not found"
```

Install with dashboard extra (no sentiment):

```bash
pip install ".[dashboard]"
pip show nltk  # must still be absent
```

## Claim

**NOT PRESENT IN PRODUCTION ARTIFACT — OPTIONAL EXTRA REMAINS AFFECTED**

Development environments that install `.[sentiment]` may pull `nltk 3.10.3` until a fixed upstream release is available.
