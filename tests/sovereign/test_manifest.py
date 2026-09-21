# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

import pytest

from responsibleai.sovereign.errors import SovereignValidationError
from responsibleai.sovereign.manifest import WhitepactManifest, validate_manifest_dict


def test_manifest_rejects_secret_metadata_keys() -> None:
    with pytest.raises(SovereignValidationError):
        validate_manifest_dict(
            {
                "organization_id": "org-a",
                "metadata": {"api_key": "leak"},
            }
        )


def test_manifest_valid_minimal() -> None:
    m = WhitepactManifest(organization_id="org-a", environment="staging")
    assert m.organization_id == "org-a"


def test_manifest_validation_error_wrapped() -> None:
    with pytest.raises(SovereignValidationError):
        validate_manifest_dict({"organization_id": 123})
