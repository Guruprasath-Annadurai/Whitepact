# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Install locally built packages into external consumers; never publish packages."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GO_IMAGE = "golang@sha256:1cf6c45ba39db9fd6db16922041d074a63c935556a05c5ccb62d181034df7f02"


def _run(args: list[str], cwd: Path, *, timeout: int = 180) -> str:
    # Consumers must import their installed artifact, not inherited PYTHONPATH;
    # build/install subprocesses do not receive host service credentials.
    environment = {
        name: os.environ[name]
        for name in ("PATH", "HOME", "TMPDIR", "LANG", "LC_ALL", "SYSTEMROOT")
        if name in os.environ
    }
    with tempfile.TemporaryDirectory(prefix="wp-package-config-") as config_dir:
        # npm refuses loading the same file twice as user/global configuration.
        # Distinct nonexistent paths exclude both inherited credential stores.
        environment.update(
            PIP_CONFIG_FILE=os.devnull,
            NPM_CONFIG_USERCONFIG=str(Path(config_dir) / "user.npmrc"),
            NPM_CONFIG_GLOBALCONFIG=str(Path(config_dir) / "global.npmrc"),
        )
        result = subprocess.run(
            args, cwd=cwd, env=environment, capture_output=True, text=True, timeout=timeout
        )
    assert result.returncode == 0, result.stdout[-3000:] + result.stderr[-3000:]
    return result.stdout


def test_python_wheel_fresh_environment_import_and_negative_transport(tmp_path) -> None:
    source = tmp_path / "source"
    shutil.copytree(
        ROOT / "sdk/python",
        source / "sdk/python",
        ignore=shutil.ignore_patterns("dist", "__pycache__"),
    )
    shutil.copy2(ROOT / "LICENSE", source / "LICENSE")
    wheels = tmp_path / "wheels"
    _run(
        [sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(wheels)],
        source / "sdk/python",
    )
    wheel = next(wheels.glob("rai_client-*.whl"))
    environment = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    _run([str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)], tmp_path)
    _run([str(python), "-m", "pip", "check"], tmp_path)
    _run(
        [
            str(python),
            "-c",
            "import rai_client; from rai_client.governance import GovernanceRuntimeClient; print(rai_client.__file__);\ntry: GovernanceRuntimeClient('local-synthetic-key', 'http://example.invalid')\nexcept ValueError: pass\nelse: raise AssertionError('insecure bearer transport accepted')",
        ],
        tmp_path,
    )


def test_typescript_tarball_external_esm_and_commonjs_consumer(tmp_path) -> None:
    source = tmp_path / "sdk"
    shutil.copytree(
        ROOT / "sdk/typescript", source, ignore=shutil.ignore_patterns("node_modules", "dist")
    )
    _run(["npm", "ci", "--prefer-offline", "--ignore-scripts", "--no-audit", "--no-fund"], source)
    _run(["npm", "run", "build"], source)
    packed = json.loads(_run(["npm", "pack", "--json", "--ignore-scripts"], source))[0]
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    _run(
        [
            "npm",
            "install",
            "--offline",
            "--ignore-scripts",
            "--no-audit",
            "--no-fund",
            str(source / packed["filename"]),
        ],
        consumer,
    )
    _run(
        [
            "node",
            "--input-type=module",
            "-e",
            "import {RAIClient,GovernanceRuntimeClient,isCompleted} from '@responsibleai/client'; if(typeof RAIClient !== 'function'||typeof GovernanceRuntimeClient !== 'function') process.exit(2); for(const status of ['UNKNOWN','DENIED','PENDING','FAILED']) if(isCompleted({result:{},status})) throw new Error('non-success completed');",
        ],
        consumer,
    )
    _run(
        [
            "node",
            "-e",
            "const {RAIClient,GovernanceRuntimeClient}=require('@responsibleai/client'); if(typeof RAIClient !== 'function'||typeof GovernanceRuntimeClient !== 'function') process.exit(2);",
        ],
        consumer,
    )


def test_go_external_consumer_module_build_and_negative_transport(tmp_path) -> None:
    consumer = tmp_path / "consumer"
    consumer.mkdir()
    shutil.copy2(ROOT / "tests/fixtures/wave1_packages/main.go", consumer / "main.go")
    _run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{ROOT / 'sdk/go'}:/sdk:ro",
            "-v",
            f"{consumer}:/consumer",
            "-w",
            "/consumer",
            GO_IMAGE,
            "sh",
            "-c",
            "go mod init example.invalid/qualification && "
            "go mod edit -require github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go@v0.0.0 "
            "-replace github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go=/sdk && "
            "go build -o /consumer/qualification . && /consumer/qualification && "
            "go test github.com/Guruprasath-Annadurai/ResponsibleAi/sdk/go/raiclient",
        ],
        tmp_path,
    )
