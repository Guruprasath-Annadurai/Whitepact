# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Didit Sandbox V3 webhook receiver. It is not an identity authority.

The handler verifies ``X-Signature-V2`` over Didit's canonical JSON, then
stores a bounded receipt. It never calls ``VerificationService`` and never
writes ``IDENTITY_VERIFIED``. ``X-Signature-Simple`` is not accepted.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sqlite3
import time
from pathlib import Path
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from responsibleai.environment import is_production

_MAX_BODY = 65_536
_MAX_ROWS = 200
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_STATUSES = frozenset(
    {
        "Approved",
        "Declined",
        "In Review",
        "Abandoned",
        "Resubmitted",
        "Not Started",
        "In Progress",
        "Kyc Expired",
    }
)
_HEX = re.compile(r"^[0-9a-fA-F]{64}$")


class DiditSandboxRefusedError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        self.status_code = status_code
        self.code = code
        super().__init__(code)


def sandbox_enabled() -> bool:
    return os.environ.get("WHITEPACT_DIDIT_SANDBOX") == "1" and not is_production()


def _secret(name: str) -> bytes | None:
    value = os.environ.get(name, "")
    if not value or len(value) < 32 or len(value) > 512:
        return None
    return value.encode("utf-8")


def shorten_floats(data: Any) -> Any:
    """Match Didit's canonical form: whole-valued floats become ints."""
    if isinstance(data, dict):
        return {key: shorten_floats(value) for key, value in data.items()}
    if isinstance(data, list):
        return [shorten_floats(item) for item in data]
    if isinstance(data, float) and data.is_integer():
        return int(data)
    return data


def canonical_json(body: Any) -> str:
    return json.dumps(
        shorten_floats(body),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DiditSandboxRefusedError(400, "malformed_json")
        result[key] = value
    return result


def _fresh(timestamp: str, *, now: float) -> bool:
    if not re.fullmatch(r"[0-9]{10,12}", timestamp):
        return False
    return abs(now - int(timestamp)) <= 300


def _signature_matches(canonical: str, header: str, secret: bytes) -> bool:
    if not _HEX.fullmatch(header):
        return False
    expected = hmac.new(secret, canonical.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.lower())


def verify_v2(
    body: dict[str, Any],
    *,
    signature: str,
    previous_signature: str,
    timestamp: str,
    secret: bytes,
    previous_secret: bytes | None,
    now: float,
) -> None:
    if not _fresh(timestamp, now=now):
        raise DiditSandboxRefusedError(401, "stale_timestamp")
    if str(body.get("timestamp", "")) != timestamp:
        raise DiditSandboxRefusedError(401, "timestamp_mismatch")
    canonical = canonical_json(body)
    if _signature_matches(canonical, signature, secret):
        return
    if previous_secret and previous_signature and _signature_matches(
        canonical, previous_signature, previous_secret
    ):
        return
    raise DiditSandboxRefusedError(401, "signature_rejected")


def _ledger_path() -> Path:
    configured = os.environ.get("WHITEPACT_DIDIT_SANDBOX_LEDGER", "")
    path = Path(configured) if configured else Path("/tmp/whitepact-didit-sandbox-ledger.sqlite")
    if not path.is_absolute():
        raise DiditSandboxRefusedError(503, "ledger_unavailable")
    return path


def _open_ledger(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(mode=0o700, exist_ok=True)
    if not path.exists():
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        os.close(descriptor)
    else:
        os.chmod(path, 0o600)
    connection = sqlite3.connect(path, timeout=2)
    connection.execute("PRAGMA journal_mode=DELETE")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS receipts (
            event_id TEXT PRIMARY KEY,
            received_at INTEGER NOT NULL,
            status TEXT NOT NULL,
            session_id TEXT NOT NULL,
            workflow_id TEXT NOT NULL,
            application_id TEXT NOT NULL,
            payload_sha256 TEXT NOT NULL
        )
        """
    )
    return connection


def _remember(body: dict[str, Any], payload_sha256: str, *, now: float) -> None:
    path = _ledger_path()
    connection = _open_ledger(path)
    try:
        count = connection.execute("SELECT COUNT(*) FROM receipts").fetchone()[0]
        if count >= _MAX_ROWS:
            connection.execute(
                """
                DELETE FROM receipts WHERE event_id IN (
                    SELECT event_id FROM receipts ORDER BY received_at ASC
                    LIMIT ?
                )
                """,
                (count - _MAX_ROWS + 1,),
            )
        try:
            connection.execute(
                """
                INSERT INTO receipts (
                    event_id, received_at, status, session_id, workflow_id,
                    application_id, payload_sha256
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    body["event_id"],
                    int(now),
                    body["status"],
                    body["session_id"],
                    body["workflow_id"],
                    body["application_id"],
                    payload_sha256,
                ),
            )
        except sqlite3.IntegrityError as exc:
            raise DiditSandboxRefusedError(409, "replayed_event") from exc
        connection.commit()
    finally:
        connection.close()
    os.chmod(path, 0o600)


def _require_identity(body: dict[str, Any]) -> None:
    application = os.environ.get("WHITEPACT_DIDIT_SANDBOX_APPLICATION_ID", "")
    workflow = os.environ.get("WHITEPACT_DIDIT_SANDBOX_WORKFLOW_ID", "")
    if not _UUID.fullmatch(application) or not _UUID.fullmatch(workflow):
        raise DiditSandboxRefusedError(503, "sandbox_not_configured")
    if not _same(str(body.get("application_id", "")), application):
        raise DiditSandboxRefusedError(403, "application_mismatch")
    if not _same(str(body.get("workflow_id", "")), workflow):
        raise DiditSandboxRefusedError(403, "workflow_mismatch")
    if body.get("environment") != "sandbox":
        raise DiditSandboxRefusedError(403, "environment_rejected")
    if body.get("webhook_type") != "status.updated":
        raise DiditSandboxRefusedError(403, "event_rejected")
    if body.get("status") not in _STATUSES:
        raise DiditSandboxRefusedError(403, "status_rejected")
    session_id = str(body.get("session_id", ""))
    event_id = str(body.get("event_id", ""))
    if not _UUID.fullmatch(session_id) or not _UUID.fullmatch(event_id):
        raise DiditSandboxRefusedError(403, "identity_malformed")
    allowed = {
        item.strip().lower()
        for item in os.environ.get("WHITEPACT_DIDIT_SANDBOX_SESSION_IDS", "").split(",")
        if item.strip()
    }
    if allowed and session_id.lower() not in allowed:
        raise DiditSandboxRefusedError(403, "session_mismatch")


def _same(left: str, right: str) -> bool:
    if len(left) != len(right):
        return False
    return hmac.compare_digest(left, right)


def assess_sandbox_event(
    payload: bytes,
    headers: dict[str, str],
    *,
    now: float | None = None,
) -> dict[str, str]:
    """Verify one sandbox delivery and store a non-sensitive receipt."""
    if not sandbox_enabled():
        raise DiditSandboxRefusedError(404, "sandbox_disabled")
    secret = _secret("WHITEPACT_DIDIT_SANDBOX_WEBHOOK_SECRET")
    if secret is None:
        raise DiditSandboxRefusedError(503, "sandbox_not_configured")
    if type(payload) is not bytes or not payload or len(payload) > _MAX_BODY:
        raise DiditSandboxRefusedError(400, "body_rejected")
    signature = ""
    previous = ""
    timestamp = ""
    simple = ""
    for name, value in headers.items():
        lowered = name.lower()
        if lowered == "x-signature-v2":
            signature = value
        elif lowered == "x-signature-v2-previous":
            previous = value
        elif lowered == "x-timestamp":
            timestamp = value
        elif lowered == "x-signature-simple":
            simple = value
    if not signature:
        raise DiditSandboxRefusedError(401, "simple_signature_rejected" if simple else "signature_rejected")
    try:
        body = json.loads(payload.decode("utf-8"), object_pairs_hook=_pairs)
    except (UnicodeError, json.JSONDecodeError, DiditSandboxRefusedError) as exc:
        raise DiditSandboxRefusedError(400, "malformed_json") from exc
    if not isinstance(body, dict):
        raise DiditSandboxRefusedError(400, "malformed_json")
    verify_v2(
        body,
        signature=signature,
        previous_signature=previous,
        timestamp=timestamp,
        secret=secret,
        previous_secret=_secret("WHITEPACT_DIDIT_SANDBOX_WEBHOOK_SECRET_PREVIOUS"),
        now=time.time() if now is None else now,
    )
    _require_identity(body)
    current = time.time() if now is None else now
    _remember(body, hashlib.sha256(payload).hexdigest(), now=current)
    return {
        "result": "sandbox_receipt_stored",
        "event_id": str(body["event_id"]),
        "status": str(body["status"]),
    }


async def handle_sandbox_webhook(request: Request) -> JSONResponse:
    try:
        receipt = assess_sandbox_event(await request.body(), dict(request.headers))
    except DiditSandboxRefusedError as exc:
        return JSONResponse(status_code=exc.status_code, content={"error": exc.code})
    return JSONResponse(status_code=200, content=receipt)
