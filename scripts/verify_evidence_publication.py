# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Verify a published evidence head without opening the application database.

Example:
  python scripts/verify_evidence_publication.py \
    --log /var/lib/whitepact/evidence-witness \
    --organization org-a \
    --sequence 4 \
    --head-hash "$HEAD"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from responsibleai.governance.evidence_publication import (  # noqa: E402
    AppendOnlyWitnessLog,
    WitnessPublicationError,
    live_object_store_status,
    verify_published_head,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--organization", required=True)
    parser.add_argument("--sequence", type=int, required=True)
    parser.add_argument("--head-hash", required=True)
    args = parser.parse_args()
    try:
        record = verify_published_head(
            AppendOnlyWitnessLog(args.log),
            organization_id=args.organization,
            chain_sequence=args.sequence,
            head_hash=args.head_hash,
        )
    except WitnessPublicationError as exc:
        json.dump(
            {
                "verified": False,
                "error": str(exc),
                "live_object_store_status": live_object_store_status(),
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
        return 1
    payload = record.to_dict()
    payload["verified"] = True
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
