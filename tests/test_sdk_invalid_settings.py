"""Unsafe deadline/retry settings must fail before any network request."""

import pytest
from sdk.python.rai_client import GovernanceRuntimeClient, RAIClient


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf"), True, "30"])
def test_invalid_deadlines(timeout):
    with pytest.raises(ValueError):
        RAIClient(timeout=timeout)
    with pytest.raises(ValueError):
        GovernanceRuntimeClient("synthetic", timeout=timeout)


@pytest.mark.parametrize("attempts", [0, -1, 1.5, float("inf"), True])
def test_invalid_read_retry_settings(attempts):
    with pytest.raises(ValueError):
        RAIClient(max_retries=attempts)
