"""Structured JSON logging setup using structlog."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_var.get()


def set_request_id(rid: str) -> None:
    _request_id_var.set(rid)


def new_request_id() -> str:
    rid = str(uuid.uuid4())[:8]
    set_request_id(rid)
    return rid


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    renderer: structlog.processors.JSONRenderer | structlog.dev.ConsoleRenderer
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Silence noisy libraries
    for lib in ("uvicorn.access", "uvicorn.error"):
        logging.getLogger(lib).setLevel(logging.WARNING)


def get_logger(name: str = "responsibleai") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
