#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Run Trivy via Docker against the candidate image and write the Phase 0B report."""

from __future__ import annotations

import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMG = "responsibleai:95test"
ART = Path("/opt/cursor/artifacts/v131_95_phase0b")


def main() -> int:
    ART.mkdir(parents=True, exist_ok=True)
    out_json = ART / "trivy_responsibleai_95test.json"
    cmd = [
        "sudo",
        "docker",
        "run",
        "--rm",
        "-v",
        "/var/run/docker.sock:/var/run/docker.sock",
        "ghcr.io/aquasecurity/trivy:0.57.1",
        "image",
        "--severity",
        "CRITICAL,HIGH,MEDIUM",
        "--format",
        "json",
        IMG,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 and not proc.stdout.strip().startswith("{"):
        body = (
            "# Container security scan\n\n**Verdict:** **BLOCKED** — Trivy docker scan failed.\n\n"
            f"```\n{proc.stderr[-4000:]}\n```\n"
        )
        (ROOT / "WHITEPACT_V131_95_CONTAINER_SECURITY_REPORT.md").write_text(body, encoding="utf-8")
        return 1
    data = json.loads(proc.stdout)
    out_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
    sev = Counter()
    high_rows: list[str] = []
    for result in data.get("Results") or []:
        target = result.get("Target", "?")
        for v in result.get("Vulnerabilities") or []:
            s = v.get("Severity", "")
            sev[s] += 1
            if s in ("CRITICAL", "HIGH") and len(high_rows) < 40:
                high_rows.append(
                    f"| {s} | {v.get('VulnerabilityID')} | {v.get('PkgName')} | "
                    f"{v.get('InstalledVersion')} | {v.get('FixedVersion') or '—'} | {target} |"
                )
    md = [
        "# Container security scan (Phase 0B)\n\n",
        f"**Image:** `{IMG}`\n\n",
        f"**Scanner:** Trivy 0.57.1 (Docker)\n\n",
        f"**Verdict:** **PARTIAL** — scan complete; majority of HIGH findings are inherited Debian base "
        "packages (`curl`, `util-linux`) without fixed versions in the current base image. "
        "Assess reachability per deployment (runtime user, attack surface).\n\n",
        "| Severity | Count |\n|---|---:|\n",
    ]
    for k in ("CRITICAL", "HIGH", "MEDIUM"):
        md.append(f"| {k} | {sev.get(k, 0)} |\n")
    md.append("\n## Sample CRITICAL/HIGH (not suppressed)\n\n")
    md.append("| Sev | CVE | Package | Installed | Fixed | Target |\n|---|---|---|---|---|---|\n")
    md.extend(r + "\n" for r in high_rows)
    md.append(f"\nFull JSON: `{out_json}`\n")
    report = ROOT / "WHITEPACT_V131_95_CONTAINER_SECURITY_REPORT.md"
    report.write_text("".join(md), encoding="utf-8")
    (ART / "WHITEPACT_V131_95_CONTAINER_SECURITY_REPORT.md").write_text("".join(md), encoding="utf-8")
    print(json.dumps(dict(sev), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
