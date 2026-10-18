# SDK and framework consumer acceptance

External package consumers: **3PASS/0SKIP,109.31seconds**, at implementationd9bd5b30.
`tests/test_wave1_package_install.py` built a Python wheel and installed it into
a fresh consumer environment, packed TypeScript and loaded external ESM/CommonJS
consumers, and built/executed the Go consumer in a network-disabled local container.
Negative bearer-transport assertions ran. No package published. Receipt:
`/private/tmp/apex-sdk-external-consumers-complete.log`.

The initial SDK harness lacked NumPy; it was an environment collection error,
not a failed consumer. The passing run supplied existing harness dependencies;
the package tests' child environments remain independently installed/sanitized.

## Real pinned framework objects, local contract endpoints

- Wave1: **24PASS/0SKIP,24.86seconds**. langchain1.4.4, langgraph1.2.14,
  openai-agents0.23.1, google-adk2.11.0, resolved openai3.31.0.
  `/private/tmp/apex-wave1-qualified.log`.
- CrewAI/LlamaIndex: **22PASS/0SKIP,27.62seconds**. crewai1.15.28,
  llama-index-core0.14.25, resolved openai2.54.0.
  `/private/tmp/apex-crewai-qualified.log`.

Commands use separate disposable Python environments, `PYTHONPATH=src:sdk/python:.`,
and the repository's unchanged test files. Real framework tool/checkpoint objects
call controlled local contract endpoints. This proves integration and outcome/
error/cancellation preservation, not external model verification, root authority
or actual privileged execution. No provider keys or model calls used.

The first combined environment run recorded14PASS/32SKIP because optional packages
were missing; those skips are retained as a distinct initial run. Separate pinned
environments removed them. Early environment collection/setup errors (NumPy,
scikit-learn, asgi-lifespan, PyOTP/core fixtures) were resolved by supplying the
actual core test dependencies; no assertions or fixtures were disabled.

## APEX-SDK-02 — combined environment BLOCKED

The two repository-pinned matrices cannot currently be installed together:
CrewAI1.15.28 requires openai>=2.30,<3, while openai-agents0.23.1 requires the
incompatible3.x line. Resolver receipt `/private/tmp/apex-framework-dependencies.log`.
Pins were not changed to force success. Separate supported environments pass;
co-installation remains an explicit compatibility limitation. No claim of one
universal shared environment or transitive release lock is made.
