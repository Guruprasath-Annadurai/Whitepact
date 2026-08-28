"""Enforced regression guard for the remediation directive's explicit
requirement: "Raw neural data must never enter audit evidence."

Per Gap 5's reproduction, this already held true today -- but only *by
construction* (no code path connects `governance/neural/` to
`governance_evidence`), not because anything actively prevents it. This
file turns that accidental truth into an enforced guard: a future
change wiring neural data into `EvidenceRecord`/`build_evidence_record()`
must fail one of these tests, not slip through silently.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

from responsibleai.governance.evidence import EvidenceRecord

_SRC_ROOT = Path(__file__).parent.parent / "src" / "responsibleai"

# Field-name substrings that would indicate raw signal/payload data --
# deliberately broad (a false positive here just means renaming a
# hypothetical future field, cheap; a false negative would defeat the
# guard's entire purpose).
_RAW_DATA_FIELD_MARKERS = ("payload", "signal", "waveform", "raw_data", "neural_data")


class TestEvidenceRecordHasNoRawDataShapedField:
    def test_no_field_name_suggests_raw_signal_or_payload_data(self) -> None:
        field_names = {f.name for f in dataclasses.fields(EvidenceRecord)}
        for name in field_names:
            for marker in _RAW_DATA_FIELD_MARKERS:
                assert marker not in name.lower(), (
                    f"EvidenceRecord.{name} looks like it could carry raw "
                    f"signal/payload data (matches marker {marker!r}) -- "
                    "argument_keys (names only, never values) is the only "
                    "argument-shaped field this record is allowed to have"
                )

    def test_argument_keys_is_the_only_argument_shaped_field(self) -> None:
        """The one field that carries anything about action arguments
        must stay names-only -- `governance/evidence.py`'s own
        docstring states this is deliberate. A second field for
        argument *values* would be exactly the kind of path raw neural
        signal data could travel through."""
        field_names = {f.name for f in dataclasses.fields(EvidenceRecord)}
        argument_shaped = {n for n in field_names if "argument" in n.lower()}
        assert argument_shaped == {"argument_keys"}


class TestNeuralModuleNeverConstructsEvidenceRecords:
    """Structural/text-scan guard (heuristic, documented as such --
    same discipline as `test_brain_policy_risk_boundary.py`'s own
    call-site guards): nothing under governance/neural/ may construct
    an `EvidenceRecord` or call `build_evidence_record()`/
    `EvidenceRepository.record()` directly. If a future phase wires
    neural evidence into the audit chain, it must go through an
    explicit, reviewed conversion this test can be updated to
    acknowledge -- not a silent, direct construction."""

    def test_no_neural_module_references_evidence_record_construction(self) -> None:
        neural_dir = _SRC_ROOT / "governance" / "neural"
        assert neural_dir.is_dir(), "expected governance/neural/ to exist"

        forbidden_patterns = (
            re.compile(r"\bEvidenceRecord\("),
            re.compile(r"\bbuild_evidence_record\("),
        )
        hits: list[str] = []
        for path in neural_dir.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for pattern in forbidden_patterns:
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        continue
                    if pattern.search(line):
                        hits.append(f"{path.relative_to(_SRC_ROOT)}: {stripped}")
        assert hits == [], (
            f"governance/neural/ code directly constructs audit evidence: {hits} -- "
            "if this is intentional new wiring, it must go through an explicit, "
            "reviewed conversion (never raw payload data), and this guard must be "
            "updated deliberately, not silently broken"
        )
