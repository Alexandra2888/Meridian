"""Structured logging + LangSmith hook. RFC §4.5, §7.

Every node logs with the same `trace_id` so a single request stitches together
in the log stream. Cost numbers are computed in `app.clients.llm` from token
counts and merged into the `final` SSE event.
"""

from __future__ import annotations

import logging
import os
import uuid

import structlog

from app.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(message)s")

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.ConsoleRenderer(colors=True),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )

    # LangSmith opt-in: setting LANGCHAIN_TRACING_V2=true + LANGSMITH_API_KEY in
    # the env is the LangChain-native path — we just propagate the settings.
    if settings.langchain_tracing_v2 and settings.langsmith_api_key:
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
        os.environ.setdefault("LANGCHAIN_API_KEY", settings.langsmith_api_key)
        os.environ.setdefault("LANGCHAIN_PROJECT", settings.langsmith_project)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name) if name else structlog.get_logger()


def new_trace_id() -> str:
    return uuid.uuid4().hex
