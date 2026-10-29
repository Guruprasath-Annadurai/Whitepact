# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Public surface for the Didit sandbox receiver.

This application exposes one route. It does not mount the enterprise console,
the reference identity webhook, or any administrative service.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from responsibleai.enterprise.didit_sandbox import handle_sandbox_webhook

app = FastAPI(title="WhitePact Didit sandbox webhook", docs_url=None, redoc_url=None, openapi_url=None)


@app.post("/api/enterprise/identity/verification/didit/sandbox")
async def didit_sandbox_webhook(request: Request) -> JSONResponse:
    return await handle_sandbox_webhook(request)
