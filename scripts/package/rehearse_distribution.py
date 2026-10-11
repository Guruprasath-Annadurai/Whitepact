#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Local distribution rehearsal. Does not upload to PyPI, npm, or GHCR."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from dual_ownership import DualOwnershipError, assert_exclusive_code_ownership, write_wheel  # noqa: E402

CANDIDATES = (
    "rai-governance-platform",
    "whitepact",
    "whitepact-governance",
    "whitepact-platform",
)


def run(cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=cwd, env=env, check=True)


def pypi_status(name: str) -> str:
    url = f"https://pypi.org/pypi/{name}/json"
    try:
        with urllib.request.urlopen(url, timeout=20) as response:
            payload = json.load(response)
        version = payload.get("info", {}).get("version", "")
        return f"published version={version}"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "not-published"
        return f"http-{exc.code}"
    except Exception as exc:  # noqa: BLE001 — report and continue
        return f"error:{type(exc).__name__}"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def build_pair(out: Path) -> tuple[Path, Path]:
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "0"
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    run([sys.executable, "-m", "build", "--outdir", str(out)], cwd=ROOT, env=env)
    wheels = list(out.glob("*.whl"))
    sdists = list(out.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise SystemExit(f"expected one wheel and one sdist in {out}")
    return wheels[0], sdists[0]


def main() -> None:
    work = Path("/tmp/whitepact-dist-rehearsal")
    if work.exists():
        shutil.rmtree(work)
    work.mkdir()
    report = work / "report.txt"
    lines: list[str] = []

    lines.append("PYPI_NAME_CHECK")
    for name in CANDIDATES:
        status = pypi_status(name)
        lines.append(f"{name} {status}")
        print(f"pypi {name}: {status}", flush=True)

    first = work / "build-a"
    second = work / "build-b"
    wheel_a, sdist_a = build_pair(first)
    wheel_b, sdist_b = build_pair(second)
    same_wheel = sha256(wheel_a) == sha256(wheel_b)
    same_sdist = sha256(sdist_a) == sha256(sdist_b)
    lines.append(f"WHEEL_REPRODUCIBLE={same_wheel}")
    lines.append(f"SDIST_REPRODUCIBLE={same_sdist}")
    lines.append(f"WHEEL={wheel_a.name}")
    if not (same_wheel and same_sdist):
        raise SystemExit("rebuild hashes differ")

    venv = work / "venv"
    run([sys.executable, "-m", "venv", str(venv)])
    pip = venv / "bin" / "pip"
    py = venv / "bin" / "python"
    run([str(pip), "install", "--upgrade", "pip"])
    run([str(pip), "install", str(wheel_a)])
    run(
        [
            str(py),
            "-c",
            "import responsibleai, whitepact, biasbuster, privacylabel; "
            "print(responsibleai.__version__)",
        ]
    )
    for cmd in ("whitepact", "responsibleai", "biasbuster"):
        run([str(venv / "bin" / cmd), "--help"])
    run([str(venv / "bin" / "whitepact"), "info"])
    run(
        [
            str(py),
            "-c",
            "from responsibleai.mcp.server import main, main_http; "
            "assert callable(main) and callable(main_http)",
        ]
    )
    run([str(pip), "install", f"{wheel_a}[dashboard]"])
    run([str(py), "-c", "import responsibleai.dashboard.app"])
    run([str(pip), "uninstall", "-y", "rai-governance-platform"])
    run([str(pip), "install", str(wheel_a)])
    run([str(py), "-c", "import responsibleai, whitepact"])
    run([str(pip), "install", "--upgrade", str(wheel_b)])
    run([str(py), "-c", "import responsibleai, whitepact; import biasbuster"])

    rename = work / "rename-tree"
    shutil.copytree(
        ROOT,
        rename,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "dist",
            "htmlcov",
            ".terraform",
            "node_modules",
            ".pytest_cache",
            "__pycache__",
        ),
    )
    pyproject = (rename / "pyproject.toml").read_text(encoding="utf-8")
    pyproject = pyproject.replace(
        'name = "rai-governance-platform"',
        'name = "whitepact-distribution-rehearsal-local"',
        1,
    )
    (rename / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    renamed_out = work / "renamed"
    env = os.environ.copy()
    env["SOURCE_DATE_EPOCH"] = "0"
    run([sys.executable, "-m", "build", "--outdir", str(renamed_out)], cwd=rename, env=env)
    renamed = next(renamed_out.glob("*.whl"))
    try:
        assert_exclusive_code_ownership([wheel_a, renamed])
    except DualOwnershipError as exc:
        lines.append(f"DUAL_CODE_OWNERSHIP=REJECTED {exc}")
    else:
        raise SystemExit("two full-code distributions were accepted")
    shim = work / "rai_governance_platform-9.9.9-py3-none-any.whl"
    write_wheel(
        shim,
        distribution="rai-governance-platform",
        version="9.9.9",
        files={},
        requires=["whitepact-distribution-rehearsal-local"],
    )
    assert_exclusive_code_ownership([renamed, shim])
    lines.append("SHIM_CODE_OWNERSHIP=NONE")
    run([str(pip), "install", "--upgrade", str(renamed)])
    show = subprocess.run(
        [str(pip), "show", "rai-governance-platform"],
        capture_output=True,
        text=True,
        check=False,
    )
    lines.append(
        f"LEGACY_DIST_AFTER_RENAME_UPGRADE={'present' if show.returncode == 0 else 'removed'}"
    )
    run(
        [
            str(py),
            "-c",
            "import responsibleai, whitepact, biasbuster; "
            "from importlib.metadata import version; "
            "print(version('whitepact-distribution-rehearsal-local'))",
        ]
    )

    sums = first / "SHA256SUMS"
    sums.write_text(
        f"{sha256(wheel_a)}  {wheel_a.name}\n{sha256(sdist_a)}  {sdist_a.name}\n",
        encoding="utf-8",
    )
    run(["sha256sum", "--check", "SHA256SUMS"], cwd=first)
    sbom_note = "SBOM=SKIPPED"
    if shutil.which("cyclonedx-py"):
        sbom = work / "sbom.cyclonedx.json"
        run(
            [
                "cyclonedx-py",
                "environment",
                "--pyproject",
                str(ROOT / "pyproject.toml"),
                "--spec-version",
                "1.6",
                "--of",
                "json",
                "-o",
                str(sbom),
                str(py),
            ]
        )
        json.loads(sbom.read_text(encoding="utf-8"))
        sbom_note = "SBOM=GENERATED"
    lines.append(sbom_note)
    lines.append("ATTESTATION=NOT_GENERATED_LOCAL")
    lines.append("UPLOAD=NONE")
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(report.read_text(), end="")


if __name__ == "__main__":
    main()
