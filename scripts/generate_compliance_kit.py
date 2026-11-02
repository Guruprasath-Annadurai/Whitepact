#!/usr/bin/env python3
"""Scaffold a compliance self-assessment starter kit for another company.

The sellable product behind STRATEGY_ROADMAP.md Part 0, Item 4: package
the CAIQ/NIST CSF self-assessment approach this project built and uses on
itself (compliance/CAIQ_SELF_ASSESSMENT.md,
compliance/NIST_CSF_SELF_ASSESSMENT.md) as a starting point for any other
small AI/software company with the same "no SOC2 budget yet" problem.

This script only copies the generic templates (compliance/starter-kit/*)
into a fresh directory with the company name and today's date substituted
in — it does not and cannot fill in the actual honest answers, which
require that company's own real facts. See
compliance/COMPLIANCE_STARTER_KIT_OFFER.md for the paid-consulting offer
this scaffolding supports (filling the templates in with a real reviewer,
not just handing over blank paper).

Usage:
    python scripts/generate_compliance_kit.py "Acme Corp"
    # → writes ./acme-corp-compliance-kit/CAIQ_TEMPLATE.md and NIST_CSF_TEMPLATE.md
"""

from __future__ import annotations

import re
import sys
from datetime import UTC, datetime
from pathlib import Path

_TEMPLATE_DIR = Path(__file__).parent.parent / "compliance" / "starter-kit"
_TEMPLATE_FILES = ["CAIQ_TEMPLATE.md", "NIST_CSF_TEMPLATE.md"]


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "company"


def generate(company_name: str, output_dir: Path | None = None) -> Path:
    if not _TEMPLATE_DIR.exists():
        raise FileNotFoundError(f"Template directory not found: {_TEMPLATE_DIR}")

    target = output_dir or Path.cwd() / f"{_slugify(company_name)}-compliance-kit"
    target.mkdir(parents=True, exist_ok=True)

    today = datetime.now(UTC).strftime("%Y-%m-%d")

    for filename in _TEMPLATE_FILES:
        src = _TEMPLATE_DIR / filename
        if not src.exists():
            print(f"  skipping missing template: {filename}", file=sys.stderr)
            continue
        text = src.read_text(encoding="utf-8")
        text = text.replace("{{COMPANY_NAME}}", company_name).replace("{{DATE}}", today)
        dest = target / filename
        dest.write_text(text, encoding="utf-8")
        print(f"  wrote {dest}")

    return target


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python scripts/generate_compliance_kit.py "Company Name" [output_dir]', file=sys.stderr)
        raise SystemExit(1)

    company_name = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    print(f"Generating compliance starter kit for: {company_name}")
    target = generate(company_name, output_dir)
    print(f"\nDone. Next step: fill in every [FILL IN: ...] placeholder in {target}/")
    print("with real, specific, honest facts — a template only saves the structure,")
    print("not the truth-telling, which is the actual hard part.")


if __name__ == "__main__":
    main()
