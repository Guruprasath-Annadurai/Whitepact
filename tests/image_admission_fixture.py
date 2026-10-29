# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Explicit Docker-transport double for existing cleanup/cancellation unit probes.

Production admission validators still run; this is not native Docker evidence.
Only callers requesting this fixture receive its disposable image approval.
"""

import json
import re

import pytest

from responsibleai.isolation import image_admission


@pytest.fixture
def approved_inert_image(monkeypatch):
    image = "sha256:" + "b" * 64
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE", image)
    monkeypatch.setenv("WHITEPACT_ISOLATION_IMAGE_APPROVALS", json.dumps({image: image}))

    def inspect_only(docker_cmd, arguments):
        if arguments == ["image", "inspect", image]:
            return json.dumps([{"Id": image, "Os": "linux"}])
        if arguments[:4] == ["container", "inspect", "--format", "{{.Image}}"]:
            assert len(arguments) == 5 and re.fullmatch(r"[0-9a-f]{64}", arguments[4])
            return image
        raise AssertionError("Unit image transport received an unexpected Docker operation")

    monkeypatch.setattr(image_admission, "_run", inspect_only)
    return image
