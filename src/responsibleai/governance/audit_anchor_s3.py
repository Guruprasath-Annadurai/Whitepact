"""Heart Production Closure Gap D -- a real, deployable
`AuditAnchorProvider` (`governance/audit_anchor.py`'s Protocol; see
that module's docstring for the full signed-anchor architecture this
does NOT rebuild) backed by S3 Object Lock, the WORM-capable storage
this codebase's own architecture already pointed at:
`audit_anchor.py`'s own docstring names `LocalFileAnchorProvider` as
"not real hardware WORM/S3 Object Lock" and explicitly leaves the seam
(`AuditAnchorProvider` Protocol) for exactly this implementation
without any call site changing.

**Optional dependency, lazy import**: `boto3` is not a base dependency
(see `pyproject.toml`'s `aws` extra) -- mirrors the `PyJWT[crypto]`
precedent in `auth/oidc.py`. A deployment that never anchors to S3
pays nothing; one that does installs
`pip install rai-governance-platform[aws]`.

**Idempotency / create-exclusive semantics**: uses `PutObject` with the
`IfNoneMatch: "*"` conditional-write header (S3's actual atomic
create-if-absent primitive, generally available since 2024) so two
concurrent publishers racing to publish the same `anchor_id` can never
both "win" -- exactly `LocalFileAnchorProvider`'s `O_CREAT | O_EXCL`
guarantee, translated to the one primitive S3 itself offers for it.
**Named honestly**: unlike a local `O_EXCL` failure, S3 cannot
distinguish "someone else already published this anchor_id" from "my
own earlier attempt succeeded but I never saw the 2xx response and am
now retrying" -- both surface as the same `PreconditionFailed` (HTTP
412) and both raise `AnchorAlreadyPublishedError` here. This is the
correct fail-safe direction (never silently treat a conflicting write
as your own success), but it does mean a network-flaky retry of a
publish that actually succeeded raises rather than silently
succeeding a second time -- callers should treat
`AnchorAlreadyPublishedError` on retry as "check whether the anchor
you meant to publish is already there" rather than as an
unconditional hard failure.

**Object Lock itself is a bucket-level configuration this provider
does not create** -- `retention_days`, when supplied, sets
`ObjectLockMode="COMPLIANCE"` and `ObjectLockRetainUntilDate` on each
`PutObject`, but the bucket must already have Object Lock enabled
(only settable at bucket-creation time, an infrastructure decision,
not an application-runtime one) or every publish raises
`InvalidRequest` from S3 itself -- surfaced here as-is, not swallowed.

**Unavailability policy (the directive requires this be decided, not
guessed)**: `publish_anchor()` (`audit_anchor.py`) is already, by that
module's own design, "a callable a scheduler/admin action can invoke,
not itself a background job" wired into any live request path -- so a
failed S3 publish (network partition, bucket misconfigured, Object
Lock not enabled, credentials expired) **fails loud, synchronously, to
the caller** (the boto3 `ClientError` propagates unchanged) rather
than being silently swallowed or queued. This phase deliberately does
NOT implement a local retry queue for failed publishes -- since
publication is already off the governed-action hot path, a failed
periodic/administrative anchor publish should alert an operator (the
caller's own scheduler/admin-action error handling) and be retried on
the next scheduled run, not accumulate a bespoke queue with its own
failure modes. A future phase that wires *live, per-decision* anchor
publication (not just periodic checkpoints) would need to revisit this
policy -- named explicitly as future work, not assumed solved here.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from responsibleai.governance.audit_anchor import AnchorAlreadyPublishedError


def _import_boto3_client_error() -> Any:
    try:
        from botocore.exceptions import ClientError
    except ImportError as err:
        raise ImportError(
            "boto3 is required for S3ObjectLockAnchorProvider. "
            "Install with: pip install rai-governance-platform[aws]"
        ) from err
    return ClientError


class S3ObjectLockAnchorProvider:
    """A real, production-*capable* `AuditAnchorProvider`
    (`governance/audit_anchor.py`) backed by an S3 bucket with Object
    Lock enabled. Accepts an already-constructed boto3 S3 client via
    `client`, rather than constructing one internally, for the same
    TCB-minimization/testability reason every other Heart seam
    (`RootResolver`, `KeyProvider`, `AuditAnchorProvider` itself) takes
    its dependency as a plain injected object: this class is fully
    testable against a fake client with no real AWS credentials or
    network access, and the caller controls credential/region/retry
    configuration exactly as it would for any other boto3 client in
    this deployment.
    """

    def __init__(
        self,
        bucket: str,
        *,
        client: Any = None,
        prefix: str = "",
        retention_days: int | None = None,
    ) -> None:
        """`client=None` lazily constructs a default boto3 S3 client
        (region/credentials from the environment, boto3's usual
        resolution chain) -- raises `ImportError` with an actionable
        install message if boto3 isn't installed, rather than failing
        with an opaque `ModuleNotFoundError` deep in `publish()`.
        `retention_days=None` publishes without setting Object Lock
        retention on the object itself (the bucket's own default
        retention configuration, if any, still applies) -- set this
        explicitly to require a minimum retention beyond the bucket
        default for anchors specifically."""
        if client is None:
            try:
                import boto3
            except ImportError as err:
                raise ImportError(
                    "boto3 is required for S3ObjectLockAnchorProvider. "
                    "Install with: pip install rai-governance-platform[aws]"
                ) from err
            client = boto3.client("s3")
        self._client = client
        self._bucket = bucket
        self._prefix = prefix
        self._retention_days = retention_days

    def _key_for(self, anchor_id: str) -> str:
        return f"{self._prefix}{anchor_id}.anchor.json"

    async def publish(self, anchor_id: str, payload: bytes) -> str:
        client_error_cls = _import_boto3_client_error()
        key = self._key_for(anchor_id)
        kwargs: dict[str, Any] = {
            "Bucket": self._bucket,
            "Key": key,
            "Body": payload,
            "IfNoneMatch": "*",  # atomic create-if-absent -- see module docstring
        }
        if self._retention_days is not None:
            kwargs["ObjectLockMode"] = "COMPLIANCE"
            kwargs["ObjectLockRetainUntilDate"] = datetime.now(UTC) + timedelta(
                days=self._retention_days
            )
        try:
            self._client.put_object(**kwargs)
        except client_error_cls as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("PreconditionFailed", "412"):
                raise AnchorAlreadyPublishedError(anchor_id) from exc
            raise
        return f"s3://{self._bucket}/{key}"

    async def fetch(self, destination_ref: str) -> bytes:
        client_error_cls = _import_boto3_client_error()
        if not destination_ref.startswith("s3://"):
            raise FileNotFoundError(f"not an s3:// destination_ref: {destination_ref!r}")
        without_scheme = destination_ref.removeprefix("s3://")
        bucket, _, key = without_scheme.partition("/")
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
        except client_error_cls as exc:
            error_code = exc.response.get("Error", {}).get("Code", "")
            if error_code in ("NoSuchKey", "404"):
                raise FileNotFoundError(f"no anchor at {destination_ref!r}: {exc}") from exc
            raise
        body = response["Body"].read()
        return bytes(body)
