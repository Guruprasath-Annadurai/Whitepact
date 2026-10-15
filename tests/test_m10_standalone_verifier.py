# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-E Cryptographic Evidence Standalone Verifier Suite (Section 6).

Verifies:
1. Merkle witness DAG & hash chain integrity across evidence records.
2. Independent verification: never trusts the internal verdict field; detects any tampering.
3. Sequence gap detection: detects missing, skipped, or out-of-order records.
4. Cryptographic Ed25519 signature verification for published heads.
5. Least-privilege file permissions (0o600 for keys, 0o700 for private dirs).
"""

from __future__ import annotations

import os
import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from responsibleai.governance.evidence import (
    _GENESIS_HASH,
    EvidenceRecord,
    compute_canonical_evidence_hash,
)
from responsibleai.governance.evidence_publication import (
    AppendOnlyWitnessLog,
    FileWitnessKeyStore,
    WitnessKeyError,
    WitnessPublicationError,
    publish_evidence_head,
    verify_publication_chain,
    verify_published_head,
)

ORG_ID = "org-crypto-m10"


def _make_evidence(
    seq: int,
    prev_h: str,
    action_type: str = "query_db",
    decision: str = "ALLOW",
) -> EvidenceRecord:
    rec_id = f"ev-{seq}"
    now_dt = datetime.now(UTC)
    now = now_dt.isoformat()
    rec = EvidenceRecord(
        action_id=f"act-{seq}",
        agent_id="agent-1",
        identity_id="user-1",
        action_type=action_type,
        target="customer_table",
        argument_keys=["limit", "offset"],
        authority_delegated_by="org-admin",
        decision=decision,
        reason_codes=["POLICY_ALLOW"],
        evaluated_at=now_dt,
        evidence_id=rec_id,
        organization_id=ORG_ID,
        chain_sequence=seq,
        prev_hash=prev_h,
        recorded_at=now,
        purpose="regular data query",
        framework="custom",
        provider="anthropic",
        model="claude-3-5-sonnet",
    )
    rec.hash = compute_canonical_evidence_hash(prev_h, rec.to_dict())
    return rec


# ==============================================================================
# 1. Merkle Hash Chain Integrity & Standalone Verification
# ==============================================================================
def test_m10_evidence_chain_standalone_verification() -> None:
    """Verifies a 5-step valid evidence hash chain independently."""
    chain: list[EvidenceRecord] = []
    prev_h = _GENESIS_HASH

    for seq in range(1, 6):
        record = _make_evidence(seq, prev_h)
        chain.append(record)
        prev_h = record.hash

    # Verify chain from scratch without trusting internal stored hashes
    expected_prev = _GENESIS_HASH
    for record in chain:
        assert record.prev_hash == expected_prev
        # Independent recalculation: verify canonical hash matches
        computed = compute_canonical_evidence_hash(expected_prev, record.to_dict())
        assert record.hash == computed
        expected_prev = record.hash


# ==============================================================================
# 2. Tampering & Decision Manipulation Detection (Zero-Trust)
# ==============================================================================
def test_m10_tampered_decision_verdict_detected() -> None:
    """Exploit Hypothesis: Adversary modifies a DENY decision to ALLOW in the DB.
    Defense Guarantee: Standalone verifier recalculates the canonical hash and detects the forgery.
    """
    deny_record = _make_evidence(1, _GENESIS_HASH, decision="DENY")
    assert deny_record.decision == "DENY"

    # Attacker tries to tamper record.decision to "ALLOW"
    tampered_dict = deny_record.to_dict()
    tampered_dict["decision"] = "ALLOW"

    # Recalculating hash over tampered record produces mismatch with stored hash
    recomputed = compute_canonical_evidence_hash(_GENESIS_HASH, tampered_dict)
    assert recomputed != deny_record.hash

    # If attacker updates the hash to match the tampered content, the next record in the chain breaks
    next_record = _make_evidence(2, deny_record.hash)
    assert next_record.prev_hash == deny_record.hash
    assert next_record.prev_hash != recomputed


# ==============================================================================
# 3. Sequence Gap & Deletion Detection
# ==============================================================================
def test_m10_evidence_sequence_gap_detected() -> None:
    """Exploit Hypothesis: Adversary deletes record 2 from a sequence 1, 2, 3.
    Defense Guarantee: Verification fails due to broken hash link and sequence discontinuity.
    """
    rec1 = _make_evidence(1, _GENESIS_HASH)
    rec2 = _make_evidence(2, rec1.hash)
    rec3 = _make_evidence(3, rec2.hash)

    # Deleting rec2 leaves [rec1, rec3]
    gapped_chain = [rec1, rec3]

    # Check 1: Sequence number gap
    assert gapped_chain[1].chain_sequence != gapped_chain[0].chain_sequence + 1

    # Check 2: Hash chain broken
    assert gapped_chain[1].prev_hash != gapped_chain[0].hash


# ==============================================================================
# 4. Ed25519 Cryptographic Witness & Publication Chain Verification
# ==============================================================================
def test_m10_ed25519_witness_verification(tmp_path: Path) -> None:
    """Verifies cryptographic head signing and publication chain verification."""
    keystore = FileWitnessKeyStore.create(tmp_path / "keys")
    log = AppendOnlyWitnessLog(tmp_path / "witness_log")

    # Publish sequence of 3 heads
    h1 = "a" * 64
    h2 = "b" * 64
    h3 = "c" * 64

    now = datetime.now(UTC).isoformat()
    publish_evidence_head(
        keystore,
        log,
        organization_id=ORG_ID,
        chain_sequence=1,
        head_hash=h1,
        witnessed_at=now,
        opaque_reference=False,
    )
    publish_evidence_head(
        keystore,
        log,
        organization_id=ORG_ID,
        chain_sequence=2,
        head_hash=h2,
        witnessed_at=now,
        opaque_reference=False,
    )
    publish_evidence_head(
        keystore,
        log,
        organization_id=ORG_ID,
        chain_sequence=3,
        head_hash=h3,
        witnessed_at=now,
        opaque_reference=False,
    )

    # 1. Valid chain verification
    records = log.history(ORG_ID)
    assert len(records) == 3
    verify_publication_chain(records)

    # 2. Verify tip matches claimed head
    matched = verify_published_head(log, organization_id=ORG_ID, chain_sequence=3, head_hash=h3)
    assert matched.chain_sequence == 3
    assert matched.head_hash == h3

    # 3. Rollback detection (claiming sequence 2 when published tip is 3)
    with pytest.raises(
        WitnessPublicationError, match="database head rolled back behind the publication"
    ):
        verify_published_head(log, organization_id=ORG_ID, chain_sequence=2, head_hash=h2)

    # 4. Forged head detection (claiming different hash at sequence 3)
    with pytest.raises(WitnessPublicationError, match="does not match the published witness"):
        verify_published_head(log, organization_id=ORG_ID, chain_sequence=3, head_hash="f" * 64)


# ==============================================================================
# 5. File Permission Hardening (Least Privilege 0o600 / 0o700)
# ==============================================================================
def test_m10_private_key_file_permission_enforcement(tmp_path: Path) -> None:
    """Verifies that private keys are created with 0o600 permissions,
    and reading fails closed if permissions are widened to group/world accessible (0o644).
    """
    key_dir = tmp_path / "secure_keys"
    store = FileWitnessKeyStore.create(key_dir)

    key_file = store.private_dir / "current.key"
    assert key_file.is_file()

    # Verify initial mode is 0o600
    file_mode = stat.S_IMODE(key_file.stat().st_mode)
    assert file_mode & 0o077 == 0, f"Expected private permissions (0o600), got {oct(file_mode)}"

    # Widening permission to 0o644 (world readable) must trigger WitnessKeyError
    os.chmod(key_file, 0o644)
    with pytest.raises(WitnessKeyError, match="group or world accessible"):
        store.current_private()

    # Restoring 0o600 allows successful read
    os.chmod(key_file, 0o600)
    key_id, key = store.current_private()
    assert isinstance(key, Ed25519PrivateKey)
    assert key_id == store.current_key_id()
