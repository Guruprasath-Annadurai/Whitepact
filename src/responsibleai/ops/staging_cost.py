# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Hetzner staging cost ceiling. Prices are euro cents, VAT exclusive."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

PRICE_BOOK_PATH = (
    Path(__file__).resolve().parents[3]
    / "infra"
    / "terraform"
    / "modules"
    / "whitepact-hetzner-foundation"
    / "pricing"
    / "hetzner-fsn1.json"
)

# The staging root's approved inventory. One of each, NAT public IPv4 only, LB11.
STAGING_SHAPE = {
    "saas": "cx33",
    "authority": "cx33",
    "execution": "cx23",
    "nat": "cx23",
    "load_balancer": "lb11",
    "primary_ipv4": 1,
}
STAGING_CEILING_CENTS = 3595


class PriceBookError(ValueError):
    """The price book cannot price the requested shape."""


@dataclass(frozen=True)
class CostLine:
    name: str
    sku: str
    count: int
    monthly_cents: int


@dataclass(frozen=True)
class SpendAlert:
    severity: str
    estimated_cents: int
    ceiling_cents: int
    action: str

    @property
    def blocks_apply(self) -> bool:
        return self.severity == "critical"


def load_price_book(path: Path | None = None) -> dict[str, object]:
    book_path = path or PRICE_BOOK_PATH
    payload = json.loads(book_path.read_text(encoding="utf-8"))
    if payload.get("currency") != "EUR" or payload.get("vat") != "exclusive":
        raise PriceBookError("Price book must be EUR exclusive of VAT.")
    return payload


def staging_lines(book: dict[str, object] | None = None) -> tuple[CostLine, ...]:
    """Price the approved staging inventory. Missing SKUs fail closed."""
    priced = book or load_price_book()
    servers = priced["server_monthly_cents"]
    balancers = priced["load_balancer_monthly_cents"]
    if not isinstance(servers, dict) or not isinstance(balancers, dict):
        raise PriceBookError("Price book server or load balancer table is invalid.")
    ipv4 = priced["primary_ipv4_monthly_cents"]
    if isinstance(ipv4, bool) or not isinstance(ipv4, int):
        raise PriceBookError("Primary IPv4 price is invalid.")
    rows = (
        ("saas", STAGING_SHAPE["saas"], 1, servers),
        ("authority", STAGING_SHAPE["authority"], 1, servers),
        ("execution", STAGING_SHAPE["execution"], 1, servers),
        ("nat", STAGING_SHAPE["nat"], 1, servers),
        ("load_balancer", STAGING_SHAPE["load_balancer"], 1, balancers),
    )
    lines: list[CostLine] = []
    for name, sku, count, table in rows:
        unit = table.get(sku)
        if isinstance(unit, bool) or not isinstance(unit, int):
            raise PriceBookError(f"No euro-cent price for {sku}.")
        lines.append(CostLine(name, str(sku), count, unit * count))
    lines.append(CostLine("primary_ipv4", "ipv4", 1, ipv4))
    return tuple(lines)


def staging_monthly_cents(book: dict[str, object] | None = None) -> int:
    return sum(line.monthly_cents for line in staging_lines(book))


def optional_backup_eur(book: dict[str, object] | None = None) -> str:
    """Hetzner backups are 20 percent of the four server SKUs, not the load balancer.

    2796 euro cents * 0.20 = 559.2 euro cents = 5.592 EUR.
    """
    from decimal import Decimal

    priced = book or load_price_book()
    if priced["backup_rate_of_server"] != "0.20":
        raise PriceBookError("Backup rate must stay the documented 20 percent.")
    server_names = {"saas", "authority", "execution", "nat"}
    server_cents = sum(
        line.monthly_cents for line in staging_lines(priced) if line.name in server_names
    )
    eur = (Decimal(server_cents) * Decimal("0.20")) / Decimal(100)
    return f"{eur:.3f}"


def assess_spend(estimated_cents: int, ceiling_cents: int = STAGING_CEILING_CENTS) -> SpendAlert:
    if estimated_cents < 0 or ceiling_cents < 0:
        raise PriceBookError("Costs cannot be negative.")
    if estimated_cents > ceiling_cents:
        return SpendAlert(
            severity="critical",
            estimated_cents=estimated_cents,
            ceiling_cents=ceiling_cents,
            action=(
                "Do not run terraform apply. The estimate is above the approved ceiling. "
                "Remove the extra resource or obtain a new owner ceiling before planning again."
            ),
        )
    if estimated_cents == ceiling_cents:
        return SpendAlert(
            severity="at_ceiling",
            estimated_cents=estimated_cents,
            ceiling_cents=ceiling_cents,
            action=(
                "The approved shape consumes the entire ceiling. Do not enable Hetzner backups, "
                "volumes, a second server, or traffic beyond the included allowance without a new owner ceiling."
            ),
        )
    if estimated_cents * 10 >= ceiling_cents * 8:
        return SpendAlert(
            severity="warning",
            estimated_cents=estimated_cents,
            ceiling_cents=ceiling_cents,
            action=(
                "Estimated spend is at least 80 percent of the ceiling. "
                "Notify the owner before adding any resource."
            ),
        )
    return SpendAlert(
        severity="ok",
        estimated_cents=estimated_cents,
        ceiling_cents=ceiling_cents,
        action="Estimate is inside the ceiling. Apply is still forbidden until the owner gate is recorded.",
    )
