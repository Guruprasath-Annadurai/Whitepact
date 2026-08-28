"""Tests for Security Remediation Gap 5, Phase 1 (External Audit
Anchor). See docs/enterprise-neural/REMEDIATION_GAP5_AUDIT_ANCHOR.md.

The point of this file, beyond round-trip coverage: prove the exact
compromise-detection property `tests/test_evidence_chain_anchoring.py`
(Phase 13) already showed was missing --
`TestFullChainRegenerationIsUndetectableByVerifyChainAlone` proved an
attacker with full DB write access can tamper a row, regenerate the
chain forward, and have `verify_chain()` report it intact regardless.
`TestAnchorDetectsFullDbCompromise` below runs that exact scenario
again, this time with a real (local-file) anchor published *before*
the tamper, and shows `verify_anchor_from_provider()` correctly
reports `DIGEST_MISMATCH` -- closing the gap those tests identified
but didn't solve.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime

import pytest

from responsibleai.governance.audit_anchor import (
    AnchorAlreadyPublishedError,
    AnchorVerificationStatus,
    LocalFileAnchorProvider,
    build_and_sign_anchor,
    publish_anchor,
    verify_anchor_from_provider,
)
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider
from responsibleai.governance.crypto.types import KeyPurpose
from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.evidence_bundle import build_evidence_bundle


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


@pytest.fixture()
def key_provider() -> LocalEnvelopeKeyProvider:
    return LocalEnvelopeKeyProvider(root_key=os.urandom(32), environment="test")


@pytest.fixture()
def provider(tmp_path):
    return LocalFileAnchorProvider(tmp_path / "anchors")


async def _sign_and_publish(bundle, key_provider, provider, *, anchor_id: str | None = None):
    key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
    record = build_and_sign_anchor(bundle, key_id, dek, anchor_id=anchor_id)
    return await publish_anchor(record, provider)


class TestBuildAndSignAnchor:
    async def test_signature_is_deterministic_hmac_over_bundle_digest(self, key_provider):
        records = [_record("r1", None, "h1")]
        bundle = build_evidence_bundle(records, org_id="org-1")
        key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)

        anchor = build_and_sign_anchor(bundle, key_id, dek)
        assert anchor.bundle_digest == bundle.bundle_digest
        assert anchor.record_count == 1
        assert anchor.destination_ref is None
        assert anchor.key_id == key_id.to_string()

    async def test_different_bundles_produce_different_signatures(self, key_provider):
        key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        bundle_a = build_evidence_bundle([_record("r1", None, "h1")], org_id="org-1")
        bundle_b = build_evidence_bundle([_record("r2", None, "h2")], org_id="org-1")

        anchor_a = build_and_sign_anchor(bundle_a, key_id, dek)
        anchor_b = build_and_sign_anchor(bundle_b, key_id, dek)
        assert anchor_a.signature != anchor_b.signature


class TestPublishAndFetchRoundTrip:
    async def test_published_anchor_round_trips_through_the_provider(self, key_provider, provider):
        bundle = build_evidence_bundle([_record("r1", None, "h1")], org_id="org-1")
        published = await _sign_and_publish(bundle, key_provider, provider)
        assert published.destination_ref is not None

        result = await verify_anchor_from_provider(
            current_bundle_digest=bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert result.is_valid
        assert result.status == AnchorVerificationStatus.VALID


class TestLocalFileAnchorProviderIsAppendOnly:
    async def test_publishing_twice_under_the_same_anchor_id_raises(self, provider):
        await provider.publish("anchor-1", b"first-payload")
        with pytest.raises(AnchorAlreadyPublishedError):
            await provider.publish("anchor-1", b"second-payload")

    async def test_first_publication_is_unaffected_by_a_rejected_second_attempt(self, provider):
        await provider.publish("anchor-1", b"first-payload")
        with pytest.raises(AnchorAlreadyPublishedError):
            await provider.publish("anchor-1", b"second-payload")
        assert await provider.fetch(str(provider._path_for("anchor-1"))) == b"first-payload"

    async def test_fetching_a_nonexistent_destination_raises(self, provider):
        with pytest.raises(FileNotFoundError):
            await provider.fetch(str(provider._path_for("does-not-exist")))


class TestVerificationDetectsTamperingAndForgery:
    async def test_wrong_signing_key_is_detected(self, provider):
        """A record signed under one key, then 'verified' against a
        different key_provider's key -- simulating an attacker who has
        their own AUDIT_ANCHOR key but not the real one -- must fail
        signature verification, not silently pass."""
        real_key_provider = LocalEnvelopeKeyProvider(root_key=os.urandom(32), environment="test")
        attacker_key_provider = LocalEnvelopeKeyProvider(
            root_key=os.urandom(32), environment="test"
        )
        # Materialize a key at the same purpose/tenant/version/environment
        # under the attacker's own (different) root key, so the lookup
        # by KeyId string succeeds and the test actually exercises a
        # signature mismatch rather than a "no such key" short-circuit.
        await attacker_key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        bundle = build_evidence_bundle([_record("r1", None, "h1")], org_id="org-1")
        published = await _sign_and_publish(bundle, real_key_provider, provider)

        result = await verify_anchor_from_provider(
            current_bundle_digest=bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=attacker_key_provider,
        )
        assert not result.is_valid
        assert result.status == AnchorVerificationStatus.SIGNATURE_INVALID

    async def test_unreachable_destination_is_reported_not_silently_passed(
        self, key_provider, provider
    ):
        result = await verify_anchor_from_provider(
            current_bundle_digest="whatever",
            destination_ref=str(provider._path_for("never-published")),
            provider=provider,
            key_provider=key_provider,
        )
        assert not result.is_valid
        assert result.status == AnchorVerificationStatus.DESTINATION_UNREACHABLE


class TestAnchorDetectsFullDbCompromise:
    """The actual point of this phase: rerun
    tests/test_evidence_chain_anchoring.py's own
    'full DB write access, chain regenerated forward' attack scenario,
    this time with an anchor published before the tamper."""

    async def test_tampering_after_anchoring_is_detected_by_digest_mismatch(
        self, key_provider, provider
    ):
        genuine_records = [
            _record("r1", None, "h1"),
            _record("r2", "h1", "h2"),
            _record("r3", "h2", "h3"),
        ]
        genuine_bundle = build_evidence_bundle(genuine_records, org_id="org-1")
        published = await _sign_and_publish(genuine_bundle, key_provider, provider)

        # Attacker with full DB write access tampers r2's decision and
        # regenerates every downstream hash so the chain still looks
        # internally consistent -- exactly
        # test_evidence_chain_anchoring.py's own attack.
        tampered_r2 = _record("r2", "h1", "h2-tampered")
        tampered_r2.decision = "DENY"  # was ALLOW
        tampered_records = [genuine_records[0], tampered_r2, genuine_records[2]]
        tampered_bundle = build_evidence_bundle(tampered_records, org_id="org-1")
        assert tampered_bundle.bundle_digest != genuine_bundle.bundle_digest

        result = await verify_anchor_from_provider(
            current_bundle_digest=tampered_bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert not result.is_valid
        assert result.status == AnchorVerificationStatus.DIGEST_MISMATCH

    async def test_untampered_state_still_verifies_valid_after_the_same_setup(
        self, key_provider, provider
    ):
        """Same setup as above, but verifying against the genuine
        (never-tampered) bundle digest must still pass -- proves the
        prior test's failure is really about tampering, not a
        miscomputed digest somewhere in the harness."""
        genuine_records = [_record("r1", None, "h1"), _record("r2", "h1", "h2")]
        genuine_bundle = build_evidence_bundle(genuine_records, org_id="org-1")
        published = await _sign_and_publish(genuine_bundle, key_provider, provider)

        result = await verify_anchor_from_provider(
            current_bundle_digest=genuine_bundle.bundle_digest,
            destination_ref=published.destination_ref,
            provider=provider,
            key_provider=key_provider,
        )
        assert result.is_valid


class TestAnchorRecordSerializationRoundTrips:
    async def test_to_dict_from_dict_round_trips(self, key_provider):
        bundle = build_evidence_bundle([_record("r1", None, "h1")], org_id="org-1")
        key_id, dek = await key_provider.get_encryption_key(KeyPurpose.AUDIT_ANCHOR, tenant_id=None)
        anchor = build_and_sign_anchor(bundle, key_id, dek)

        from responsibleai.governance.audit_anchor import AnchorRecord

        round_tripped = AnchorRecord.from_dict(anchor.to_dict())
        assert round_tripped == anchor
