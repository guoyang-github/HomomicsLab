"""Structured logging configuration with correlation-id support."""

import json
import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, Dict, Optional

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: Optional[str]) -> None:
    """Set the correlation id for the current async/sync context."""
    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    """Return the current correlation id, if any."""
    return _correlation_id.get()


def new_correlation_id() -> str:
    """Generate a new correlation id."""
    return str(uuid.uuid4())


class correlation_id_context:
    """Context manager / async context manager for correlation ids."""

    def __init__(self, correlation_id: Optional[str] = None):
        self.correlation_id = correlation_id or new_correlation_id()
        self._token = None

    def __enter__(self):
        self._token = _correlation_id.set(self.correlation_id)
        return self.correlation_id

    def __exit__(self, exc_type, exc, tb):
        if self._token is not None:
            _correlation_id.reset(self._token)

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, exc_type, exc, tb):
        self.__exit__(exc_type, exc, tb)


class CorrelationIdFilter(logging.Filter):
    """Inject ``correlation_id`` into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class JsonFormatter(logging.Formatter):
    """JSON log formatter with correlation id and structured extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
            "source": {
                "pathname": record.pathname,
                "lineno": record.lineno,
                "function": record.funcName,
            },
        }

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        # Merge any extra fields attached to the record.
        extra_keys = getattr(record, "extra_keys", None) or []
        for key in extra_keys:
            payload[key] = getattr(record, key)

        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(
    level: str = "INFO",
    json_format: bool = True,
) -> None:
    """Configure root logging for HomomicsLab.

    Args:
        level: Minimum log level (DEBUG, INFO, WARNING, ERROR).
        json_format: If True, emit JSON lines; otherwise a simple text format.
    """
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(CorrelationIdFilter())

    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s %(levelname)s [%(correlation_id)s] %(name)s: %(message)s"
            )
        )

    # Replace existing handlers to avoid duplicate lines during reconfiguration.
    root.handlers = [handler]

    # Reduce noise from overly chatty third-party libraries.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
