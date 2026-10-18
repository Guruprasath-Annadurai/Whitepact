# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Qualification-only pytest inventory; never changes selected tests or outcomes."""

import json
import os
from pathlib import Path


def pytest_collection_finish(session):
    destination = os.environ.get("M13_COLLECTION_FILE")
    if destination:
        Path(destination).write_text(
            json.dumps(
                [
                    {"nodeid": item.nodeid, "markers": sorted(m.name for m in item.iter_markers())}
                    for item in session.items
                ],
                indent=2,
            )
            + "\n"
        )
