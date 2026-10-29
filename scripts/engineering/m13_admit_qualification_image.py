# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Approve this disposable CI build's content ID, never its mutable tag.

This is a trusted qualification setup action, not runtime admission or production
release approval. The image comes from docker build --iidfile in the same job.
"""

import argparse
import json
import os
import re
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--iid-file", type=Path, required=True)
    parser.add_argument("--github-env", type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get("GITHUB_ACTIONS") != "true":
        parser.error("Only disposable GitHub Actions qualification is supported")
    image = args.iid_file.read_text(encoding="ascii").strip()
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        parser.error("Build must supply a complete immutable content ID")
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    receipt = json.loads(result.stdout)
    if len(receipt) != 1 or receipt[0].get("Id") != image or receipt[0].get("Os") != "linux":
        parser.error("Actual Linux image does not match the build receipt")
    with args.github_env.open("a", encoding="utf-8") as stream:
        stream.write(f"WHITEPACT_ISOLATION_IMAGE={image}\nWHITEPACT_TEST_RUNTIME_IMAGE={image}\n")
        stream.write(
            "WHITEPACT_ISOLATION_IMAGE_APPROVALS="
            + json.dumps({image: image}, separators=(",", ":"))
            + "\n"
        )
    print(
        json.dumps(
            {
                "qualification_only": True,
                "source": "docker build --iidfile",
                "approved_content_id": image,
                "registry_manifest_claimed": False,
            }
        )
    )


if __name__ == "__main__":
    main()
