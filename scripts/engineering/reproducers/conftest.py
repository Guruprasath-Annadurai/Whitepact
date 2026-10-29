# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Transport setup for one byte-preserved historical cancellation unit probe.

This fixture does not change the approved test, its assertions, the provenance
allowlist or production validators. It is not native Docker qualification.
"""

from pathlib import Path

import pytest
from tests.image_admission_fixture import approved_inert_image as approved_inert_image


@pytest.fixture(autouse=True)
def _image_transport_for_preserved_cancellation(request):
    if (
        request.node.path
        == Path(__file__).resolve().with_name("test_m13_dual_titan_cancellation.py")
        and request.node.name
        == "test_execute_cleanup_failure_retains_tracking_after_cancellation"
    ):
        request.getfixturevalue("approved_inert_image")
