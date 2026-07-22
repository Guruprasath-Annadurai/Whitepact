"""Tests for PublicIncidentRepository — the public, crowd-reported, moderated
AI Incident Database (compliance-adjacent: the "CVE database for AI failures")."""

from __future__ import annotations

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.db.public_incident_repository import PublicIncidentRepository


@pytest.fixture()
async def db():
    engine = create_engine(":memory:")
    await engine.init()
    yield engine
    await engine.close()


@pytest.fixture()
async def repo(db):
    return PublicIncidentRepository(db)


async def _submit(repo, **overrides):
    defaults = dict(
        title="A test incident title",
        description="A sufficiently long description of what happened here.",
        incident_type="jailbreak",
        severity="high",
        affected_model="test-model",
        affected_provider="test-provider",
    )
    defaults.update(overrides)
    return await repo.submit(**defaults)


class TestSubmission:
    async def test_submit_starts_pending_review(self, repo):
        r = await _submit(repo)
        assert r["status"] == "PENDING_REVIEW"
        assert r["public_id"] is None

    async def test_submit_stores_reporter_and_evidence(self, repo):
        r = await _submit(
            repo, reporter_name="alice", reporter_contact="alice@example.com",
            evidence={"urls": ["https://example.com"]}, tags=["jailbreak", "roleplay"],
        )
        assert r["reporter_name"] == "alice"
        assert r["reporter_contact"] == "alice@example.com"
        assert r["evidence"] == {"urls": ["https://example.com"]}
        assert r["tags"] == ["jailbreak", "roleplay"]

    async def test_pending_report_not_in_published_list(self, repo):
        await _submit(repo)
        published = await repo.list_published()
        assert published == []

    async def test_pending_report_not_visible_by_public_id(self, repo):
        r = await _submit(repo)
        assert r["public_id"] is None
        assert await repo.get_by_public_id("RAI-2026-0001") is None


class TestModerationApprove:
    async def test_approve_assigns_sequential_public_id(self, repo):
        r1 = await _submit(repo, title="first")
        r2 = await _submit(repo, title="second")
        a1 = await repo.approve(r1["id"], reviewed_by="admin")
        a2 = await repo.approve(r2["id"], reviewed_by="admin")
        assert a1["public_id"] == "RAI-2026-0001"
        assert a2["public_id"] == "RAI-2026-0002"

    async def test_approve_sets_published_status_and_timestamp(self, repo):
        r = await _submit(repo)
        approved = await repo.approve(r["id"], reviewed_by="admin")
        assert approved["status"] == "PUBLISHED"
        assert approved["published_at"] is not None
        assert approved["reviewed_by"] == "admin"

    async def test_approve_computes_hash_chain(self, repo):
        r1 = await _submit(repo, title="first")
        r2 = await _submit(repo, title="second")
        a1 = await repo.approve(r1["id"], reviewed_by="admin")
        a2 = await repo.approve(r2["id"], reviewed_by="admin")
        assert len(a1["entry_hash"]) == 64
        assert a1["prev_hash"] == "0" * 64
        assert a2["prev_hash"] == a1["entry_hash"]

    async def test_approve_unknown_id_returns_none(self, repo):
        assert await repo.approve("does-not-exist", reviewed_by="admin") is None

    async def test_approve_already_reviewed_returns_none(self, repo):
        r = await _submit(repo)
        await repo.approve(r["id"], reviewed_by="admin")
        assert await repo.approve(r["id"], reviewed_by="admin2") is None

    async def test_published_entry_visible_via_public_id(self, repo):
        r = await _submit(repo)
        approved = await repo.approve(r["id"], reviewed_by="admin")
        fetched = await repo.get_by_public_id(approved["public_id"])
        assert fetched is not None
        assert fetched["title"] == r["title"]

    async def test_published_entry_redacts_reporter_contact_by_default(self, repo):
        r = await _submit(repo, reporter_contact="secret@example.com")
        approved = await repo.approve(r["id"], reviewed_by="admin")
        fetched = await repo.get_by_public_id(approved["public_id"])
        assert "reporter_contact" not in fetched

    async def test_published_entry_in_public_listing(self, repo):
        r = await _submit(repo)
        await repo.approve(r["id"], reviewed_by="admin")
        published = await repo.list_published()
        assert len(published) == 1
        assert "reporter_contact" not in published[0]


class TestModerationReject:
    async def test_reject_sets_status_and_reason(self, repo):
        r = await _submit(repo)
        rejected = await repo.reject(r["id"], reviewed_by="admin", reason="insufficient evidence")
        assert rejected["status"] == "REJECTED"
        assert rejected["rejection_reason"] == "insufficient evidence"

    async def test_rejected_report_never_appears_published(self, repo):
        r = await _submit(repo)
        await repo.reject(r["id"], reviewed_by="admin", reason="spam")
        assert await repo.list_published() == []

    async def test_reject_unknown_id_returns_none(self, repo):
        assert await repo.reject("does-not-exist", reviewed_by="admin", reason="x") is None


class TestListPending:
    async def test_list_pending_excludes_reviewed(self, repo):
        r1 = await _submit(repo, title="pending one")
        r2 = await _submit(repo, title="pending two")
        await repo.approve(r1["id"], reviewed_by="admin")

        pending = await repo.list_pending()
        assert len(pending) == 1
        assert pending[0]["id"] == r2["id"]

    async def test_list_pending_includes_reporter_contact(self, repo):
        await _submit(repo, reporter_contact="secret@example.com")
        pending = await repo.list_pending()
        assert pending[0]["reporter_contact"] == "secret@example.com"


class TestCheckEndpointBackend:
    async def test_check_matches_exact_model_and_provider(self, repo):
        r = await _submit(repo, affected_model="gpt-x", affected_provider="openai")
        await repo.approve(r["id"], reviewed_by="admin")

        matches = await repo.check("gpt-x", "openai")
        assert len(matches) == 1

    async def test_check_case_insensitive(self, repo):
        r = await _submit(repo, affected_model="GPT-X", affected_provider="OpenAI")
        await repo.approve(r["id"], reviewed_by="admin")

        matches = await repo.check("gpt-x", "openai")
        assert len(matches) == 1

    async def test_check_no_match_returns_empty(self, repo):
        r = await _submit(repo, affected_model="gpt-x", affected_provider="openai")
        await repo.approve(r["id"], reviewed_by="admin")

        matches = await repo.check("claude", "anthropic")
        assert matches == []

    async def test_check_excludes_unpublished(self, repo):
        await _submit(repo, affected_model="gpt-x", affected_provider="openai")
        matches = await repo.check("gpt-x", "openai")
        assert matches == []


class TestStatusUpdate:
    async def test_update_status_to_resolved(self, repo):
        r = await _submit(repo)
        approved = await repo.approve(r["id"], reviewed_by="admin")
        updated = await repo.update_status(approved["public_id"], "RESOLVED", reviewed_by="admin")
        assert updated["status"] == "RESOLVED"

    async def test_update_status_does_not_change_hash(self, repo):
        r = await _submit(repo)
        approved = await repo.approve(r["id"], reviewed_by="admin")
        updated = await repo.update_status(approved["public_id"], "DISPUTED", reviewed_by="admin")
        assert updated["entry_hash"] == approved["entry_hash"]
        assert updated["prev_hash"] == approved["prev_hash"]

    async def test_update_status_unknown_id_returns_none(self, repo):
        assert await repo.update_status("RAI-2026-9999", "RESOLVED", reviewed_by="admin") is None

    async def test_update_status_on_pending_report_returns_none(self, repo):
        await _submit(repo)
        # No public_id yet since it's unapproved — update_status looks up by
        # public_id, so this exercises the "not found" path correctly.
        assert await repo.update_status("RAI-2026-0001", "RESOLVED", reviewed_by="admin") is None


class TestVerifyChain:
    async def test_verify_intact_chain(self, repo):
        r1 = await _submit(repo, title="one")
        r2 = await _submit(repo, title="two")
        await repo.approve(r1["id"], reviewed_by="admin")
        await repo.approve(r2["id"], reviewed_by="admin")

        result = await repo.verify_chain()
        assert result["intact"] is True
        assert result["entries_checked"] == 2
        assert result["broken_links"] == []

    async def test_verify_empty_database(self, repo):
        result = await repo.verify_chain()
        assert result["intact"] is True
        assert result["entries_checked"] == 0

    async def test_verify_detects_tampering(self, repo, db):
        from sqlalchemy import update as sa_update

        from responsibleai.db.engine import public_incident_reports

        r = await _submit(repo)
        approved = await repo.approve(r["id"], reviewed_by="admin")

        # Directly tamper with a published entry's severity outside the
        # repository API, bypassing the hash chain entirely.
        async with db.raw.begin() as conn:
            await conn.execute(
                sa_update(public_incident_reports)
                .where(public_incident_reports.c.public_id == approved["public_id"])
                .values(severity="low")
            )

        result = await repo.verify_chain()
        assert result["intact"] is False
        assert len(result["broken_links"]) == 1
