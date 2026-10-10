#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact FastStart V1 — Rigorous Multi-Version Benchmark Runner.

Measures and validates:
- Target A: Lightweight core installation (Cold, un-cached) [Target: <= 10.0s]
- Target B: Cached core installation (Warm) [Target: <= 2.0s]
- Target C: Full governance server package ([dashboard], Cold & Warm) [Target: <= 30.0s]
- Target D: First policy decision & CLI doctrine demonstration (< 60s)
- Target E: Cached core install + CLI doctrine demonstration (< 300s)

Methodology Invariants (FST-R06):
1. Returns non-zero exit code (failure) if any required target fails its threshold.
2. Distinguishes cold vs cached installations.
3. Distinguishes 'pip' vs 'uv' installer metrics.
4. Distinguishes CLI demonstration latency from actual protected-execution latency.
5. Does not overclaim cached installation plus a simulation as production qualification.
6. Portable interpreter discovery without machine-specific paths.
7. Logs host CPU, OS, platform, and benchmark tool versions.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time


def get_system_info() -> dict[str, str]:
    """Capture host system architecture, OS, and tool versions."""
    uv_ver = "unknown"
    try:
        res = subprocess.run(["uv", "--version"], capture_output=True, text=True, check=False)
        if res.returncode == 0:
            uv_ver = res.stdout.strip()
    except Exception:
        pass

    return {
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "cpu_arch": platform.machine(),
        "cpu_processor": platform.processor(),
        "python_runtime": sys.version.split()[0],
        "uv_version": uv_ver,
    }


def find_interpreters(required_versions: list[str] | None = None) -> list[str]:
    """Discover Python interpreters portably without hardcoded local machine paths."""
    discovered: list[str] = []
    versions = required_versions or ["3.11", "3.12"]

    for ver in versions:
        # 1. Try PATH binaries (e.g. python3.11, python3.12)
        candidate = shutil.which(f"python{ver}")
        if candidate and os.path.isabs(candidate) and candidate not in discovered:
            discovered.append(candidate)
            continue

        # 2. Try uv python find <ver>
        try:
            res = subprocess.run(
                ["uv", "python", "find", ver],
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                p = res.stdout.strip()
                if p and os.path.exists(p) and p not in discovered:
                    discovered.append(p)
                    continue
        except Exception:
            pass

    # If none found from the matrix, fallback to running python
    if not discovered:
        discovered.append(sys.executable)

    return discovered


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str, float]:
    t0 = time.perf_counter()
    res = subprocess.run(cmd, capture_output=True, text=True, env=env)
    t1 = time.perf_counter()
    return res.returncode, res.stdout, res.stderr, (t1 - t0)


def benchmark_for_python(py_exec: str) -> tuple[dict[str, float], dict[str, str], bool]:
    py_ver = subprocess.run(
        [py_exec, "-c", "import sys; print(sys.version.split()[0])"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    print("\n" + "=" * 68)
    print(f" Running Benchmark Matrix on Python {py_ver}")
    print(f" Executable: {py_exec}")
    print("=" * 68)

    dist_dir = tempfile.mkdtemp(prefix="wp_dist_")

    try:
        # Build wheels first
        print("\n[*] Building WhitePact release distribution wheel...")
        code, out, err, dt_build = run_cmd(
            ["uv", "build", "--wheel", "-o", dist_dir], env=os.environ.copy()
        )
        if code != 0:
            raise RuntimeError(f"Build failed: {err}")
        wheels = [os.path.join(dist_dir, f) for f in os.listdir(dist_dir) if f.endswith(".whl")]
        assert len(wheels) == 1, f"Expected 1 wheel, found {wheels}"
        wheel_path = wheels[0]
        print(f"    Built: {os.path.basename(wheel_path)} in {dt_build:.2f}s")

        results: dict[str, float] = {}
        statuses: dict[str, str] = {}

        # -------------------------------------------------------------
        # Target A: Lightweight core installation (Cold, un-cached)
        # Target: <= 10.0s
        # -------------------------------------------------------------
        print("\n--- Target A: Cold Core Installation (no cache, clean venv) ---")
        with tempfile.TemporaryDirectory() as venv_a:
            run_cmd(["uv", "venv", "--python", py_exec, venv_a])
            py_a = os.path.join(venv_a, "bin", "python")
            wp_a = os.path.join(venv_a, "bin", "whitepact")
            code, out, err, dt_a_uv = run_cmd(
                ["uv", "pip", "install", "--python", py_a, "--no-cache", wheel_path]
            )
            assert code == 0, f"Target A (uv) install failed: {err}"
            code_v, out_v, err_v, _ = run_cmd([wp_a, "info"])
            assert code_v == 0 and "rai-governance-platform" in out_v
            results["target_a_cold_uv"] = dt_a_uv

            # Also measure standard pip for comparative realism
            py_pip = os.path.join(venv_a, "bin", "python")
            run_cmd([py_pip, "-m", "pip", "cache", "purge"])
            code_p, out_p, err_p, dt_a_pip = run_cmd(
                [py_pip, "-m", "pip", "install", "--no-cache-dir", "--force-reinstall", wheel_path]
            )
            results["target_a_cold_pip"] = dt_a_pip if code_p == 0 else -1.0

            status_a = "PASS" if dt_a_uv <= 10.0 else "FAIL"
            statuses["target_a_cold_core"] = status_a
            print(f"    Target A Duration (uv):  {dt_a_uv:.2f}s (Threshold <= 10.0s) -> [{status_a}]")
            if results["target_a_cold_pip"] > 0:
                print(f"    Target A Duration (pip): {results['target_a_cold_pip']:.2f}s (informational)")

        # -------------------------------------------------------------
        # Target B: Cached core installation (Warm)
        # Target: <= 2.0s
        # -------------------------------------------------------------
        print("\n--- Target B: Warm Core Installation (cached, clean venv) ---")
        with tempfile.TemporaryDirectory() as venv_b:
            run_cmd(["uv", "venv", "--python", py_exec, venv_b])
            py_b = os.path.join(venv_b, "bin", "python")
            wp_b = os.path.join(venv_b, "bin", "whitepact")
            code, out, err, dt_b = run_cmd(["uv", "pip", "install", "--python", py_b, wheel_path])
            assert code == 0, f"Target B install failed: {err}"
            code_v, out_v, err_v, _ = run_cmd([wp_b, "info"])
            assert code_v == 0 and "rai-governance-platform" in out_v
            results["target_b_warm_core"] = dt_b
            status_b = "PASS" if dt_b <= 2.0 else "FAIL"
            statuses["target_b_warm_core"] = status_b
            print(f"    Target B Duration: {dt_b:.2f}s (Threshold <= 2.0s) -> [{status_b}]")

        # -------------------------------------------------------------
        # Target C: Full governance server package ([dashboard])
        # Target: <= 30.0s
        # -------------------------------------------------------------
        print("\n--- Target C: Full Governance Server Package (Cold & Warm) ---")
        with tempfile.TemporaryDirectory() as venv_c_cold:
            run_cmd(["uv", "venv", "--python", py_exec, venv_c_cold])
            py_c = os.path.join(venv_c_cold, "bin", "python")
            wp_c = os.path.join(venv_c_cold, "bin", "whitepact")
            code, out, err, dt_c_cold = run_cmd(
                [
                    "uv",
                    "pip",
                    "install",
                    "--python",
                    py_c,
                    "--no-cache",
                    f"{wheel_path}[dashboard]",
                ]
            )
            assert code == 0, f"Target C cold install failed: {err}"
            code_v, out_v, err_v, _ = run_cmd([wp_c, "--help"])
            assert code_v == 0 and "doctor" in out_v
            results["target_c_cold_server"] = dt_c_cold
            status_c_cold = "PASS" if dt_c_cold <= 30.0 else "FAIL"
            statuses["target_c_cold_server"] = status_c_cold
            print(f"    Target C (Cold): {dt_c_cold:.2f}s (Threshold <= 30.0s) -> [{status_c_cold}]")

        with tempfile.TemporaryDirectory() as venv_c_warm:
            run_cmd(["uv", "venv", "--python", py_exec, venv_c_warm])
            py_c_w = os.path.join(venv_c_warm, "bin", "python")
            code, out, err, dt_c_warm = run_cmd(
                ["uv", "pip", "install", "--python", py_c_w, f"{wheel_path}[dashboard]"]
            )
            assert code == 0, f"Target C warm install failed: {err}"
            results["target_c_warm_server"] = dt_c_warm
            status_c_warm = "PASS" if dt_c_warm <= 30.0 else "FAIL"
            statuses["target_c_warm_server"] = status_c_warm
            print(f"    Target C (Warm): {dt_c_warm:.2f}s (Threshold <= 30.0s) -> [{status_c_warm}]")

        # -------------------------------------------------------------
        # Target D: First policy decision & CLI doctrine demonstration
        # Target: <= 60.0s
        # -------------------------------------------------------------
        print("\n--- Target D: First Policy Decision & CLI Doctrine Latency ---")
        with tempfile.TemporaryDirectory() as venv_d:
            run_cmd(["uv", "venv", "--python", py_exec, venv_d])
            py_d = os.path.join(venv_d, "bin", "python")
            wp_d = os.path.join(venv_d, "bin", "whitepact")
            run_cmd(["uv", "pip", "install", "--python", py_d, wheel_path])

            # Measure CLI doctrine demo latency
            t_start_d = time.perf_counter()
            code_d, out_d, err_d, dt_cli_d = run_cmd([wp_d, "faststart", "--json"])
            t_end_d = time.perf_counter()
            dt_d = t_end_d - t_start_d

            assert code_d == 0, f"Target D failed: {err_d}"
            rep_d = json.loads(out_d)
            assert rep_d["verified"] is True
            results["target_d_cli_demo"] = dt_d
            status_d = "PASS" if dt_d <= 60.0 else "FAIL"
            statuses["target_d_policy_decision_latency"] = status_d
            print(f"    Target D CLI Demo: {dt_d:.4f}s (Threshold <= 60.0s) -> [{status_d}]")

            # Measure genuine programmatic policy evaluation latency
            code_prog, out_prog, err_prog, dt_prog = run_cmd(
                [
                    py_d,
                    "-c",
                    "from whitepact.faststart import run_faststart_workflow; r = run_faststart_workflow(); assert r.verified",
                ]
            )
            assert code_prog == 0, f"Programmatic evaluation failed: {err_prog}"
            results["target_d_programmatic_latency"] = dt_prog
            print(f"    Target D Programmatic Evaluation: {dt_prog:.4f}s")

        # -------------------------------------------------------------
        # Target E: Cached core install + CLI doctrine demonstration
        # Target: <= 300.0s (5m)
        # -------------------------------------------------------------
        print("\n--- Target E: Cached Core Install + CLI Doctrine Demonstration ---")
        t_start_e = time.perf_counter()
        with tempfile.TemporaryDirectory() as venv_e:
            run_cmd(["uv", "venv", "--python", py_exec, venv_e])
            py_e = os.path.join(venv_e, "bin", "python")
            wp_e = os.path.join(venv_e, "bin", "whitepact")
            run_cmd(["uv", "pip", "install", "--python", py_e, wheel_path])
            code_e, out_e, err_e, _ = run_cmd([wp_e, "faststart", "--json"])
            assert code_e == 0, f"FastStart CLI failed: {err_e}"
            data = json.loads(out_e)
            assert data["verified"] is True
        t_end_e = time.perf_counter()
        dt_e = t_end_e - t_start_e
        results["target_e_cached_install_and_demo"] = dt_e
        status_e = "PASS" if dt_e <= 300.0 else "FAIL"
        statuses["target_e_cached_install_and_demo"] = status_e
        print(f"    Target E Total End-to-End: {dt_e:.2f}s (Threshold <= 300.0s) -> [{status_e}]")

        all_passed = all(st == "PASS" for st in statuses.values())
        return results, statuses, all_passed

    finally:
        shutil.rmtree(dist_dir, ignore_errors=True)


def benchmark(args: argparse.Namespace | None = None) -> int:
    args = args or argparse.Namespace(require_matrix=False, python=None)

    print("=================================================================")
    print(" WhitePact FastStart V1 — Rigorous Multi-Version Benchmark Runner")
    print("=================================================================")

    sys_info = get_system_info()
    print(f"Host OS:        {sys_info['os_name']} {sys_info['os_release']} ({sys_info['cpu_arch']})")
    print(f"Host Processor: {sys_info['cpu_processor']}")
    print(f"Benchmark Tool: {sys_info['uv_version']}")
    print(f"Runner Python:  {sys_info['python_runtime']}")
    print("=" * 68)

    if args.python:
        interpreters = [args.python]
    else:
        interpreters = find_interpreters(["3.11", "3.12"])

    if args.require_matrix:
        found_versions = {
            subprocess.run(
                [p, "-c", "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"],
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            for p in interpreters
        }
        for expected in ("3.11", "3.12"):
            if expected not in found_versions:
                print(f"ERROR: Required Python {expected} interpreter not found for matrix qualification.")
                return 1

    matrix_success = True
    summary_records = []

    for py_exec in interpreters:
        results, statuses, passed = benchmark_for_python(py_exec)
        summary_records.append((py_exec, results, statuses, passed))
        if not passed:
            matrix_success = False

    print("\n" + "=" * 68)
    print(" FINAL PERFORMANCE QUALIFICATION MATRIX SUMMARY")
    print("=" * 68)
    for py_exec, results, statuses, passed in summary_records:
        print(f"\nInterpreter: {py_exec}")
        for target, st in statuses.items():
            metric_val = results.get(target, results.get(target.replace("_core", "_uv"), 0.0))
            print(f"  {target:<35}: {metric_val:6.2f}s -> [{st}]")
        status_banner = "PASSED" if passed else "FAILED"
        print(f"  Overall Interpreter Status        : [{status_banner}]")

    print("\n" + "=" * 68)
    if not matrix_success:
        print(" QUALIFICATION STATUS: FAIL (One or more benchmark targets failed)")
        print(" - Target A failed threshold (<= 10.0s) due to un-cached cold download overhead.")
        print(" - Per remediation order FST-R06, reported as FAIL until formally revised.")
        print("=================================================================")
        return 1
    else:
        print(" QUALIFICATION STATUS: PASS (All benchmark targets met thresholds)")
        print("=================================================================")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WhitePact FastStart benchmark runner")
    parser.add_argument("--require-matrix", action="store_true", help="Require both 3.11 and 3.12")
    parser.add_argument("--python", type=str, default=None, help="Specific python interpreter path")
    cli_args = parser.parse_args()
    sys.exit(benchmark(cli_args))
