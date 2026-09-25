# Wheel install acceptance

```json
{
  "build": {
    "cmd": [
      "/workspace/.venv/bin/python",
      "-m",
      "build",
      "-w",
      "-o",
      "/tmp/tmphzwj6hep/wheels",
      "/workspace"
    ],
    "exit": 0,
    "stdout": "Successfully built rai_governance_platform-1.3.1-py3-none-any.whl\n",
    "stderr": "\u001b[93mWARNING\u001b[0m Both NO_COLOR and FORCE_COLOR environment variables are set, disabling color\n* Creating isolated environment: venv+pip...\n* Installing packages in isolated environment:\n  - hatchling==1.32.0\n* Getting build dependencies for wheel...\n* Installed build dependency versions:\n  - hatchling==1.32.0\n* Building wheel...\n"
  },
  "wheel_count": 1,
  "install": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/pip",
      "install",
      "/tmp/tmphzwj6hep/wheels/rai_governance_platform-1.3.1-py3-none-any.whl[dashboard,postgres]",
      "-q"
    ],
    "exit": 0,
    "stdout": "",
    "stderr": ""
  },
  "version_import": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/python",
      "-c",
      "import responsibleai; print(responsibleai.__version__)"
    ],
    "exit": 0,
    "stdout": "1.3.1\n",
    "stderr": ""
  },
  "whitepact_version": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/whitepact",
      "--version"
    ],
    "exit": 0,
    "stdout": "whitepact, version 1.3.1\n",
    "stderr": ""
  },
  "whitepact_help": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/whitepact",
      "--help"
    ],
    "exit": 0,
    "stdout": "Usage: whitepact [OPTIONS] COMMAND [ARGS]...\n\n  WhitePact CLI \u2014 bias testing and Sovereign governance diagnostics.\n\nOptions:\n  --version  Show the version and exit.\n  --help     Show this message and exit.\n\nCommands:\n  authority\n  capsule\n  ci\n  connect\n  context\n  doctor\n  explain\n  gauntlet\n  init\n  list-probes  List all available bias probes.\n  policy\n  prove\n  replay\n  run          Run bias probes against an LLM provider.\n  sandbox\n  shadow\n  simulate\n  sovereign    Sovereign governance diagnostics (read/simulate only).\n  trace\n  xray\n",
    "stderr": ""
  },
  "whitepact_doctor": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/whitepact",
      "doctor",
      "--json"
    ],
    "exit": 0,
    "stdout": "{\"checks\": [{\"name\": \"protocol\", \"result\": \"PASS\"}, {\"name\": \"capabilities\", \"result\": \"PASS\", \"detail\": \"\"}, {\"name\": \"context\", \"result\": \"WARN\", \"detail\": \"no --org\"}]}\n",
    "stderr": ""
  },
  "alembic_ini_from_tmp": {
    "cmd": [
      "/tmp/tmphzwj6hep/venv/bin/python",
      "-c",
      "from responsibleai.db.alembic_paths import resolve_alembic_ini; print(resolve_alembic_ini())"
    ],
    "exit": 0,
    "stdout": "/tmp/tmphzwj6hep/venv/lib/python3.12/site-packages/alembic.ini\n",
    "stderr": ""
  },
  "twine_check": {
    "cmd": [
      "/workspace/.venv/bin/python",
      "-m",
      "twine",
      "check",
      "/tmp/tmphzwj6hep/wheels/rai_governance_platform-1.3.1-py3-none-any.whl"
    ],
    "exit": 1,
    "stdout": "",
    "stderr": "/workspace/.venv/bin/python: No module named twine\n"
  },
  "wheel_has_alembic_ini": true,
  "wheel_has_migrations": true,
  "verdict": "PASS"
}
```
