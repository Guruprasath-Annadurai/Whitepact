"""Tests for Heart Production Closure Gap D --
`governance/audit_anchor_s3.py`'s `S3ObjectLockAnchorProvider`.

**Honest scope, per the directive's own rule**: no real AWS credentials
or S3/Object-Lock infrastructure exist in this environment. Every test
below exercises this module's own logic (request construction, the
IfNoneMatch conditional-write idempotency path, error-code mapping,
Protocol conformance against the real `build_and_sign_anchor()`/
`publish_anchor()`/`verify_anchor_from_provider()` pipeline) against a
`_FakeS3Client` that reproduces the exact behavior AWS's own S3 API
documents for `PutObject`/`GetObject` with `IfNoneMatch`, using real
`botocore.exceptions.ClientError` instances (botocore itself is a
lightweight, no-network-to-import dependency) so the provider's own
`except ClientError` branch is genuinely exercised, not mocked around.
**Live external verification against a real S3 bucket is BLOCKED** --
not run, not claimed, not simulated as passing. See
`docs/heart-production-closure/00_CLOSURE_AUDIT.md`'s Gap D section
and the final closure verdict for this explicitly marked as BLOCKED
rather than silently omitted.
"""

from __future__ import annotations

import asyncio
import os
from datetime import UTC, datetime

import pytest

# Optional dependency (pyproject.toml's `aws` extra), same pattern as
# test_langchain_middleware.py/test_async_db.py -- guards this whole
# file rather than every individual test.
pytest.importorskip("botocore")
from botocore.exceptions import ClientError  # noqa: E402

from responsibleai.governance.audit_anchor import (
    AnchorAlreadyPublishedError,
    AnchorVerificationStatus,
    build_and_sign_anchor,
    publish_anchor,
    verify_anchor_from_provider,
)
from responsibleai.governance.audit_anchor_s3 import S3ObjectLockAnchorProvider
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider
from responsibleai.governance.crypto.types import KeyPurpose
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.evidence_bundle import build_evidence_bundle


class _FakeS3Client:
    """Reproduces the exact AWS-documented behavior this provider
    depends on: `PutObject` with `IfNoneMatch="*"` raises
    `PreconditionFailed` (412) if the key already exists;
    `GetObject` on a missing key raises `NoSuchKey` (404)."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict] = {}
        self.put_calls: list[dict] = []

    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)
        key = (kwargs["Bucket"], kwargs["Key"])
        if kwargs.get("IfNoneMatch") == "*" and key in self.objects:
            raise ClientError(
                {
                    "Error": {
                        "Code": "PreconditionFailed",
                        "Message": "At least one of the pre-conditions you specified did not hold",
                    }
                },
                "PutObject",
            )
        self.objects[key] = {
            "Body": kwargs["Body"],
            "ObjectLockMode": kwargs.get("ObjectLockMode"),
            "ObjectLockRetainUntilDate": kwargs.get("ObjectLockRetainUntilDate"),
        }
        return {"ETag": '"fake-etag"'}

    def get_object(self, **kwargs):
        key = (kwargs["Bucket"], kwargs["Key"])
        if key not in self.objects:
            raise ClientError(
                {"Error": {"Code": "NoSuchKey", "Message": "The specified key does not exist."}},
                "GetObject",
            )

        class _Body:
            def __init__(self, data: bytes) -> None:
                self._data = data

            def read(self) -> bytes:
                return self._data

        return {"Body": _Body(self.objects[key]["Body"])}


@pytest.fixture()
def fake_client() -> _FakeS3Client:
    return _FakeS3Client()


@pytest.fixture()
def provider(fake_client) -> S3ObjectLockAnchorProvider:
    return S3ObjectLockAnchorProvider("evidence-anchors", client=fake_client)


@pytest.fixture()
def key_provider() -> LocalEnvelopeKeyProvider:
    return LocalEnvelopeKeyProvider(root_key=os.urandom(32), environment="test")


def _record(evidence_id: str, prev_hash: str | None, hash_: str) -> EvidenceRecord:
    return EvidenceRecord(
        evidence_id=evidence_id,
        organization_id="org-1",
        action_id=f"action-{evidence_id}",
        agent_id="agent-1",
        identity_id="identity-1",
        action_type="mcp_tool_call",
        target="rai_scan",
        argument_keys=[],
        authority_delegated_by="org-1",
        decision="ALLOW",
        reason_codes=[],
        evaluated_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC).isoformat(),
        prev_hash=prev_hash,
        hash=hash_,
    )


class TestMissingBoto3RaisesActionableImportError:
    def test_no_client_and_no_boto3_installed_would_raise_actionable_error(self, monkeypatch):
        """boto3 IS installed in this test environment (needed to
        exercise the ClientError-handling code paths above), so this
        test simulates its absence by making the internal `import
        boto3` fail, proving the actionable-message path without
        actually uninstalling the dependency other tests need."""
        import builtins

        real_import = builtins.__import__

        def _fake_import(name, *args, **kwargs):
            if name == "boto3":
                raise ImportError("No module named 'boto3'")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", _fake_import)
        with pytest.raises(ImportError, match="rai-governance-platform\\[aws\\]"):
            S3ObjectLockAnchorProvider("evidence-anchors")


class TestPublishAndFetch:
    async def test_publish_returns_an_s3_uri_destination_ref(self, provider):
        ref = await provider.publish("anchor-1", b'{"digest": "abc"}')
        assert ref == "s3://evidence-anchors/anchor-1.anchor.json"

    async def test_fetch_returns_exactly_what_was_published(self, provider):
        payload = b'{"digest": "abc123"}'
        ref = await provider.publish("anchor-1", payload)
        fetched = await provider.fetch(ref)
        assert fetched == payload

    async def test_prefix_is_applied_to_the_object_key(self, fake_client):
        provider = S3ObjectLockAnchorProvider(
            "evidence-anchors", client=fake_client, prefix="org-1/"
        )
        ref = await provider.publish("anchor-1", b"data")
        assert ref == "s3://evidence-anchors/org-1/anchor-1.anchor.json"


class TestIdempotentCreateExclusive:
    async def test_publishing_the_same_anchor_id_twice_raises(self, provider):
        await provider.publish("anchor-1", b"first")
        with pytest.raises(AnchorAlreadyPublishedError):
            await provider.publish("anchor-1", b"second")

    async def test_second_publish_does_not_overwrite_the_first(self, provider, fake_client):
        await provider.publish("anchor-1", b"first")
        with pytest.raises(AnchorAlreadyPublishedError):
            await provider.publish("anchor-1", b"second")
        fetched = await provider.fetch("s3://evidence-anchors/anchor-1.anchor.json")
        assert fetched == b"first"

    async def test_concurrent_publishes_of_the_same_anchor_id_only_one_wins(self, provider):
        """Multi-instance safety: two 'processes' racing to publish the
        same anchor_id must not both succeed -- exactly the property
        the append-only anchor architecture requires."""
        results = await asyncio.gather(
            provider.publish("anchor-1", b"a"),
            provider.publish("anchor-1", b"b"),
            return_exceptions=True,
        )
        successes = [r for r in results if not isinstance(r, Exception)]
        failures = [r for r in results if isinstance(r, Exception)]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], AnchorAlreadyPublishedError)

    async def test_different_anchor_ids_do_not_conflict(self, provider):
        await provider.publish("anchor-1", b"a")
        await provider.publish("anchor-2", b"b")  # must not raise


class TestFetchMissingAnchor:
    async def test_fetch_of_a_never_published_anchor_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.fetch("s3://evidence-anchors/never-published.anchor.json")

    async def test_fetch_of_a_non_s3_ref_raises_file_not_found(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.fetch("/some/local/path.anchor.json")


class TestObjectLockRetention:
    async def test_retention_days_sets_object_lock_mode_and_retain_until(self, fake_client):
        provider = S3ObjectLockAnchorProvider(
            "evidence-anchors", client=fake_client, retention_days=30
        )
        await provider.publish("anchor-1", b"data")
        call = fake_client.put_calls[0]
        assert call["ObjectLockMode"] == "COMPLIANCE"
        assert call["ObjectLockRetainUntilDate"] > datetime.now(UTC)

    async def test_no_retention_days_means_no_object_lock_kwargs_sent(self, fake_client):
        provider = S3ObjectLockAnchorProvider("evidence-anchors", client=fake_client)
        await provider.publish("anchor-1", b"data")
        call = fake_client.put_calls[0]
        assert "ObjectLockMode" not in call
        assert "ObjectLockRetainUntilDate" not in call


class TestUnrelatedClientErrorsPropagate:
    async def test_a_non_precondition_client_error_is_not_swallowed(self, fake_client):
        def _raise_access_denied(**kwargs):
            raise ClientError({"Error": {"Code": "AccessDenied", "Message": "denied"}}, "PutObject")

        fake_client.put_object = _raise_access_denied
        provider = S3ObjectLockAnchorProvider("evidence-anchors", client=fake_client)
        with pytest.raises(ClientError):
            await provider.publish("anchor-1", b"data")


class TestFullAnchorPipelineAgainstTheRealProtocol:
    """End-to-end through the real, unmodified `audit_anchor.py`
    pipeline (build_and_sign_anchor -> publish_anchor ->
    verify_anchor_from_provider), proving S3ObjectLockAnchorProvider
    is a genuine drop-in for AuditAnchorProvider -- no call site in
    audit_anchor.py changes to use it."""

    async def test_compromise_detection_works_through_the_s3_provider(self, provider, key_provider):
        records = (
            _record("e1", None, "hash1"),
            _record("e2", "hash1", "hash2"),
        )
        bundle = build_evidence_bundle(list(records), org_id="org-1", bundle_id="bundle-1")
        key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        record = build_and_sign_anchor(bundle, key_id, dek, anchor_id="anchor-1")
        published = await publish_anchor(record, provider)
        assert published.destination_ref is not None

        # Untampered: verifying against the same freshly-recomputed
        # digest reports VALID.
        result = await verify_anchor_from_provider(
            current_bundle_digest=bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert result.status == AnchorVerificationStatus.VALID

        # Tampered: the "current" digest (as if the primary DB chain
        # had been regenerated forward after a tamper) no longer
        # matches what was anchored to S3 before the tamper.
        tampered_result = await verify_anchor_from_provider(
            current_bundle_digest="forged-digest-after-tamper",
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert tampered_result.status == AnchorVerificationStatus.DIGEST_MISMATCH
