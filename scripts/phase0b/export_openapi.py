#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "src"))
os.environ.setdefault("WHITEPACT_LOG_LEVEL", "ERROR")
from fastapi.testclient import TestClient  # noqa: E402
from responsibleai.dashboard.app import app  # noqa: E402

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/openapi.json")
out.write_text(json.dumps(TestClient(app).get("/api/openapi.json").json()), encoding="utf-8")
print(len(json.loads(out.read_text()).get("paths", {})))
