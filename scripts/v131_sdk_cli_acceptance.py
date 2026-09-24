# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run v1.3.1 SDK + CLI acceptance checks; prints JSON summary to stdout."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str], *, cwd: Path | None = None, env: dict | None = None) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=cwd or ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return {
        "cmd": cmd,
        "exit": proc.returncode,
        "stdout": proc.stdout[-4000:],
        "stderr": proc.stderr[-4000:],
    }


def main() -> int:
    py = sys.executable
    results: dict[str, object] = {}

    # Python SDK wheel + import
    with tempfile.TemporaryDirectory() as td:
        wheel_dir = Path(td)
        results["python_sdk_wheel"] = run(
            [py, "-m", "pip", "wheel", str(ROOT / "sdk" / "python"), "-w", str(wheel_dir), "-q"]
        )
        wheels = list(wheel_dir.glob("*.whl"))
        results["python_sdk_wheel_count"] = len(wheels)
        if wheels:
            venv = Path(td) / "venv"
            run([py, "-m", "venv", str(venv)])
            pip = venv / "bin" / "pip"
            pyvenv = venv / "bin" / "python"
            results["python_sdk_install"] = run([str(pip), "install", str(wheels[0]), "-q"])
            results["python_sdk_import"] = run(
                [str(pyvenv), "-c", "from rai_client import RAIClient; print(RAIClient)"],
            )

    # TypeScript SDK build
    ts_dir = ROOT / "sdk" / "typescript"
    if (ts_dir / "package.json").is_file():
        results["typescript_npm_ci"] = run(["npm", "ci"], cwd=ts_dir)
        results["typescript_build"] = run(["npm", "run", "build"], cwd=ts_dir)
        ver = json.loads((ts_dir / "package.json").read_text())["version"]
        results["typescript_version"] = ver

    # Go SDK
    go_dir = ROOT / "sdk" / "go"
    if (go_dir / "go.mod").is_file():
        results["go_test"] = run(["go", "test", "./..."], cwd=go_dir)
        results["go_vet"] = run(["go", "vet", "./..."], cwd=go_dir)

    # CLI behavioral (not only --help)
    results["whitepact_version"] = run([py, "-m", "biasbuster.cli", "--version"])
    results["whitepact_scan_help"] = run([py, "-m", "biasbuster.cli", "scan", "--help"])
    results["whitepact_scan_missing_file"] = run(
        [py, "-m", "biasbuster.cli", "scan", "/nonexistent/path.txt"],
    )
    results["responsibleai_version"] = run(
        [py, "-c", "import responsibleai; print(responsibleai.__version__)"],
    )

    print(json.dumps(results, indent=2))
    failed = [
        k
        for k, v in results.items()
        if isinstance(v, dict)
        and v.get("exit", 0) != 0
        and k not in {"whitepact_scan_missing_file"}  # expected non-zero
    ]
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
