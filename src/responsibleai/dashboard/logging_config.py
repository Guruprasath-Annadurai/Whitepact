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
        processors=shared_processors
        + [
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

    # Enterprise Readiness Phase 9 (secrets-never-logged sweep): found by
    # a real test, not hypothesized -- `aiosqlite`'s own DEBUG-level
    # logging emits the complete SQL statement INCLUDING BOUND PARAMETER
    # VALUES for every query, which means any webhook signing secret,
    # TOTP MFA secret, or backup code ever written via an unencrypted
    # column (encryption is opt-in via RAI_FIELD_ENCRYPTION_KEY, not
    # default) would appear in plaintext in the log stream the moment an
    # operator sets RAI_LOG_LEVEL=DEBUG for troubleshooting -- something
    # this codebase's own root-logger-level setting above would
    # otherwise silently permit. Capped at INFO regardless of the
    # configured app log level, same reasoning `asyncpg` (the Postgres
    # driver) gets the same treatment for: raw SQL/parameter logging is
    # never something turning up app log verbosity should grant for
    # free. If genuine query-level debugging is ever needed, raise
    # these two specific loggers back to DEBUG deliberately, in a
    # disposable environment, not as a byproduct of app-wide DEBUG.
    for lib in ("aiosqlite", "asyncpg"):
        logging.getLogger(lib).setLevel(
            max(logging.INFO, getattr(logging, level.upper(), logging.INFO))
        )


def get_logger(name: str = "responsibleai") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
