# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Isolated Persona Sandbox protocol candidate, NOT a credential issuer.

No public route or canonical IDENTITY_VERIFIED write is installed. A sandbox
approval remains SANDBOX_SIMULATED and cannot authorize reusable credentials.
Real provider qualification requires operator-enrolled sandbox access; injected
HTTP transports are always identified as synthetic protocol evidence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import stat
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import httpx
from sqlalchemy import text

from responsibleai.data_governance.tenant_controller import postgres_identity
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.environment import is_production

AUDIENCE = "whitepact:persona-sandbox-integration:v1"
API = "https://api.withpersona.com"
VERSION = "2026-09-29"


class PersonaSandboxRefusedError(ValueError):
    """No identity attestation or execution authority is issued."""


def _bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise PersonaSandboxRefusedError("Duplicate JSON field")
        result[key] = value
    return result


def _timestamp(value):
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
        return parsed.timestamp()
    except (AttributeError, TypeError, ValueError) as exc:
        raise PersonaSandboxRefusedError("Ambiguous provider timestamp") from exc


def verify_persona_signature(body: bytes, header: str, webhook_secrets: tuple[bytes, ...]):
    """Persona's raw-body HMAC protocol, including rotation and bounded age."""
    if type(body) is not bytes or len(body) > 524288 or not webhook_secrets:
        raise PersonaSandboxRefusedError("Webhook input refused")
    if type(header) is not str or len(header) > 4096:
        raise PersonaSandboxRefusedError("Webhook signature refused")
    for pair in header.split():
        matched = re.fullmatch(r"t=([0-9]{10,12}),v1=([0-9a-fA-F]{64})", pair)
        if not matched or not time.time() - 300 <= int(matched[1]) <= time.time() + 30:
            continue
        signed = matched[1].encode("ascii") + b"." + body
        if any(
            hmac.compare_digest(
                hmac.new(secret, signed, hashlib.sha256).hexdigest(), matched[2].lower()
            )
            for secret in webhook_secrets
        ):
            return
    raise PersonaSandboxRefusedError("Webhook signature or timestamp refused")


@dataclass(frozen=True)
class PersonaSandboxPolicy:
    deployment_id: str
    database_identity: str
    provider_environment_id: str
    provider_organization_id: str
    template_id: str
    template_version_id: str
    policy_version: str
    audience: str = AUDIENCE
    expires_in_seconds: int = 1800

    def validate(self):
        if (
            is_production()
            or os.environ.get("WHITEPACT_ENV") != "development"
            or self.audience != AUDIENCE
            or type(self.expires_in_seconds) is not int
            or not 60 <= self.expires_in_seconds <= 3600
            or any(
                type(value) is not str or not value
                for key, value in asdict(self).items()
                if key != "expires_in_seconds"
            )
            or not re.fullmatch(r"itmpl_[A-Za-z0-9]+", self.template_id)
            or not re.fullmatch(r"itmplv_[A-Za-z0-9]+", self.template_version_id)
        ):
            raise PersonaSandboxRefusedError("Isolated development sandbox policy required")


class PersonaSandboxAdapter:
    """Internal, isolated inquiry/receipt ledger; never a production verifier."""

    def __init__(
        self, engine, policy, *, api_key, webhook_secrets, ledger_path, _test_transport=None
    ):
        policy.validate()
        if (
            type(api_key) is not str
            or not api_key.startswith("persona_sandbox_")
            or len(api_key) < 40
            or type(webhook_secrets) is not tuple
            or not 1 <= len(webhook_secrets) <= 2
            or any(type(secret) is not bytes or len(secret) < 32 for secret in webhook_secrets)
        ):
            raise PersonaSandboxRefusedError(
                "Enrolled sandbox API and webhook credentials required"
            )
        self.engine, self.policy = engine, policy
        self._key, self._secrets, self._transport = api_key, webhook_secrets, _test_transport
        self.path = Path(ledger_path)
        parent = self.path.parent.stat()
        if (
            not self.path.is_absolute()
            or self.path.parent.resolve() != self.path.parent
            or parent.st_uid != os.getuid()
            or stat.S_IMODE(parent.st_mode) & 0o077
        ):
            raise PersonaSandboxRefusedError("Private isolated ledger directory required")
        try:
            descriptor = os.open(
                self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600
            )
            created = True
        except FileExistsError:
            descriptor = os.open(self.path, os.O_RDWR | os.O_NOFOLLOW)
            created = False
        try:
            info = os.fstat(descriptor)
            if (
                not stat.S_ISREG(info.st_mode)
                or info.st_nlink != 1
                or info.st_uid != os.getuid()
                or stat.S_IMODE(info.st_mode) != 0o600
            ):
                raise PersonaSandboxRefusedError("Private regular ledger file required")
        finally:
            os.close(descriptor)
        self.digest = hashlib.sha256(_bytes(asdict(policy))).hexdigest()
        with self._ledger() as store:
            marker = store.execute("PRAGMA application_id").fetchone()[0]
            if created:
                store.execute("PRAGMA application_id=1464881986")
            elif marker != 1464881986:
                raise PersonaSandboxRefusedError("Not an established isolated Persona ledger")
            store.execute(
                "CREATE TABLE IF NOT EXISTS policy(id INTEGER PRIMARY KEY CHECK(id=1),digest TEXT NOT NULL)"
            )
            store.execute("INSERT OR IGNORE INTO policy VALUES(1,?)", (self.digest,))
            if store.execute("SELECT digest FROM policy WHERE id=1").fetchone() != (self.digest,):
                raise PersonaSandboxRefusedError("Ledger deployment or policy substitution")
            store.execute(
                "CREATE TABLE IF NOT EXISTS inquiries(reference TEXT PRIMARY KEY,inquiry TEXT UNIQUE,customer TEXT NOT NULL,tenant TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL CHECK(state IN ('RESERVED','PENDING','UNKNOWN','REVIEW_REQUIRED','SANDBOX_APPROVED','DENIED','CONFLICT','EXPIRED')),last_event REAL NOT NULL DEFAULT 0,provenance TEXT NOT NULL DEFAULT 'SANDBOX_SIMULATED' CHECK(provenance='SANDBOX_SIMULATED'))"
            )
            store.execute(
                "CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,digest TEXT NOT NULL,inquiry TEXT NOT NULL,state TEXT NOT NULL)"
            )

    @contextmanager
    def _ledger(self):
        store = sqlite3.connect(self.path, timeout=2)
        try:
            store.execute("BEGIN IMMEDIATE")
            yield store
            store.commit()
        except BaseException:
            store.rollback()
            raise
        finally:
            store.close()

    async def _scope(self):
        self.policy.validate()
        if hashlib.sha256(_bytes(asdict(self.policy))).hexdigest() != self.digest:
            raise PersonaSandboxRefusedError("Sandbox policy changed")
        with self._ledger() as store:
            if store.execute("SELECT digest FROM policy WHERE id=1").fetchone() != (self.digest,):
                raise PersonaSandboxRefusedError("Sandbox ledger policy changed")
        if self.engine.raw.dialect.name != "postgresql":
            raise PersonaSandboxRefusedError("Isolated PostgreSQL required")
        async with self.engine.raw.connect() as connection:
            name = await connection.scalar(text("SELECT current_database()"))
            identity = await postgres_identity(connection)
        if not name.startswith("wp_persona_sandbox_") or identity != self.policy.database_identity:
            raise PersonaSandboxRefusedError("Database identity or isolated namespace mismatch")

    async def _request(self, method, path, **kwargs):
        try:
            async with httpx.AsyncClient(
                base_url=API,
                timeout=10,
                follow_redirects=False,
                trust_env=False,
                transport=self._transport,
            ) as client:
                response = await client.request(
                    method,
                    path,
                    headers={
                        "Authorization": f"Bearer {self._key}",
                        "Persona-Version": VERSION,
                        "Content-Type": "application/json",
                        "Key-Inflection": "kebab",
                        **kwargs.pop("headers", {}),
                    },
                    **kwargs,
                )
        except httpx.RequestError as exc:
            raise PersonaSandboxRefusedError(
                "Provider request unavailable; no automatic retry"
            ) from exc
        if response.status_code not in (200, 201):
            raise PersonaSandboxRefusedError("Provider request refused")
        if (
            response.headers.get("Persona-Environment-Id") != self.policy.provider_environment_id
            or response.headers.get("Persona-Organization-Id")
            != self.policy.provider_organization_id
        ):
            raise PersonaSandboxRefusedError("Provider environment or organization mismatch")
        try:
            return json.loads(response.content, object_pairs_hook=_unique)["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise PersonaSandboxRefusedError("Provider response malformed") from exc

    def _binding(self, data, reference, inquiry=None):
        try:
            identifier, attributes, relationships = (
                data["id"],
                data["attributes"],
                data["relationships"],
            )
            if (
                data["type"] != "inquiry"
                or not re.fullmatch(r"inq_[A-Za-z0-9]+", identifier)
                or (inquiry is not None and identifier != inquiry)
                or attributes["reference-id"] != reference
                or relationships["inquiry-template"]["data"]["id"] != self.policy.template_id
                or relationships["inquiry-template-version"]["data"]["id"]
                != self.policy.template_version_id
            ):
                raise PersonaSandboxRefusedError(
                    "Inquiry subject, tenant or policy binding mismatch"
                )
            if attributes.get("expires-at") and _timestamp(attributes["expires-at"]) <= time.time():
                raise PersonaSandboxRefusedError("Provider inquiry expired")
            return identifier, attributes["status"]
        except (KeyError, TypeError) as exc:
            raise PersonaSandboxRefusedError("Inquiry binding missing") from exc

    async def start(self, *, session_token, csrf, tenant_id):
        await self._scope()
        principal = await WebIdentityRepository(self.engine).get_principal(session_token)
        if (
            principal is None
            or principal.org_id != tenant_id
            or not csrf
            or not hmac.compare_digest(
                principal.csrf_hash, hashlib.sha256(csrf.encode()).hexdigest()
            )
        ):
            raise PersonaSandboxRefusedError("Current tenant session and CSRF required")
        reference = secrets.token_hex(32)
        with self._ledger() as store:
            store.execute(
                "INSERT INTO inquiries(reference,customer,tenant,expires,state) VALUES(?,?,?,?,?)",
                (
                    reference,
                    principal.user_id,
                    tenant_id,
                    time.time() + self.policy.expires_in_seconds,
                    "RESERVED",
                ),
            )
        try:
            data = await self._request(
                "POST",
                "/api/v1/inquiries",
                headers={"Idempotency-Key": reference},
                json={
                    "data": {
                        "attributes": {
                            "inquiry-template-id": self.policy.template_id,
                            "reference-id": reference,
                        }
                    }
                },
            )
            identifier, _ = self._binding(data, reference)
        except PersonaSandboxRefusedError:
            with self._ledger() as store:
                store.execute(
                    "UPDATE inquiries SET state='UNKNOWN' WHERE reference=?", (reference,)
                )
            raise
        with self._ledger() as store:
            store.execute(
                "UPDATE inquiries SET inquiry=?,state='PENDING' WHERE reference=? AND state='RESERVED'",
                (identifier, reference),
            )
        return {
            "inquiry_id": identifier,
            "provenance": "SANDBOX_SIMULATED",
            "canonical_issuance_allowed": False,
        }

    def _receipt(self, row, *, duplicate=False):
        reference, inquiry, customer, tenant, expires, state, _ = row[:7]
        return {
            "inquiry_id": inquiry,
            "customer_id": customer,
            "tenant_id": tenant,
            "outcome": "EXPIRED" if time.time() >= expires else state,
            "provenance": "SANDBOX_SIMULATED",
            "provider": "persona-sandbox",
            "provider_environment_id": self.policy.provider_environment_id,
            "deployment_id": self.policy.deployment_id,
            "database_identity": self.policy.database_identity,
            "policy_version": self.policy.policy_version,
            "audience": self.policy.audience,
            "canonical_issuance_allowed": False,
            "duplicate": duplicate,
            "evidence_mode": "SYNTHETIC_PROTOCOL_FIXTURE"
            if self._transport is not None
            else "PROVIDER_NETWORK",
        }

    async def handle_webhook(self, body, signature):
        await self._scope()
        verify_persona_signature(body, signature, self._secrets)
        try:
            event = json.loads(body, object_pairs_hook=_unique)["data"]
            event_id, attributes = event["id"], event["attributes"]
            inquiry = attributes["payload"]["data"]
            identifier = inquiry["id"]
            event_time = _timestamp(attributes["created-at"])
            if (
                event["type"] != "event"
                or not re.fullmatch(r"evt_[A-Za-z0-9]+", event_id)
                or type(attributes.get("name")) is not str
                or not re.fullmatch(r"inquiry\.[a-z-]+", attributes["name"])
                or event_time > time.time() + 30
            ):
                raise PersonaSandboxRefusedError("Provider event identity or time refused")
        except (ValueError, KeyError, TypeError) as exc:
            raise PersonaSandboxRefusedError("Webhook event malformed") from exc
        digest = hashlib.sha256(body).hexdigest()
        conflict = False
        with self._ledger() as store:
            previous = store.execute(
                "SELECT digest,inquiry FROM events WHERE id=?", (event_id,)
            ).fetchone()
            if previous:
                if previous != (digest, identifier):
                    store.execute(
                        "UPDATE inquiries SET state='CONFLICT' WHERE inquiry=?", (previous[1],)
                    )
                    conflict = True
                else:
                    row = store.execute(
                        "SELECT * FROM inquiries WHERE inquiry=?", (identifier,)
                    ).fetchone()
                    return self._receipt(row, duplicate=True)
            else:
                row = store.execute(
                    "SELECT * FROM inquiries WHERE inquiry=?", (identifier,)
                ).fetchone()
                if row is None:
                    raise PersonaSandboxRefusedError(
                        "Inquiry was not issued by this isolated controller"
                    )
                store.execute(
                    "INSERT INTO events VALUES(?,?,?,'PROCESSING')", (event_id, digest, identifier)
                )
                # If a worker dies before independent API confirmation, no old
                # approval may remain effective and duplicate delivery is inert.
                store.execute(
                    "UPDATE inquiries SET state='REVIEW_REQUIRED' WHERE inquiry=?", (identifier,)
                )
        if conflict:
            raise PersonaSandboxRefusedError("Conflicting event replay")
        decision = "DENIED"
        try:
            self._binding(inquiry, row[0], identifier)
            actual = await self._request("GET", f"/api/v1/inquiries/{identifier}")
            _, api_status = self._binding(actual, row[0], identifier)
            if (
                attributes["name"] == "inquiry.approved"
                and inquiry["attributes"]["status"] == api_status == "approved"
            ):
                decision = "SANDBOX_APPROVED"
            elif (
                attributes["name"] == "inquiry.completed"
                and inquiry["attributes"]["status"] == api_status == "completed"
            ):
                decision = "PENDING"
        except PersonaSandboxRefusedError:
            decision = "DENIED"
        with self._ledger() as store:
            current = store.execute(
                "SELECT * FROM inquiries WHERE inquiry=?", (identifier,)
            ).fetchone()
            if (
                row[5] in {"DENIED", "CONFLICT", "UNKNOWN", "EXPIRED", "REVIEW_REQUIRED"}
                or current[5] != "REVIEW_REQUIRED"
                or event_time < row[6]
                or event_time < row[4] - self.policy.expires_in_seconds - 30
                or (row[5] == "SANDBOX_APPROVED" and decision != "SANDBOX_APPROVED")
            ):
                decision = "CONFLICT"
            if time.time() >= row[4]:
                decision = "EXPIRED"
            store.execute(
                "UPDATE inquiries SET state=?,last_event=? WHERE inquiry=?",
                (decision, event_time, identifier),
            )
            store.execute("UPDATE events SET state=? WHERE id=?", (decision, event_id))
            result = store.execute(
                "SELECT * FROM inquiries WHERE inquiry=?", (identifier,)
            ).fetchone()
        return self._receipt(result)
