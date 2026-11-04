"""Small logging setup with a per-request correlation ID.

Usage::

    configure_logging(settings.log_level)
    log = get_logger(__name__)
    request_id = new_request_id()
    log.info("starting assessment", extra={"county": "Machakos"})
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

_request_id: ContextVar[str] = ContextVar("request_id", default="-")


class RequestIdFilter(logging.Filter):
    """Inject the current request ID into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id.get()
        return True


def new_request_id() -> str:
    """Start a new correlation scope and return its short ID."""
    value = uuid.uuid4().hex[:12]
    _request_id.set(value)
    return value


def current_request_id() -> str:
    return _request_id.get()


def configure_logging(level: str = "INFO") -> None:
    """Configure a single stdout handler. Safe to call more than once."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s %(levelname)-8s %(name)s [%(request_id)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    handler.addFilter(RequestIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())

    # AWS SDK and HTTP client logs are noisy at INFO.
    for noisy in ("botocore", "boto3", "urllib3", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
