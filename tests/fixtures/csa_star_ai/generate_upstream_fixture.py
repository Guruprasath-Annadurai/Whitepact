# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Generate parser-test workbook only — NOT a CSA submission artifact."""

from __future__ import annotations

from pathlib import Path

DOMAINS = [
    "A&A",
    "AIS",
    "BCR",
    "CCC",
    "CEK",
    "DSP",
    "GRC",
    "HRS",
    "IAM",
    "IVS",
    "LOG",
    "SEF",
    "STA",
    "TVM",
    "UEM",
    "AIG",
    "MDL",
    "OPS",
]


def main() -> None:
    import openpyxl

    out = Path(__file__).with_name("TEST_ONLY_AI-CAIQ_v1.1_320rows.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "AI-CAIQv1.1"
    ws.append(
        [
            "Question ID",
            "Question",
            "CSP CAIQ Answer",
            "SSRM Control Ownership",
            "CSP Implementation Description (Optional/Recommended)",
            "CSC Responsibilities  (Optional/Recommended)",
        ]
    )
    for n in range(320):
        domain = DOMAINS[n % len(DOMAINS)]
        major = (n // len(DOMAINS)) + 1
        minor = (n % 3) + 1
        qid = f"{domain}-{major:02d}.{minor}"
        ws.append([qid, f"Synthetic test question for {qid}?", "", "", "", ""])
    wb.save(out)
    print(out)


if __name__ == "__main__":
    main()
