## What this PR does

<!-- One paragraph. Which governance pillar does this touch? -->

## Motivation

<!-- Why is this needed? What problem does it solve? -->

## Changes

<!-- Bullet list of files changed and what was changed -->

## Tests

- [ ] New tests added / existing tests updated
- [ ] All tests pass locally (`pytest`)
- [ ] Coverage is maintained or improved

## Checklist

- [ ] Code follows the existing style (no docstrings on self-explanatory code, type hints everywhere)
- [ ] No raw data or PII is stored or logged
- [ ] Async methods are properly `async def`
- [ ] New public APIs are added to the relevant `__init__.py`
- [ ] If adding a new probe, it has a `default_threshold` and at least 4 `DEFAULT_TEMPLATES`
- [ ] If adding a new DP mechanism, it includes the formal privacy cost in the docstring
