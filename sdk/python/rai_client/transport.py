"""Credential transport configuration shared by SDK clients."""

from ipaddress import ip_address
from math import isfinite
from urllib.parse import urlsplit


def validate_timeout(timeout: float) -> None:
    if (
        isinstance(timeout, bool)
        or not isinstance(timeout, (int, float))
        or not isfinite(timeout)
        or timeout <= 0
    ):
        raise ValueError("SDK timeout must be positive and finite")


def validate_base_url(base_url: str, api_key: str) -> None:
    """Require HTTPS for bearer keys, except explicit local development hosts."""
    try:
        url = urlsplit(base_url)
        host = url.hostname
        if not host or url.username is not None or url.password is not None:
            raise ValueError
        if url.scheme not in {"http", "https"}:
            raise ValueError
        # Validate port without copying the possibly credential-bearing input to errors.
        _ = url.port
        if not api_key or url.scheme == "https":
            return
        if host == "localhost":
            return
        try:
            if ip_address(host).is_loopback:
                return
        except ValueError:
            pass
    except ValueError:
        pass
    raise ValueError("SDK base URL must use HTTPS or explicit loopback HTTP for bearer credentials")
