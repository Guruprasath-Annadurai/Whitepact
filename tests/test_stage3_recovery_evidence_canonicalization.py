# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""V2 type/precision/collision and historical receipt refusal specifications."""

import hashlib
import json
import sqlite3
from dataclasses import replace
from datetime import UTC, date, datetime, time, timedelta, timezone, tzinfo
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from responsibleai.data_governance import operator_recovery_control as control
from responsibleai.data_governance.operator_recovery import (
    RecoveryAuthorizationError,
    RecoveryReceiptLedger,
)
from tests.test_operator_recovery_authorization import fixture_request


@pytest.mark.parametrize(
    "left,right",
    [
        (None, False),
        (True, 1),
        (1, 1.0),
        (0.0, -0.0),
        (b"\x00\xff", "00ff"),
        (UUID(int=1), str(UUID(int=1))),
        (Decimal("1.00"), Decimal("1.0")),
        (Decimal("-0.00"), Decimal("0.00")),
        (Decimal("9007199254740993.00000001"), Decimal("9007199254740993.00000002")),
        (Decimal("1"), 1),
        (date(2026, 10, 23), "2026-10-23"),
        (time(1, 2, 3, 4), time(1, 2, 3, 5)),
        (datetime(2026, 10, 23, microsecond=1), datetime(2026, 10, 23, microsecond=2)),
        (datetime(2026, 10, 23), datetime(2026, 10, 23, tzinfo=UTC)),
        (
            datetime(2026, 10, 23, tzinfo=UTC),
            datetime(2026, 10, 23, tzinfo=timezone(timedelta(hours=1))),
        ),
        (["bytes", "00ff"], b"\x00\xff"),
        ([1, 2], (1, 2)),
        ({"format": control.EVIDENCE_FORMAT, "rows": []}, []),
        ("\u00e9", "e\u0301"),
        (timedelta(microseconds=1), timedelta(microseconds=2)),
    ],
)
def test_distinct_types_and_precision_never_share_canonical_bytes(left, right):
    assert control._evidence_bytes(left) != control._evidence_bytes(right)


def test_exact_decimal_binary_and_timezone_semantics():
    assert control._evidence_value(Decimal("123.4500")) == ["decimal", 0, [1, 2, 3, 4, 5, 0, 0], -4]
    assert control._evidence_value(b"\x00\xff") == ["bytes", "00ff"]
    assert control._evidence_value(datetime(2026, 10, 23, 1, 2, 3, 4, tzinfo=UTC)) == [
        "datetime",
        "2026-10-23T01:02:03.000004+00:00",
        0,
        ["fixed", 0, "UTC"],
    ]
    assert control._evidence_value(datetime(2026, 10, 23))[-1] == ["naive"]
    zone = ZoneInfo("America/New_York")
    first = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    second = first.replace(fold=1)
    assert control._evidence_bytes(first) != control._evidence_bytes(second)


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        Decimal("NaN"),
        Decimal("Infinity"),
        {1: "ambiguous"},
        object(),
        set(),
        bytearray(b"x"),
    ],
)
def test_unknown_or_ambiguous_values_fail_closed(value):
    with pytest.raises(RecoveryAuthorizationError):
        control._evidence_bytes(value)


def test_unknown_timezone_is_rejected_without_calling_it():
    class UnknownZone(tzinfo):
        def utcoffset(self, value):
            raise AssertionError("Do not invoke unknown timezone code")

    with pytest.raises(RecoveryAuthorizationError, match="Unsupported.*timezone"):
        control._evidence_bytes(datetime(2026, 10, 23, tzinfo=UnknownZone()))
    with pytest.raises(RecoveryAuthorizationError, match="Ambiguous.*timezone"):
        control._evidence_bytes(time(1, tzinfo=ZoneInfo("America/New_York")))


def test_row_order_and_mapping_insertion_order_are_irrelevant():
    first = {"a": datetime(2026, 10, 23, tzinfo=UTC), "b": Decimal("1.000")}
    second = {"x": b"\x01", "y": [True, None]}
    assert control._snapshot_digest([first, second]) == control._snapshot_digest(
        [second, dict(reversed(list(first.items())))]
    )
    assert control._snapshot_digest([first]) != control._snapshot_digest([first, first])


def test_legacy_json_digest_is_unchanged_but_snapshot_format_is_explicitly_new():
    value = {"a": [1, True, None], "b": "\u00e9"}
    expected = hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()
    assert control._digest(value) == expected
    assert control._snapshot_digest([]) != control._digest([])
    assert control.EVIDENCE_FORMAT == "WHITEPACT-PG-RECOVERY-EVIDENCE-V2"


def test_old_signed_request_cannot_be_relabelled_as_current_evidence():
    manifest, _, _ = fixture_request()
    with pytest.raises(RecoveryAuthorizationError, match="Historical signed evidence"):
        control._require_manifest_format(manifest)
    current = replace(manifest, request_id="pg-evidence-v2:" + "a" * 32)
    control._require_manifest_format(current)
    assert current.canonical_bytes() != manifest.canonical_bytes()  # signatures bind the version


def test_legacy_control_schema_is_not_silently_migrated(tmp_path):
    path = tmp_path / "legacy.sqlite3"
    RecoveryReceiptLedger.initialize(path)
    with sqlite3.connect(path) as connection:
        connection.execute("CREATE TABLE recovery_operations(epoch INTEGER, request_id TEXT)")
    before = path.read_bytes()
    with pytest.raises(RecoveryAuthorizationError, match="Historical recovery evidence"):
        with control._control_connection(SimpleNamespace(ledger_path=path)):
            raise AssertionError("Historical ledger must not be admitted")
    assert path.read_bytes() == before


def test_unknown_receipt_format_is_rejected(tmp_path):
    path = tmp_path / "unknown.sqlite3"
    control.initialize_control_ledger(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO recovery_operations(request_id,manifest,signatures,profile_digest,phase,evidence_format,approved_evidence) VALUES('old','{}','{}','old','COMPLETE','UNKNOWN','{}')"
        )
    with pytest.raises(RecoveryAuthorizationError, match="Historical recovery evidence"):
        with control._control_connection(SimpleNamespace(ledger_path=path)):
            raise AssertionError("Unknown evidence format must not be admitted")


@pytest.mark.parametrize("change", ["legacy", "mutation", "missing", "malformed"])
def test_signed_evidence_cannot_be_reinterpreted_or_relabelled(change):
    manifest, _, _ = fixture_request()
    evidence = {"evidence_format": control.EVIDENCE_FORMAT, "source_digest": "a" * 64}
    manifest = replace(manifest, evidence_digest=control._digest(evidence))
    control._require_completed_evidence({"approved_evidence": json.dumps(evidence)}, manifest)
    if change == "legacy":
        evidence["evidence_format"] = "LEGACY"
        # Even a matching old signed digest cannot be treated as current.
        manifest = replace(manifest, evidence_digest=control._digest(evidence))
    elif change == "mutation":
        evidence["source_digest"] = "b" * 64
    row = {"approved_evidence": json.dumps(evidence)}
    if change == "missing":
        row = {}
    elif change == "malformed":
        row = {"approved_evidence": "{"}
    with pytest.raises(RecoveryAuthorizationError, match="format or digest changed"):
        control._require_completed_evidence(row, manifest)
