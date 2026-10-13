#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline checks for the zero-budget OCI candidate.

Does not call a cloud API and does not run Terraform apply.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

MODULE = Path(__file__).resolve().parent

EXACT = {
    "shape": "VM.Standard.A1.Flex",
    "ocpus": "2",
    "memory_in_gbs": "12",
    "boot_volume_gb": "50",
    "data_volume_gb": "50",
    "authorization_gate": "HOLD",
    "vcn_cidr": "10.8.0.0/16",
    "subnet_cidr": "10.8.1.0/24",
}

FORBIDDEN_RESOURCE_TYPES = (
    "oci_core_nat_gateway",
    "oci_load_balancer_load_balancer",
    "oci_network_load_balancer_network_load_balancer",
    "oci_database_autonomous_database",
    "oci_mysql_mysql_db_system",
    "oci_objectstorage_bucket",
    "oci_core_public_ip",
    "oci_core_instance_pool",
)

REQUIRED_RESOURCE_TYPES = (
    "oci_limits_quota",
    "oci_core_instance",
    "oci_core_security_list",
    "oci_bastion_bastion",
    "terraform_data",
)

RESOURCE_RE = re.compile(r'^\s*resource\s+"([^"]+)"\s+"[^"]+"\s+\{', re.M)
def _default_pattern(name: str) -> str:
    return rf'variable\s+"{re.escape(name)}"\s+\{{.*?default\s+=\s+"?([^"\n]+)"?'


def _read_module() -> str:
    parts = []
    for path in sorted(MODULE.glob("*.tf")):
        parts.append(path.read_text(encoding="utf-8"))
    return "\n".join(parts)


def resource_types(text: str) -> set[str]:
    return set(RESOURCE_RE.findall(text))


def allocation_errors(text: str) -> list[str]:
    errors: list[str] = []
    for name, expected in EXACT.items():
        found = re.search(_default_pattern(name), text, re.S)
        if not found:
            errors.append(f"variable {name} has no default")
            continue
        actual = found.group(1).strip()
        if actual != expected:
            errors.append(f"variable {name} default is {actual!r}, expected {expected!r}")
    return errors


def module_errors(text: str) -> list[str]:
    errors = allocation_errors(text)
    found = resource_types(text)
    for name in FORBIDDEN_RESOURCE_TYPES:
        if name in found:
            errors.append(f"forbidden resource {name} is declared")
    for name in REQUIRED_RESOURCE_TYPES:
        if name not in found:
            errors.append(f"required resource {name} is missing")
    if not re.search(r"assign_public_ip\s+=\s+true", text):
        errors.append("primary VNIC must set assign_public_ip = true so egress does not need a paid NAT gateway")
    if re.search(r"prohibit_internet_ingress\s+=\s+true", text):
        errors.append("prohibit_internet_ingress=true makes the subnet private and forces a paid NAT gateway")
        errors.append("security list ingress must not allow 0.0.0.0/0")
    if "AUTHORIZED_BY_OWNER" not in text or "authorization_gate" not in text:
        errors.append("authorization gate precondition is missing")
    if "169.254.169.254/32" not in text:
        errors.append("resolver egress to the OCI metadata address must be DNS-only and explicit")
    cloud_init = (MODULE / "cloud-init.yaml").read_text(encoding="utf-8")
    if "169.254.169.254" not in cloud_init or "--dports 80,443" not in cloud_init:
        errors.append("cloud-init must drop container HTTP to the metadata address")
    if "password" in cloud_init.lower() or "BEGIN OPENSSH PRIVATE KEY" in cloud_init:
        errors.append("cloud-init contains secret material")
    apply_script = (MODULE / "apply.sh").read_text(encoding="utf-8")
    if "exit 2" not in apply_script or "terraform apply" not in apply_script:
        errors.append("apply.sh must refuse terraform apply with exit 2")
    return errors


def self_test() -> int:
    text = _read_module()
    errors = module_errors(text)
    if errors:
        print("zero-budget preflight failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    hostile = text + '\nresource "oci_core_nat_gateway" "bad" {\n}\n'
    hostile_types = resource_types(hostile)
    if "oci_core_nat_gateway" not in hostile_types:
        print("preflight failed to detect a forbidden resource")
        return 1

    drifted = text.replace("default     = 12", "default     = 24", 1)
    if not allocation_errors(drifted):
        print("preflight failed to detect a memory drift")
        return 1

    print("zero-budget preflight passed")
    print("allocation: VM.Standard.A1.Flex 2 OCPU / 12 GB / 50 GB boot / 50 GB data")
    print("authorization gate: HOLD")
    print("provider mutation: refused")
    return 0


def main(argv: list[str]) -> int:
    if argv not in ([], ["--self-test"]):
        print("usage: preflight.py [--self-test]", file=sys.stderr)
        return 2
    return self_test()


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
