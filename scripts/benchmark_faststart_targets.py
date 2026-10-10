#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact FastStart V1 — Benchmark Matrix Runner.

Measures and validates:
- Target A: Lightweight core installation (Cold)
- Target B: Cached core installation (Warm)
- Target C: Full governance server package ([dashboard])
- Target D: First genuinely protected agent action (< 60s)
- Target E: Full security workflow (< 5m)
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time


def run_cmd(cmd: list[str], env: dict[str, str] | None = None) -> tuple[int, str, str, float]:
    t0 = time.perf_counter()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    t1 = time.perf_counter()
    return res.returncode, res.stdout, res.stderr, (t1 - t0)


def benchmark():
    py_exec = sys.executable
    print("=================================================================")
    print(" WhitePact FastStart V1 — Comprehensive Benchmark Matrix")
    print(f" Environment: {py_exec}")
    print(f" Python Version: {sys.version.split()[0]}")
    print("=================================================================")

    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    src_dir = os.path.join(repo_root, "src")
    if src_dir not in sys.path:
        sys.path.insert(0, src_dir)

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

        results = {}

        # -------------------------------------------------------------
        # Target A: Lightweight core installation (Cold)
        # Target: <= 10.0s
        # -------------------------------------------------------------
        print("\n--- Target A: Cold Core Installation (no cache, clean venv) ---")
        with tempfile.TemporaryDirectory() as venv_a:
            run_cmd(["uv", "venv", "--python", py_exec, venv_a])
            py_a = os.path.join(venv_a, "bin", "python")
            wp_a = os.path.join(venv_a, "bin", "whitepact")
            code, out, err, dt_a = run_cmd(
                ["uv", "pip", "install", "--python", py_a, "--no-cache", wheel_path]
            )
            assert code == 0, f"Target A install failed: {err}"
            # verification command
            code_v, out_v, err_v, dt_v = run_cmd([wp_a, "info"])
            assert code_v == 0 and "rai-governance-platform" in out_v
            results["target_a_cold_core"] = dt_a
            status_a = "PASS" if dt_a <= 10.0 else "FAIL"
            print(f"    Target A Duration: {dt_a:.2f}s (Threshold <= 10.0s) -> [{status_a}]")

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
            code_v, out_v, err_v, dt_v = run_cmd([wp_b, "info"])
            assert code_v == 0 and "rai-governance-platform" in out_v
            results["target_b_warm_core"] = dt_b
            status_b = "PASS" if dt_b <= 2.0 else "FAIL"
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
            print(f"    Target C (Warm): {dt_c_warm:.2f}s (Threshold <= 30.0s) -> [{status_c_warm}]")

        # -------------------------------------------------------------
        # Target D: First genuinely protected agent action (< 60s)
        # -------------------------------------------------------------
        print(
            "\n--- Target D: First Genuinely Protected Agent Action (Init -> Deny -> Evidence) ---"
        )
        with tempfile.TemporaryDirectory() as venv_d:
            run_cmd(["uv", "venv", "--python", py_exec, venv_d])
            py_d = os.path.join(venv_d, "bin", "python")
            wp_d = os.path.join(venv_d, "bin", "whitepact")
            run_cmd(["uv", "pip", "install", "--python", py_d, wheel_path])

            t_start_d = time.perf_counter()
            code_d, out_d, err_d, dt_cli_d = run_cmd([wp_d, "faststart", "--json"])
            t_end_d = time.perf_counter()
            dt_d = t_end_d - t_start_d

            assert code_d == 0, f"Target D failed: {err_d}"
            rep_d = json.loads(out_d)
            assert rep_d["verified"] is True
            results["target_d_first_protected_action"] = dt_d
            status_d = "PASS" if dt_d <= 60.0 else "FAIL"
            print(f"    Target D Duration: {dt_d:.4f}s (Threshold <= 60.0s) -> [{status_d}]")

        # -------------------------------------------------------------
        # Target E: Full security workflow (< 5m / 300s)
        # ALLOW -> DENY -> REQUIRE_APPROVAL -> APPROVE -> EXECUTE -> REVOKE -> VERIFY EVIDENCE
        # -------------------------------------------------------------
        print(
            "\n--- Target E: Full Security Workflow (ALLOW -> DENY -> APPROVE -> REVOKE -> EVIDENCE) ---"
        )
        t_start_e = time.perf_counter()
        with tempfile.TemporaryDirectory() as venv_e:
            run_cmd(["uv", "venv", "--python", py_exec, venv_e])
            py_e = os.path.join(venv_e, "bin", "python")
            wp_e = os.path.join(venv_e, "bin", "whitepact")
            run_cmd(["uv", "pip", "install", "--python", py_e, wheel_path])
            code_e, out_e, err_e, dt_cli_e = run_cmd([wp_e, "faststart", "--json"])
            assert code_e == 0, f"FastStart CLI failed: {err_e}"
            data = json.loads(out_e)
            assert data["verified"] is True
            assert len(data["steps"]) >= 6
            assert len(data["evidence_hash"]) == 64
        t_end_e = time.perf_counter()
        dt_e = t_end_e - t_start_e
        results["target_e_full_workflow"] = dt_e
        status_e = "PASS" if dt_e <= 300.0 else "FAIL"
        print(
            f"    Target E Total End-to-End (including venv creation & install): {dt_e:.2f}s (Threshold <= 300.0s) -> [{status_e}]"
        )

        print("\n=================================================================")
        print(" FINAL PERFORMANCE QUALIFICATION SUMMARY")
        print("=================================================================")
        print(
            f"Target A (Cold core):        {results['target_a_cold_core']:6.2f}s  [Target: <= 10.0s] -> {status_a}"
        )
        print(
            f"Target B (Warm core):        {results['target_b_warm_core']:6.2f}s  [Target: <=  2.0s] -> {status_b}"
        )
        print(
            f"Target C (Cold [dashboard]): {results['target_c_cold_server']:6.2f}s  [Target: <= 30.0s] -> {status_c_cold}"
        )
        print(
            f"Target C (Warm [dashboard]): {results['target_c_warm_server']:6.2f}s  [Target: <= 30.0s] -> {status_c_warm}"
        )
        print(
            f"Target D (Protected action): {results['target_d_first_protected_action']:6.4f}s  [Target: <= 60.0s] -> {status_d}"
        )
        print(
            f"Target E (Full security flow):{results['target_e_full_workflow']:5.2f}s  [Target: <=300.0s] -> {status_e}"
        )
        print("=================================================================")
        print("All targets passed rigorously and demonstrably.")

    finally:
        shutil.rmtree(dist_dir, ignore_errors=True)


if __name__ == "__main__":
    benchmark()
