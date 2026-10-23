# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Nonproduction reservation storage primitive, NOT a provisioning authority.

This disconnected primitive can only reserve PENDING identities. It cannot
publish ACTIVE, activate Store A, issue grants or complete provisioning. A
separately authenticated controller, protected database role and completion
admission verifier are still mandatory before any runtime integration.
"""

from __future__ import annotations

import re
import secrets
import sqlite3
import uuid
from dataclasses import astuple, dataclass

from responsibleai.data_governance.backup_defense import SqliteDurableLifecycleStateProvider
from responsibleai.environment import is_production


class ProvisioningReservationError(RuntimeError):
    """Pending evidence is unavailable or conflicts; no authority is created."""


@dataclass(frozen=True)
class PendingTenantIdentity:
    deployment_id: str
    request_id: str
    principal_id: str
    operation_digest: str
    tenant_id: str
    generation_id: str
    status: str


class PendingTenantReservations:
    """Durable exactly-once pending reservation; caller authentication is NOT implemented here."""

    def __init__(self, provider: SqliteDurableLifecycleStateProvider) -> None:
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        if (
            type(provider) is not SqliteDurableLifecycleStateProvider
            or not provider.verify_integrity()
        ):
            raise ProvisioningReservationError("Verified durable Store B is required")
        self._provider = provider

    def initialize(self) -> None:
        """Explicit test/engineering setup; never called by a read or reservation."""
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute(
                "CREATE TABLE tenant_provisioning_reservations ("
                "deployment_id TEXT NOT NULL,request_id TEXT NOT NULL,"
                "principal_id TEXT NOT NULL,operation_digest TEXT NOT NULL,"
                "tenant_id TEXT NOT NULL UNIQUE,generation_id TEXT NOT NULL UNIQUE "
                "CHECK(length(generation_id)=64 AND generation_id NOT GLOB '*[^a-f0-9]*'),"
                "status TEXT NOT NULL CHECK(status='PENDING'),"
                "PRIMARY KEY(deployment_id,request_id))"
            )
            for action in ("UPDATE", "DELETE"):
                connection.execute(
                    f"CREATE TRIGGER tenant_reservation_no_{action.lower()} BEFORE {action} "
                    "ON tenant_provisioning_reservations BEGIN "
                    "SELECT RAISE(ABORT,'Pending identity reservations are immutable'); END"
                )
            connection.commit()
        finally:
            connection.close()

    def reserve(
        self, *, deployment_id: str, request_id: str, principal_id: str, operation_digest: str
    ) -> PendingTenantIdentity:
        """Reserve only pending data; never infer that a claimed principal is authorized."""
        if is_production():
            raise ProvisioningReservationError("Reservation primitive is not production qualified")
        for value in (deployment_id, request_id, principal_id):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
                raise ProvisioningReservationError("Invalid reservation binding")
        if not isinstance(operation_digest, str) or not re.fullmatch(
            r"[a-f0-9]{64}", operation_digest
        ):
            raise ProvisioningReservationError("Invalid operation digest")
        if not self._provider.verify_integrity():
            raise ProvisioningReservationError("Store B integrity is unverified")
        connection = self._provider._get_connection()
        try:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT deployment_id,request_id,principal_id,operation_digest,"
                "tenant_id,generation_id,status FROM tenant_provisioning_reservations "
                "WHERE deployment_id=? AND request_id=?",
                (deployment_id, request_id),
            ).fetchone()
            if row is not None:
                if row[2:4] != (principal_id, operation_digest) or row[6] != "PENDING":
                    raise ProvisioningReservationError("Reservation binding conflict")
                result = PendingTenantIdentity(*row)
            else:
                result = PendingTenantIdentity(
                    deployment_id,
                    request_id,
                    principal_id,
                    operation_digest,
                    str(uuid.uuid4()),
                    secrets.token_hex(32),
                    "PENDING",
                )
                connection.execute(
                    "INSERT INTO tenant_provisioning_reservations VALUES(?,?,?,?,?,?,?)",
                    astuple(result),
                )
            connection.commit()
            return result
        except sqlite3.Error as error:
            raise ProvisioningReservationError("Pending reservation storage unavailable") from error
        finally:
            connection.close()
