# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute

from responsibleai.sovereign.protocol import CapabilityAvailability, SovereignFeature
from responsibleai.sovereign.router import router
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.web_routes import web_router

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "sovereign-v1-web.json"
TS_RETRY = ROOT / "sdk" / "typescript" / "sovereign" / "retry.ts"

ENUM_DEFS = (
    "CapabilityAvailability",
    "MissionDisposition",
    "GauntletStatus",
    "TraceStageStatus",
)


def _router_paths(api_router) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                out.add((method, route.path))
    return out


def _load_contract() -> dict:
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


def test_web_contract_routes_exist() -> None:
    data = _load_contract()
    routes = _router_paths(router) | _router_paths(web_router)
    missing: list[str] = []
    for cap in data.get("capabilities", []):
        if cap.get("availability") not in ("AVAILABLE", "EXPERIMENTAL"):
            continue
        fid = cap.get("feature_id") or cap.get("feature")
        for ep in cap.get("endpoints", []):
            key = (ep["method"], ep["path"])
            if key not in routes:
                missing.append(f"{fid}: {key}")
    assert not missing, f"missing routes: {missing}"


def test_available_capabilities_have_schemas() -> None:
    data = _load_contract()
    for cap in data.get("capabilities", []):
        if cap.get("availability") != "AVAILABLE":
            continue
        fid = cap.get("feature_id") or cap.get("feature")
        assert cap.get("endpoints"), fid
        assert cap.get("response_schema") is not None, fid
        for ep in cap.get("endpoints", []):
            assert ep.get("method") and ep.get("path"), fid
        if cap.get("feature_id") not in ("status", "capabilities"):
            assert cap.get("request_schema") is not None or fid == "status", fid
        assert cap.get("unknown_behavior") is not None, fid
        assert cap.get("unavailable_behavior") is not None, fid
        assert cap.get("feature_id"), fid
        assert cap.get("feature_version"), fid


def test_contract_enums_defined() -> None:
    data = _load_contract()
    defs = data.get("$defs", {})
    for name in ENUM_DEFS:
        assert name in defs, name
        assert defs[name].get("enum"), name


def test_contract_capability_negotiation_consistency() -> None:
    data = _load_contract()
    negotiated = {
        f.name.value: f.availability for f in SovereignService().get_capabilities().features
    }
    for cap in data.get("capabilities", []):
        if cap.get("availability") != "AVAILABLE":
            continue
        neg = cap.get("negotiation_name")
        if not neg:
            continue
        try:
            feat = SovereignFeature(neg)
        except ValueError:
            continue
        avail = negotiated.get(feat.value)
        assert avail in (
            CapabilityAvailability.AVAILABLE,
            CapabilityAvailability.EXPERIMENTAL,
        ), f"contract claims {cap['feature_id']} but negotiation reports {avail}"


def test_browser_safe_post_routes_in_contract() -> None:
    data = _load_contract()
    routes = _router_paths(web_router)
    missing: list[str] = []
    for cap in data.get("capabilities", []):
        if cap.get("availability") not in ("AVAILABLE", "EXPERIMENTAL"):
            continue
        for ep in cap.get("endpoints", []):
            if ep["method"] != "POST":
                continue
            path = ep["path"]
            if not path.startswith("/api/web/sovereign/"):
                continue
            key = (ep["method"], path)
            if key not in routes:
                missing.append(f"{cap.get('feature_id')}: {key}")
    assert not missing, f"missing browser routes: {missing}"


def test_backend_available_routes_in_contract() -> None:
    data = _load_contract()
    contract_paths: set[tuple[str, str]] = set()
    for cap in data.get("capabilities", []):
        for ep in cap.get("endpoints", []):
            contract_paths.add((ep["method"], ep["path"]))
    routes = _router_paths(router)
    sovereign_only = {r for r in routes if r[1].startswith("/api/sovereign")}
    missing_in_contract = sorted(sovereign_only - contract_paths)
    assert not missing_in_contract, f"routes not documented in contract: {missing_in_contract}"


def test_typescript_retry_map_aligns_with_never_retry_ops() -> None:
    text = TS_RETRY.read_text(encoding="utf-8")
    for op in (
        "shadow",
        "simulate_blast_radius",
        "gauntlet",
        "capsule_reproduce",
    ):
        assert f'{op}: "NEVER_BLINDLY_RETRY"' in text
