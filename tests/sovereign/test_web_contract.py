# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
from pathlib import Path

from fastapi.routing import APIRoute

from responsibleai.sovereign.router import router, web_router

ROOT = Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "contracts" / "sovereign-v1-web.json"


def _router_paths(api_router) -> set[tuple[str, str]]:
    out: set[tuple[str, str]] = set()
    for route in api_router.routes:
        if not isinstance(route, APIRoute):
            continue
        for method in route.methods:
            if method in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                out.add((method, route.path))
    return out


def test_web_contract_routes_exist() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    routes = _router_paths(router) | _router_paths(web_router)
    missing: list[str] = []
    for cap in data.get("capabilities", []):
        if cap.get("availability") not in ("AVAILABLE", "EXPERIMENTAL"):
            continue
        for ep in cap.get("endpoints", []):
            key = (ep["method"], ep["path"])
            if key not in routes:
                missing.append(f"{cap['feature']}: {key}")
    assert not missing, f"missing routes: {missing}"


def test_available_capabilities_have_schemas() -> None:
    data = json.loads(CONTRACT.read_text(encoding="utf-8"))
    for cap in data.get("capabilities", []):
        if cap.get("availability") != "AVAILABLE":
            continue
        assert cap.get("endpoints"), cap["feature"]
        assert cap.get("unknown_behavior") is not None or cap.get("notes") is not None, cap["feature"]
