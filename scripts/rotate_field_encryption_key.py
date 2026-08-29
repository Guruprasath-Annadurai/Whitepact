#!/usr/bin/env python3
"""Re-encrypt every field-encrypted column under the currently active
field-encryption scheme — legacy Fernet rotation (unchanged, original
behavior), or migration to/rotation within the new
`governance/crypto`-based scheme (Enterprise Neural Phase 2 Step 5, see
`docs/enterprise-neural/02_PHASE2_STEP5_REPORT.md`).

Read `compliance/KEY_MANAGEMENT.md` before running this — it explains
the full rotation procedure this script is one step of.

**Mode 1 — legacy Fernet rotation** (original behavior, unchanged):

    1. Generate a new Fernet key.
    2. Put it FIRST in RAI_FIELD_ENCRYPTION_KEY (comma-separated), keeping
       the old key(s) after it so existing ciphertext still decrypts.
    3. Run this script — it reads every row of every encrypted column
       (decrypts with whichever key in the list matches) and writes it
       back (always encrypts with the first key).
    4. Only once this has completed successfully against your real
       database should you drop the old key from RAI_FIELD_ENCRYPTION_KEY.

    Usage:
        RAI_FIELD_ENCRYPTION_KEY="new_key,old_key" RAI_DB_PATH=./data/rai.db \
            python scripts/rotate_field_encryption_key.py

**Mode 2 — migrate to (or rotate within) the new scheme**: set
`RAI_ROOT_KEY` (a 32-byte urlsafe-base64-encoded key — generate one
with `python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"`).
This script resolves the current `FIELD_ENCRYPTION` key from a
`LocalEnvelopeKeyProvider` backed by the real `CryptoKeyRepository`
(persisted to the same database this script rotates data in — not a
throwaway in-memory store), activates it for this run via
`configure_field_encryption_key()`, then sweeps every encrypted column:
existing legacy-Fernet ciphertext and pre-encryption plaintext both get
re-encrypted under the new scheme (the same ORM round-trip mechanism
Mode 1 already uses — `EncryptedString.process_result_value` already
tries the new scheme first, legacy Fernet second, so nothing special is
needed to *read* mixed-scheme data). Set `RAI_CRYPTO_ROTATE_VERSION=1`
to force a new key *version* even if one is already active (real
rotation within the new scheme, not just first-time activation).

**If you have existing legacy Fernet ciphertext, keep
`RAI_FIELD_ENCRYPTION_KEY` set to it alongside `RAI_ROOT_KEY` for this
run.** Without it, this script cannot decrypt existing legacy
ciphertext before re-encrypting — it would silently re-encrypt the
still-encrypted Fernet token *as if it were plaintext*, corrupting the
data (recoverable only by someone who still has the old Fernet key and
manually unwraps twice). A pre-flight check refuses to proceed if it
detects legacy-Fernet-shaped ciphertext with no legacy key configured
to unwrap it first — see `_refuse_if_unrecoverable_legacy_ciphertext`.

    Usage:
        RAI_ROOT_KEY="<32-byte urlsafe-base64 key>" \
        RAI_FIELD_ENCRYPTION_KEY="<existing key(s), if any>" \
        RAI_CRYPTO_ENVIRONMENT=prod RAI_DB_PATH=./data/rai.db \
            python scripts/rotate_field_encryption_key.py

`RAI_CRYPTO_ENVIRONMENT` (default `"prod"`) must match whatever
environment name any future application-startup wiring uses for the
same `KeyProvider` — see `docs/enterprise-neural/02_PHASE2_STEP5_REPORT.md`
for why this is provisional (no application code constructs a
`KeyProvider` yet; this script is the first thing in the codebase that
does, as an explicit, standalone administrative action).

Safe to re-run in either mode: rows already encrypted under the
currently active key are read and rewritten as a no-op
(same-ciphertext-producing plaintext).

Deliberately does not touch webhook payload signing or SAML session
signing — see `docs/enterprise-neural/02_PHASE2_STEP4_REPORT.md`'s
scope correction for webhooks (a two-party secret, not this script's
concern) and the fact that SAML session tokens are never persisted as
encrypted-at-rest column data in the first place (they're short-lived
bearer tokens, not rows in a table).
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sqlalchemy import select, update  # noqa: E402

from responsibleai.db.crypto_key_repository import CryptoKeyRepository  # noqa: E402
from responsibleai.db.encryption import (  # noqa: E402
    _load_fernet,
    configure_field_encryption_key,
)
from responsibleai.db.engine import (  # noqa: E402
    audit_log,
    create_engine,
    org_api_keys,
    public_incident_reports,
    webhook_configs,
)
from responsibleai.governance.crypto import KeyPurpose  # noqa: E402
from responsibleai.governance.crypto.local_envelope import LocalEnvelopeKeyProvider  # noqa: E402

_ROOT_KEY_ENV_VAR = "RAI_ROOT_KEY"
_ENVIRONMENT_ENV_VAR = "RAI_CRYPTO_ENVIRONMENT"
_ROTATE_VERSION_ENV_VAR = "RAI_CRYPTO_ROTATE_VERSION"

# (table, [encrypted columns]) — kept in sync with db/engine.py's EncryptedString usage.
_ENCRYPTED_COLUMNS = [
    (audit_log, ["ip_address"]),
    (public_incident_reports, ["reporter_name", "reporter_contact"]),
    (webhook_configs, ["secret"]),
    (org_api_keys, ["mfa_secret"]),
]


async def _rotate_table(conn, table, columns: list[str]) -> int:
    id_col = table.c.id
    cols = [id_col, *(table.c[c] for c in columns)]
    result = await conn.execute(select(*cols))
    rows = result.fetchall()

    rewritten = 0
    for row in rows:
        row_id = row[0]
        values = dict(zip(columns, row[1:], strict=True))
        if all(v is None for v in values.values()):
            continue
        # SELECT already ran each value through EncryptedString.process_result_value
        # (new scheme first, then legacy Fernet, then plaintext passthrough) via
        # the type engine; writing it back runs process_bind_param (new scheme if
        # active, else legacy Fernet with the current first key).
        await conn.execute(update(table).where(id_col == row_id).values(**values))
        rewritten += 1
    return rewritten


def _load_root_key() -> bytes | None:
    raw = os.environ.get(_ROOT_KEY_ENV_VAR)
    if not raw:
        return None
    try:
        key = base64.urlsafe_b64decode(raw.encode("ascii"))
    except (binascii.Error, ValueError) as exc:
        print(f"{_ROOT_KEY_ENV_VAR} is not valid urlsafe-base64: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    if len(key) != 32:
        print(
            f"{_ROOT_KEY_ENV_VAR} must decode to exactly 32 bytes, got {len(key)}. Generate one with: "
            'python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"',
            file=sys.stderr,
        )
        raise SystemExit(1)
    return key


async def _activate_new_scheme_if_requested(engine) -> bool:
    """Returns True if the new scheme was activated for this run."""
    root_key = _load_root_key()
    if root_key is None:
        return False

    environment = os.environ.get(_ENVIRONMENT_ENV_VAR, "prod")
    store = CryptoKeyRepository(engine)
    provider = LocalEnvelopeKeyProvider(root_key, environment=environment, store=store)

    if os.environ.get(_ROTATE_VERSION_ENV_VAR):
        key_id = await provider.rotate(KeyPurpose.FIELD_ENCRYPTION, None)
        dek = await provider.get_decryption_key(key_id)
        print(
            f"Rotated FIELD_ENCRYPTION key to version {key_id.version} (environment={environment!r})."
        )
    else:
        key_id, dek = await provider.get_encryption_key(KeyPurpose.FIELD_ENCRYPTION, None)
        print(
            f"Activated FIELD_ENCRYPTION key version {key_id.version} (environment={environment!r})."
        )

    configure_field_encryption_key(key_id, dek)
    return True


_FERNET_VERSION_BYTE = 0x80


async def _refuse_if_unrecoverable_legacy_ciphertext(conn) -> None:
    """Mode 2 safety check: activating the new scheme without a legacy
    key configured means any pre-existing legacy Fernet ciphertext
    can't be decrypted before being re-encrypted — it would be
    silently double-wrapped as new-scheme "plaintext" instead,
    corrupting it. Scans raw stored values for the structural shape of
    a legacy Fernet token (its fixed version byte) and refuses to
    proceed if any is found with no legacy key available to unwrap it.

    Heuristic, not a certainty (the same "could a real plaintext value
    coincidentally look like ciphertext" class of question Phase 2
    Step 3 ran into with base32 TOTP secrets) — but the failure
    direction here is the safe one: a false positive just means an
    operator has to confirm no legacy data exists before proceeding, a
    false negative would mean silent corruption, and this check's
    entire purpose is making that false negative structurally
    unlikely, not eliminating an already-inherent ambiguity in the
    decrypt-or-assume-plaintext design every mode of this script relies
    on.
    """
    if _load_fernet() is not None:
        return  # legacy key available -- safe, decrypts correctly before re-encrypting

    for table, columns in _ENCRYPTED_COLUMNS:
        id_col = table.c.id
        cols = [id_col, *(table.c[c] for c in columns)]
        result = await conn.execute(select(*cols))
        for row in result.fetchall():
            for raw_value in row[1:]:
                if raw_value is None or not isinstance(raw_value, str):
                    continue
                try:
                    decoded = base64.urlsafe_b64decode(raw_value.encode("ascii"))
                except (binascii.Error, ValueError):
                    continue
                if decoded[:1] == bytes([_FERNET_VERSION_BYTE]):
                    print(
                        f"REFUSING TO PROCEED: {table.name!r} appears to contain legacy "
                        "Fernet ciphertext, but RAI_FIELD_ENCRYPTION_KEY is not set. "
                        "Migrating now would double-wrap that ciphertext under the new "
                        "scheme instead of decrypting it first, corrupting the data. Set "
                        "RAI_FIELD_ENCRYPTION_KEY to the existing key(s) alongside "
                        f"{_ROOT_KEY_ENV_VAR} for this run, then retry.",
                        file=sys.stderr,
                    )
                    raise SystemExit(1)


async def main() -> None:
    db_url = os.environ.get("RAI_DATABASE_URL") or os.environ.get("RAI_DB_PATH", "./data/rai.db")
    engine = create_engine(db_url)

    try:
        new_scheme_activated = await _activate_new_scheme_if_requested(engine)

        if not new_scheme_activated and _load_fernet() is None:
            print(
                f"Neither {_ROOT_KEY_ENV_VAR} nor RAI_FIELD_ENCRYPTION_KEY is set — "
                "nothing to rotate. Set one of them before running this script "
                "(see this script's own module docstring for both modes).",
                file=sys.stderr,
            )
            raise SystemExit(1)

        total = 0
        async with engine.raw.begin() as conn:
            if new_scheme_activated:
                await _refuse_if_unrecoverable_legacy_ciphertext(conn)
            for table, columns in _ENCRYPTED_COLUMNS:
                count = await _rotate_table(conn, table, columns)
                print(f"  {table.name}: re-encrypted {count} row(s) across {columns}")
                total += count
    finally:
        await engine.close()

    print(f"Done — {total} row(s) re-encrypted under the current key.")
    if new_scheme_activated:
        print("Rows now under the new governance/crypto envelope scheme.")
    else:
        print("Verify against your real data, then drop the old key from")
        print("RAI_FIELD_ENCRYPTION_KEY and restart once you're confident.")


if __name__ == "__main__":
    asyncio.run(main())
