# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for the MCP Trust/Supply-Chain Scanner (SPEC.md Section 7,
Phase 13). The one hard requirement this enforces throughout: every
finding is VERIFIED_FACT / INFERRED_SIGNAL / UNKNOWN, never a single
opaque score.
"""

from __future__ import annotations

import pytest

from responsibleai.db import PublicIncidentRepository, create_engine
from responsibleai.supplychain import (
    McpServerManifest,
    McpToolDescriptor,
    SupplyChainScanner,
    Verdict,
)


def _clean_manifest() -> McpServerManifest:
    return McpServerManifest(
        name="acme-tools",
        publisher="Acme Inc",
        tools=[McpToolDescriptor(name="search_web", description="Search the web for a query.")],
    )


class TestConfusableCharacterCheck:
    async def test_clean_ascii_name_is_verified_fact_clean(self) -> None:
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(_clean_manifest())
        finding = next(f for f in findings if f.check == "confusable_characters")
        assert finding.verdict == Verdict.VERIFIED_FACT
        assert "No known confusable" in finding.summary

    async def test_cyrillic_a_in_server_name_detected(self) -> None:
        manifest = McpServerManifest(name="rаi_tools", tools=[])  # Cyrillic а
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(manifest)
        finding = next(f for f in findings if f.check == "confusable_characters")
        assert finding.verdict == Verdict.VERIFIED_FACT
        assert "server_name" in finding.detail["matches"]

    async def test_confusable_in_tool_name_detected(self) -> None:
        manifest = McpServerManifest(
            name="clean-server",
            tools=[McpToolDescriptor(name="scаn", description="scan things")],  # Cyrillic а
        )
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(manifest)
        finding = next(f for f in findings if f.check == "confusable_characters")
        assert finding.verdict == Verdict.VERIFIED_FACT
        assert any(key.startswith("tool:") for key in finding.detail["matches"])

    async def test_no_tools_no_false_positive(self) -> None:
        manifest = McpServerManifest(name="plain-name", tools=[])
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(manifest)
        finding = next(f for f in findings if f.check == "confusable_characters")
        assert finding.detail == {}


class TestToolDescriptionScan:
    async def test_clean_descriptions_are_inferred_signal_clean(self) -> None:
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(_clean_manifest())
        finding = next(f for f in findings if f.check == "tool_description_scan")
        assert finding.verdict == Verdict.INFERRED_SIGNAL
        assert "No known-bad" in finding.summary

    async def test_pii_in_description_flagged(self) -> None:
        manifest = McpServerManifest(
            name="s",
            tools=[
                McpToolDescriptor(
                    name="t", description="Contact us at leak@example.com for support"
                )
            ],
        )
        scanner = SupplyChainScanner()
        findings = scanner.scan_offline(manifest)
        finding = next(f for f in findings if f.check == "tool_description_scan")
        assert finding.verdict == Verdict.INFERRED_SIGNAL
        assert "t" in finding.detail["flagged_tools"]

    async def test_always_inferred_signal_never_verified_fact(self) -> None:
        """A content-pattern match is a heuristic no matter the result --
        this check must never claim VERIFIED_FACT in either direction."""
        clean_scanner = SupplyChainScanner()
        clean_finding = next(
            f
            for f in clean_scanner.scan_offline(_clean_manifest())
            if f.check == "tool_description_scan"
        )
        assert clean_finding.verdict != Verdict.VERIFIED_FACT

        dirty_manifest = McpServerManifest(
            name="s",
            tools=[McpToolDescriptor(name="t", description="I will kill you")],
        )
        dirty_finding = next(
            f
            for f in clean_scanner.scan_offline(dirty_manifest)
            if f.check == "tool_description_scan"
        )
        assert dirty_finding.verdict != Verdict.VERIFIED_FACT


class TestKnownIncidentsCheck:
    @pytest.fixture()
    async def incident_repo(self):
        engine = create_engine(":memory:")
        await engine.init()
        yield PublicIncidentRepository(engine)
        await engine.close()

    async def test_no_incident_repo_supplied_skips_check(self) -> None:
        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest())
        assert not any(f.check == "known_incidents" for f in report.findings)

    async def test_no_matching_incidents_is_unknown_not_safe(self, incident_repo) -> None:
        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest(), incident_repo=incident_repo)
        finding = next(f for f in report.findings if f.check == "known_incidents")
        assert finding.verdict == Verdict.UNKNOWN
        assert "not evidence of safety" in finding.summary

    async def test_matching_incident_is_verified_fact(self, incident_repo) -> None:
        await incident_repo.submit(
            title="Data leak",
            description="Leaked user data via a tool call.",
            incident_type="data_leak",
            severity="HIGH",
            affected_model="acme-tools",
            affected_provider="Acme Inc",
            reporter_name=None,
            reporter_contact=None,
            evidence=None,
            tags=None,
        )
        record = await incident_repo.list_pending()
        await incident_repo.approve(record[0]["id"], reviewed_by="admin")

        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest(), incident_repo=incident_repo)
        finding = next(f for f in report.findings if f.check == "known_incidents")
        assert finding.verdict == Verdict.VERIFIED_FACT
        assert len(finding.detail["incidents"]) == 1


class TestSupplyChainReport:
    async def test_report_never_produces_a_single_score(self) -> None:
        """SPEC.md's one hard requirement: findings are returned as a
        list of per-check verdicts, never collapsed into a single
        opaque number."""
        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest())
        d = report.to_dict()
        assert "findings" in d
        assert isinstance(d["findings"], list)
        assert not any(key in d for key in ("score", "trust_score", "rating"))
        for finding in d["findings"]:
            assert finding["verdict"] in {"VERIFIED_FACT", "INFERRED_SIGNAL", "UNKNOWN"}

    async def test_findings_by_verdict_filters_correctly(self) -> None:
        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest())
        verified = report.findings_by_verdict(Verdict.VERIFIED_FACT)
        assert all(f.verdict == Verdict.VERIFIED_FACT for f in verified)

    async def test_report_id_and_server_name_populated(self) -> None:
        scanner = SupplyChainScanner()
        report = await scanner.scan(_clean_manifest())
        assert report.report_id
        assert report.server_name == "acme-tools"
